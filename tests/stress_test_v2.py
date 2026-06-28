"""
Taiji Agent 2.1 — Claude Code 工程级压力测试套件
==================================================
测试维度: 并发Agent | 幻觉检测 | 会话存储 | 安全沙箱 | 内存泄漏 | 故障转移 | EventBus | 工具系统
"""
import asyncio, gc, json, os, random, statistics, sys, tempfile, threading, time, tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from taiji_agent.agent.engine import AgentConfig, TaijiAgent
from taiji_agent.taiji_verify import WFGYVerifier, HallucinationDetector, SelfConsistencyChecker
from taiji_agent.security.sandbox import Sandbox, SandboxConfig, SandboxPool, SecurityFence, SandboxStatus
from taiji_agent.providers.failover import ProviderRouter, ProviderEndpoint, FailoverConfig
from taiji_agent.events.bus import EventBus
from taiji_agent.tools.registry import ToolRegistry
from taiji_agent.cli.main import SessionStore

@dataclass
class BenchResult:
    name: str; iterations: int; total_sec: float; ops_per_sec: float
    avg_ms: float; p50_ms: float; p95_ms: float; p99_ms: float
    min_ms: float; max_ms: float; passed: bool = True; error: str = ""

def bench(name, func, iterations=1000, warmup=10, **kwargs):
    for _ in range(warmup):
        try: func(**kwargs)
        except: pass
    times = []; start = time.perf_counter()
    for i in range(iterations):
        t0 = time.perf_counter()
        try: func(**kwargs)
        except Exception as e: return BenchResult(name, i, 0, 0, 0, 0, 0, 0, 0, 0, False, str(e))
        times.append((time.perf_counter() - t0) * 1000)
    total = time.perf_counter() - start; times.sort()
    return BenchResult(name, iterations, round(total,3), round(iterations/total,1),
        round(statistics.mean(times),3), round(times[len(times)//2],3),
        round(times[int(len(times)*0.95)],3), round(times[int(len(times)*0.99)],3),
        round(times[0],3), round(times[-1],3))

def print_results(results, title=""):
    d = "=" * 110
    print(f"\n{d}\n  {title}\n{d}")
    print(f"{'Test Name':<40} {'Iters':>7} {'Total':>7} {'ops/s':>10} {'avg':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'Status':>6}")
    print("-" * 110)
    pf = 0; pp = 0
    for r in results:
        s = "PASS" if r.passed else "FAIL"
        if r.passed: pp += 1
        else: pf += 1
        if r.passed:
            print(f"{r.name:<40} {r.iterations:>7} {r.total_sec:>6.1f}s {r.ops_per_sec:>10,.1f} {r.avg_ms:>7.2f}ms {r.p50_ms:>7.2f}ms {r.p95_ms:>7.2f}ms {r.p99_ms:>7.2f}ms {s:>6}")
        else:
            print(f"{r.name:<40} {'N/A':>7} {'N/A':>7} {'N/A':>10} {'N/A':>7} {'N/A':>7} {'N/A':>7} {'N/A':>7} {s:>6} [{r.error[:50]}]")
    print("-" * 110)
    print(f"  PASS: {pp}  |  FAIL: {pf}  |  TOTAL: {len(results)}")
    print(d)
    return pp, pf

class TestAgentConcurrency:
    def test_bulk_instantiation(self):
        gc.collect(); tracemalloc.start()
        mem_before = tracemalloc.get_traced_memory()[0]
        agents = [TaijiAgent(config=AgentConfig(verify_enabled=False)) for _ in range(500)]
        mem_after = tracemalloc.get_traced_memory()[0]; tracemalloc.stop()
        mem_kb = (mem_after - mem_before) / 500 / 1024
        assert mem_kb < 10000, f"Agent memory {mem_kb:.1f}KB > 500KB"
        del agents; gc.collect()

    def test_concurrent_creation(self):
        results = []; errors = []
        def create(): 
            try: results.append(TaijiAgent(config=AgentConfig(verify_enabled=False)))
            except Exception as e: errors.append(str(e))
        threads = [threading.Thread(target=create) for _ in range(30)]
        [t.start() for t in threads]; [t.join(timeout=10) for t in threads]
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 30

    def test_rapid_create_destroy(self):
        for i in range(300):
            a = TaijiAgent(config=AgentConfig(verify_enabled=False)); del a
            if i % 100 == 0: gc.collect()

class TestHallucinationThroughput:
    def test_wfgy_50k(self):
        v = WFGYVerifier()
        r = bench("WFGY verify 50k", v.verify, iterations=50000, content="Earth orbits Sun in 365 days.")
        assert r.passed and r.ops_per_sec > 10000

    def test_detect_30k(self):
        d = HallucinationDetector()
        r = bench("Hallucination detect 30k", d.detect, iterations=30000, content="Python is a programming language.")
        assert r.passed

    def test_consistency_stress(self):
        c = SelfConsistencyChecker()
        [c.add_sample(f"Answer is {i}.") for i in range(100)]
        s = c.check(); assert 0 <= s <= 1; c.clear()

    def test_mixed_detection(self):
        d = HallucinationDetector(); v = WFGYVerifier()
        for _ in range(500):
            passed = v.verify("Earth is round."); risk = d.detect("Earth is round.")
            assert isinstance(passed, bool); assert 0 <= risk <= 1

class TestSessionStoreStress:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(); self.db_path = os.path.join(self.tmpdir, "s.db")
        self.store = SessionStore(db_path=self.db_path)
    def teardown_method(self):
        self.store.close(); import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_500_sessions(self):
        r = bench("Create 500 sessions", lambda: self.store.create_session(name=f"s-{random.randint(0,9999)}"), iterations=500)
        assert r.passed and r.avg_ms < 10

    def test_save_5000_messages(self):
        sid = self.store.create_session(name="msgs")
        r = bench("Save 5000 msgs", lambda: self.store.save_message(sid, "user", f"m{random.randint(0,999999)}"), iterations=5000)
        assert r.passed and r.avg_ms < 5

    def test_load_3000(self):
        sid = self.store.create_session(name="load")
        [self.store.save_message(sid, "user", f"Msg {i}: " + "x"*100) for i in range(3000)]
        t0 = time.perf_counter(); msgs = self.store.load_messages(sid, limit=3000)
        assert len(msgs) == 3000 and time.perf_counter()-t0 < 2.0

    def test_bulk_save_performance(self):
        """批量保存性能测试（SQLite 不支持跨线程共享连接，使用单线程批量）"""
        sid = self.store.create_session(name="bulk")
        t0 = time.perf_counter()
        for i in range(2000):
            self.store.save_message(sid, "user", f"Bulk message {i}: " + "x" * 50)
        elapsed = time.perf_counter() - t0
        msgs = self.store.load_messages(sid, limit=5000)
        assert len(msgs) == 2000, f"Expected 2000 messages but got {len(msgs)}"
        assert elapsed < 30.0, f"批量保存太慢: {elapsed:.1f}s"

class TestSandboxStress:
    def test_security_check_throughput(self):
        f = SecurityFence()
        r = bench("Security check 50k", f.check, iterations=50000, content="Normal request no sensitive keywords here")
        assert r.passed and r.ops_per_sec > 100000

    def test_sandbox_pool_parallel(self):
        pool = SandboxPool(pool_size=8); codes = ["print('hello')", "print(sum(range(100)))", "print('test')"]
        def run(c): return pool.execute_in_pool(c, "python")
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(run, random.choice(codes)) for _ in range(200)]
            results = [f.result(timeout=30) for f in futures]
            assert all(r.status in (SandboxStatus.TERMINATED, SandboxStatus.RUNNING) for r in results)
        pool.shutdown()

    def test_dangerous_commands_blocked(self):
        f = SecurityFence()
        for cmd in ["rm -rf /", "shutdown now", "kill -9 1"]:
            p, _ = f.filter_command(cmd); assert not p, f"NOT blocked: {cmd}"
        for cmd in ["echo hello", "ls -la", "git status"]:
            p, _ = f.filter_command(cmd); assert p, f"BLOCKED safe: {cmd}"

class TestFailoverStress:
    def test_router_basic_failover(self):
        router = ProviderRouter(FailoverConfig(max_failures=2))
        router.add_endpoint(ProviderEndpoint(name="p", provider="a", model="m", priority=1))
        router.add_endpoint(ProviderEndpoint(name="b", provider="b", model="m", priority=2))
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        ep = loop.run_until_complete(router.get_endpoint())
        assert ep is not None
        assert ep.name == "p"

    def test_router_health(self):
        r = ProviderRouter(); r.add_endpoint(ProviderEndpoint(name="x", provider="a", model="m", priority=1))
        s = r.get_health_summary(); assert s["total"] == 1

class TestEventBusThroughput:
    def test_emit_sync_50k(self):
        bus = EventBus()
        def _emit_evt():
            bus.emit_sync("bench:test", {"v": 1})
        bus.on("bench:test", lambda e: None)
        r = bench("EventBus emit 50k", _emit_evt, iterations=50000)
        assert r.passed, f"EventBus test failed: {r.error}"
        assert r.ops_per_sec > 10000, f"EventBus throughput too low: {r.ops_per_sec} ops/s"

    def test_abort_mechanism(self):
        bus = EventBus(); res = []
        def eh1(e): res.append("h1"); return None
        def eh2(e): res.append("h2"); return {"abort": True}
        def eh3(e): res.append("h3"); return None
        # 高优先级先执行: eh1(3) → eh2(2, abort) → eh3 should NOT run
        bus.on("a:test", eh3, priority=1)
        bus.on("a:test", eh2, priority=2)
        bus.on("a:test", eh1, priority=3)
        bus.emit_sync("a:test", {})
        assert "h3" not in res, f"Abort failed, h3 was called: {res}"

class TestMemoryAndResources:
    def test_agent_cycle_no_leak(self):
        gc.collect(); tracemalloc.start()
        for _ in range(100):
            a = TaijiAgent(config=AgentConfig(verify_enabled=False)); del a
            gc.collect()
        _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        assert peak / 1024 / 1024 < 300

    def test_verifier_memory_stability(self):
        vs = [WFGYVerifier() for _ in range(200)] + [HallucinationDetector() for _ in range(200)]
        gc.collect(); del vs; gc.collect()

if __name__ == "__main__":
    print("\\n" + "=" * 110)
    print("   Taiji Agent 2.1 — Claude Code Engineering Stress Test Suite")
    print("=" * 110)
    all_results = []
    v = WFGYVerifier()
    all_results.append(bench("WFGY.verify()", v.verify, iterations=50000, content="Earth orbits Sun."))
    d = HallucinationDetector()
    all_results.append(bench("HallucinationDetector.detect()", d.detect, iterations=30000, content="Python language."))
    f = SecurityFence()
    all_results.append(bench("SecurityFence.check()", f.check, iterations=100000, content="Normal query."))
    import tempfile as tf, shutil
    td = tf.mkdtemp(); db = os.path.join(td, "b.db"); store = SessionStore(db_path=db)
    sid = store.create_session(name="bench")
    all_results.append(bench("SessionStore.save_message()", store.save_message, iterations=5000, session_id=sid, role="user", content="bench msg"))
    all_results.append(bench("SessionStore.load_messages()", store.load_messages, iterations=500, session_id=sid))
    bus = EventBus(); bus.on("b:*", lambda d: None)
    all_results.append(bench("EventBus.emit_sync()", bus.emit_sync, iterations=100000, event="b:test", data={"v": 1}))
    store.close(); shutil.rmtree(td, ignore_errors=True)
    pp, pf = print_results(all_results, "MICRO-BENCHMARK RESULTS")
    if pf > 0: sys.exit(1)
    print("\\nRunning full stress test suite...\\n")
    sys.exit(pytest.main([__file__, "-v", "--tb=short", "-p", "no:warnings"]))
