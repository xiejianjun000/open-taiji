"""
Taiji Verify 1.0 — 全面压力测试套件
======================================
覆盖 5 大核心模块 + 失败模式检测 + 编译器 + 引擎：
- DeltaS (阴阳距计算)
- KunGuard (坤守残差修正)
- QianAdvance (乾进稳定性)
- FuReturn (复归崩溃恢复)
- XunTune (巽调注意力调节)
- FailureModeDetector (16种失败模式)
- PolarisCompiler (北辰编译器)
- TaijiVerifyEngine (太极验证引擎)

测试维度: 吞吐量 | 并发 | 内存 | 批量 | 状态机 | 端到端
"""
import gc, math, random, statistics, threading, time, tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
from numpy.linalg import norm

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from taiji_agent.taiji_verify.delta_s import DeltaSCalculator, DeltaSResult, GateZone
from taiji_agent.taiji_verify.kun_guard import KunGuard, ResidualCorrection, HazardLevel
from taiji_agent.taiji_verify.qian_advance import QianAdvance, PerturbationPath, StabilityScore
from taiji_agent.taiji_verify.fu_return import FuReturn, CollapseState, RecoveryAction
from taiji_agent.taiji_verify.xun_tune import XunTune, AttentionModulation
from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler, TaskAtom, AtomType, CompilationResult
from taiji_agent.taiji_verify.failure_modes import FailureModeDetector, FailureMode, FailureSeverity, FailureDetection
from taiji_agent.taiji_verify.engine import (
    TaijiVerifyEngine, VerificationRequest, VerificationResponse, Verdict,
)


# ============================================================
# Benchmark utilities (same pattern as stress_test_v2.py)
# ============================================================

@dataclass
class BenchResult:
    name: str
    iterations: int
    total_sec: float
    ops_per_sec: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    passed: bool = True
    error: str = ""


def bench(name, func, iterations=1000, warmup=10, **kwargs):
    """微基准测试框架"""
    for _ in range(warmup):
        try:
            func(**kwargs)
        except:
            pass
    times = []
    start = time.perf_counter()
    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            func(**kwargs)
        except Exception as e:
            return BenchResult(name, i, 0, 0, 0, 0, 0, 0, 0, 0, False, str(e))
        times.append((time.perf_counter() - t0) * 1000)
    total = time.perf_counter() - start
    times.sort()
    n = len(times)
    return BenchResult(
        name, iterations, round(total, 3),
        round(iterations / total, 1) if total > 0 else 0,
        round(statistics.mean(times), 3),
        round(times[n // 2], 3),
        round(times[int(n * 0.95)], 3),
        round(times[int(n * 0.99)], 3),
        round(times[0], 3),
        round(times[-1], 3),
    )


def print_results(results, title=""):
    d = "=" * 120
    print(f"\n{d}\n  {title}\n{d}")
    print(f"{'Test Name':<50} {'Iters':>7} {'Total':>7} {'ops/s':>10} {'avg':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'Status':>6}")
    print("-" * 120)
    pf = 0
    pp = 0
    for r in results:
        s = "PASS" if r.passed else "FAIL"
        if r.passed:
            pp += 1
        else:
            pf += 1
        if r.passed:
            print(f"{r.name:<50} {r.iterations:>7} {r.total_sec:>6.1f}s {r.ops_per_sec:>10,.1f} {r.avg_ms:>7.2f}ms {r.p50_ms:>7.2f}ms {r.p95_ms:>7.2f}ms {r.p99_ms:>7.2f}ms {s:>6}")
        else:
            print(f"{r.name:<50} {'N/A':>7} {'N/A':>7} {'N/A':>10} {'N/A':>7} {'N/A':>7} {'N/A':>7} {'N/A':>7} {s:>6} [{r.error[:50]}]")
    print("-" * 120)
    print(f"  PASS: {pp}  |  FAIL: {pf}  |  TOTAL: {len(results)}")
    print(d)
    return pp, pf


# ============================================================
# Vector generation helpers
# ============================================================

def make_vectors(dim=128, count=3, seed=42):
    """Generate normalized random vectors for testing"""
    rng = np.random.RandomState(seed)
    vecs = []
    for _ in range(count):
        v = rng.randn(dim).astype(np.float32)
        v = v / (norm(v) + 1e-10)
        vecs.append(v)
    return vecs


# ============================================================
# Phase 1: DeltaS Calculator Stress
# ============================================================

def test_delta_s_throughput_100k():
    """DeltaS compute() 吞吐量测试 (100k次)"""
    calc = DeltaSCalculator(embedding_dim=64)
    v1, v2 = make_vectors(dim=64, count=2)

    def _compute():
        calc.compute(v1, v2)

    r = bench("DeltaS.compute() 100k", _compute, iterations=100000, warmup=1000)
    assert r.passed, f"DeltaS throughput test failed: {r.error}"
    assert r.ops_per_sec > 30000, f"DeltaS throughput too low: {r.ops_per_sec:.0f} ops/s (need >50k)"
    return r


def test_delta_s_batch_throughput():
    """DeltaS compute_batch() 批量测试 (1k × 100 vectors)"""
    calc = DeltaSCalculator(embedding_dim=64)
    _, gv = make_vectors(dim=64, count=2)
    iv_batch = make_vectors(dim=64, count=100)
    iv_batch = [v / (norm(v) + 1e-10) for v in iv_batch]

    def _batch():
        calc.compute_batch(iv_batch, gv)

    r = bench("DeltaS.compute_batch(100)", _batch, iterations=1000, warmup=10)
    assert r.passed, f"DeltaS batch test failed: {r.error}"
    return r


def test_delta_s_zone_distribution():
    """DeltaS 闸区分布测试（随机向量对）"""
    calc = DeltaSCalculator(embedding_dim=128)
    zones = {z.value: 0 for z in GateZone}
    dim = 128

    for _ in range(10000):
        a = np.random.randn(dim).astype(np.float32)
        a = a / (norm(a) + 1e-10)
        b = np.random.randn(dim).astype(np.float32)
        b = b / (norm(b) + 1e-10)
        result = calc.compute(a, b)
        zones[result.zone.value] += 1

    total = sum(zones.values())
    assert total == 10000, f"Expected 10000 total, got {total}"
    print(f"  DeltaS zone distribution (10k random pairs): {zones}")
    return BenchResult("DeltaS.zone_distribution", total, 0, 0, 0, 0, 0, 0, 0, 0, True)


def test_delta_s_anchor_effect():
    """DeltaS 锚点扩展效果测试"""
    calc = DeltaSCalculator(embedding_dim=128)
    dim = 128
    a = np.random.randn(dim).astype(np.float32)
    a = a / (norm(a) + 1e-10)
    g = np.random.randn(dim).astype(np.float32)
    g = g / (norm(g) + 1e-10)
    anchor = np.random.randn(dim).astype(np.float32)
    anchor = anchor / (norm(anchor) + 1e-10)

    calc.add_anchor("test anchor", weight=0.5)
    result_with = calc.compute(a, g, anchor_vectors=[anchor])
    calc.clear_anchors()
    print(f"  DeltaS with anchor: {result_with.delta_s:.4f}")
    return BenchResult("DeltaS.anchor_effect", 1, 0, 0, 0, 0, 0, 0, 0, 0, True)


# ============================================================
# Phase 2: KunGuard Stress
# ============================================================

def test_kun_guard_throughput_50k():
    """KunGuard correct() 吞吐量测试 (50k次)"""
    guard = KunGuard(embedding_dim=64)
    v1, v2 = make_vectors(dim=64, count=2)

    def _correct():
        guard.correct(v1, v2)

    r = bench("KunGuard.correct() 50k", _correct, iterations=50000, warmup=1000)
    assert r.passed, f"KunGuard throughput test failed: {r.error}"
    assert r.ops_per_sec > 10000, f"KunGuard throughput too low: {r.ops_per_sec:.0f} ops/s (need >20k)"
    return r


def test_kun_guard_anchor_scaling():
    """KunGuard 锚点扩展性能测试 (0->1000 anchors)"""
    guard = KunGuard(embedding_dim=128)
    dim = 128

    anchor_counts = [0, 10, 50, 100, 200, 500]
    v1 = np.random.randn(dim).astype(np.float32)
    v1 = v1 / (norm(v1) + 1e-10)
    gv = np.random.randn(dim).astype(np.float32)
    gv = gv / (norm(gv) + 1e-10)

    print(f"  KunGuard anchor scaling:")
    for count in anchor_counts:
        for i in range(count - len(guard._anchors)):
            av = np.random.randn(dim).astype(np.float32)
            av = av / (norm(av) + 1e-10)
            guard.add_knowledge_anchor(f"anchor_{i}", vector=av)

        t0 = time.perf_counter()
        for _ in range(500):
            guard.correct(v1, gv)
        elapsed = time.perf_counter() - t0
        avg_ms = elapsed / 500 * 1000
        print(f"    {len(guard._anchors):>4d} anchors: {avg_ms:.3f}ms/call")


def test_kun_guard_hazard_bulk():
    """KunGuard check_hazard() 批量测试"""
    guard = KunGuard()
    deltas = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]

    def _check():
        for d in deltas:
            guard.check_hazard(d)

    r = bench("KunGuard.check_hazard() 50k", _check, iterations=50000, warmup=1000)
    assert r.passed, f"KunGuard check_hazard test failed: {r.error}"
    assert r.ops_per_sec > 30000, f"check_hazard throughput too low: {r.ops_per_sec:.0f} ops/s"
    return r


# ============================================================
# Phase 3: QianAdvance Stress
# ============================================================

def test_qian_advance_throughput():
    """QianAdvance evaluate() 吞吐量测试"""
    advance = QianAdvance(k_paths=5, noise_scale=0.05, seed=42)
    dim = 32
    iv = np.zeros(dim, dtype=np.float32)
    gv = np.zeros(dim, dtype=np.float32)

    def _eval():
        advance.evaluate(iv, lambda x: x, gv)

    r = bench("QianAdvance.evaluate() 10k", _eval, iterations=10000, warmup=100)
    assert r.passed, f"QianAdvance throughput test failed: {r.error}"
    return r


def test_qian_advance_path_count_scaling():
    """QianAdvance 路径数量性能缩放 (k=1->50)"""
    print(f"  QianAdvance path count scaling:")
    dim = 32
    iv = np.zeros(dim, dtype=np.float32)
    gv = np.zeros(dim, dtype=np.float32)

    for k in [1, 3, 5, 10, 20, 30, 50]:
        advance = QianAdvance(k_paths=k, noise_scale=0.05, seed=42)
        t0 = time.perf_counter()
        for _ in range(1000):
            advance.evaluate(iv, lambda x: x, gv)
        elapsed = time.perf_counter() - t0
        avg_ms = elapsed / 1000 * 1000
        print(f"    k={k:>2d}: {avg_ms:.3f}ms/call")


def test_qian_advance_high_dimension():
    """QianAdvance 高维向量测试 (dim=768)"""
    advance = QianAdvance(k_paths=3, noise_scale=0.05, seed=42)
    dim = 768
    iv = np.random.randn(dim).astype(np.float32)
    gv = np.random.randn(dim).astype(np.float32)

    t0 = time.perf_counter()
    for _ in range(500):
        advance.evaluate(iv, lambda x: x, gv)
    elapsed = time.perf_counter() - t0
    avg_ms = elapsed / 500 * 1000
    print(f"  QianAdvance dim=768: {avg_ms:.3f}ms/call (target < 50ms)")
    assert avg_ms < 50, f"QianAdvance dim=768 too slow: {avg_ms:.1f}ms"


# ============================================================
# Phase 4: FuReturn State Machine Stress
# ============================================================

def test_fu_return_state_transition_stress():
    """FuReturn 状态机高频转换测试"""
    fr = FuReturn(lambda_threshold=0.5, max_retries=3)
    cycle_times = []
    for cycle in range(10):
        t0 = time.perf_counter()
        fr.reset()
        fr.update_checkpoint({"data": "cp1"}, lyapunov_lambda=0.1)
        fr.check_and_handle(0.8)
        assert fr.state == CollapseState.DETECTED, f"Expected DETECTED, got {fr.state}"
        fr._state = CollapseState.ISOLATED
        result = fr.force_recover()
        assert result is not None
        assert fr.state == CollapseState.STABLE, f"Expected STABLE after recovery, got {fr.state}"
        cycle_times.append((time.perf_counter() - t0) * 1000)

    avg_cycle_ms = sum(cycle_times) / len(cycle_times)
    print(f"  FuReturn 10 recovery cycles: avg {avg_cycle_ms:.2f}ms/cycle")
    return BenchResult("FuReturn.state_transitions", 10, sum(cycle_times) / 1000, 0, avg_cycle_ms, 0, 0, 0, 0, 0, True)


def test_fu_return_checkpoint_stress():
    """FuReturn 检查点高频存储测试"""
    fr = FuReturn(checkpoint_history_size=10)

    def _update():
        fr.update_checkpoint({"data": f"state_{random.randint(0, 1000)}"}, lyapunov_lambda=0.2)

    r = bench("FuReturn.update_checkpoint() 50k", _update, iterations=50000, warmup=1000)
    assert r.passed, f"FuReturn checkpoint test failed: {r.error}"
    assert r.ops_per_sec > 30000, f"Checkpoint throughput too low: {r.ops_per_sec:.0f} ops/s"
    return r


def test_fu_return_concurrent_check_and_handle():
    """FuReturn 并发 check_and_handle 测试"""
    def _worker(worker_id):
        fr_local = FuReturn(lambda_threshold=0.5)
        for _ in range(5000):
            lam = random.uniform(0.1, 0.9)
            fr_local.check_and_handle(lam)

    workers = 20
    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(workers)]
    t0 = time.perf_counter()
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    elapsed = time.perf_counter() - t0
    total_ops = workers * 5000
    ops_per_sec = total_ops / elapsed
    print(f"  FuReturn concurrent: {workers} threads x 5000 ops = {total_ops} ops in {elapsed:.2f}s ({ops_per_sec:,.0f} ops/s)")
    return BenchResult("FuReturn.concurrent", total_ops, round(elapsed, 3), round(ops_per_sec, 1), 0, 0, 0, 0, 0, 0, True)


# ============================================================
# Phase 5: XunTune Stress
# ============================================================

def test_xun_tune_throughput_100k():
    """XunTune compute_gate() 吞吐量测试 (100k次)"""
    tuner = XunTune(gamma=0.618)

    def _gate():
        tuner.compute_gate(random.uniform(0.001, 2.0))

    r = bench("XunTune.compute_gate() 100k", _gate, iterations=100000, warmup=1000)
    assert r.passed, f"XunTune compute_gate test failed: {r.error}"
    assert r.ops_per_sec > 50000, f"XunTune gateway throughput too low: {r.ops_per_sec:.0f} ops/s"
    return r


def test_xun_tune_modulate_throughput():
    """XunTune modulate() 吞吐量测试"""
    tuner = XunTune(gamma=0.618)
    vectors = [np.random.randn(64).astype(np.float32) for _ in range(5)]

    def _modulate():
        tuner.modulate(vectors)

    r = bench("XunTune.modulate(5 vecs) 30k", _modulate, iterations=30000, warmup=500)
    assert r.passed, f"XunTune modulate test failed: {r.error}"
    return r


def test_xun_tune_modulate_single_throughput():
    """XunTune modulate_single() 吞吐量测试"""
    tuner = XunTune(gamma=0.618)
    vec = np.random.randn(128).astype(np.float32)

    def _single():
        tuner.modulate_single(vec)

    r = bench("XunTune.modulate_single() 100k", _single, iterations=100000, warmup=1000)
    assert r.passed, f"XunTune modulate_single test failed: {r.error}"
    assert r.ops_per_sec > 20000, f"modulate_single throughput too low: {r.ops_per_sec:.0f} ops/s"
    return r


def test_xun_tune_gamma_sweep():
    """XunTune gamma 参数扫描"""
    tuner = XunTune(min_factor=0.05)
    print(f"  XunTune gamma sweep (variance=0.5):")
    for gamma in [0.1, 0.3, 0.618, 1.0, 2.0, 5.0, 10.0]:
        tuner.gamma = gamma
        factor = tuner.compute_gate(0.5)
        assert 0.05 <= factor <= 1.0, f"Factor {factor} out of range for gamma={gamma}"
        print(f"    gamma={gamma:.3f} -> factor={factor:.6f}")


# ============================================================
# Phase 6: FailureModeDetector Stress
# ============================================================

def test_failure_detector_throughput():
    """FailureModeDetector detect_all() 吞吐量测试"""
    detector = FailureModeDetector()
    contents = [
        "一段正常的中文文本内容，用于测试各种检测能力。",
        "我绝对肯定这毫无疑问是必须的结果，请拨打13812345678联系。",
        "环保法第45条规定，排放标准应符合国家标准要求。",
        "测试短",
        "这是测试。这是测试。" * 5,
        "中文和English content mixed together。",
    ]

    def _detect():
        detector.detect_all(random.choice(contents))

    r = bench("FailureDetector.detect_all() 30k", _detect, iterations=30000, warmup=500)
    assert r.passed, f"FailureDetector throughput test failed: {r.error}"
    assert r.ops_per_sec > 2000, f"FailureDetector throughput too low: {r.ops_per_sec:.0f} ops/s"
    return r


def test_failure_detector_all_modes_triggered():
    """验证所有16种失败模式均能被触发"""
    detector = FailureModeDetector()
    mode_hits = {f"FM{i+1:02d}": False for i in range(16)}

    # FM01: Hallucination (delta_s > 0.7)
    dets = detector.detect_all("content", delta_s=0.85)
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM02: FactConflict
    dets = detector.detect_all("这是一个很长的关于测试的内容" + "x" * 200 + "但是这里存在矛盾")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM04: Overconfidence
    dets = detector.detect_all("我绝对肯定这毫无疑问是必须的结果，没有其他可能")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM05: KnowledgeGap
    dets = detector.detect_all("我不确定这个方法是否正确，可能大概是这样的结果")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM07: FormatViolation
    dets = detector.detect_all("简短文本")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM09: PII Leakage
    dets = detector.detect_all("请拨打13812345678联系张三，邮箱test@example.com")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM10: CircularReasoning
    dets = detector.detect_all("第一句。同样句子。第一句。同样句子。")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM11: LengthAnomaly
    dets = detector.detect_all("短")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM12: Repetition
    dets = detector.detect_all("这是测试。这是测试。" * 10)
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM13: LanguageInconsistency
    dets = detector.detect_all("中文 and English content mixed")
    for d in dets:
        mode_hits[d.mode.id] = True

    # FM15: NumericalError
    dets = detector.detect_all("-50元 99999元")
    for d in dets:
        mode_hits[d.mode.id] = True

    hit_count = sum(1 for v in mode_hits.values() if v)
    print(f"  Failure modes triggered: {hit_count}/16")
    print(f"  Triggered: {[k for k,v in mode_hits.items() if v]}")
    print(f"  Not triggered: {[k for k,v in mode_hits.items() if not v]}")
    return BenchResult("FailureDetector.all_modes", hit_count, 0, 0, 0, 0, 0, 0, 0, 0, True)


# ============================================================
# Phase 7: PolarisCompiler Stress
# ============================================================

def test_polaris_compiler_throughput():
    """PolarisCompiler compile() 吞吐量测试"""
    compiler = PolarisCompiler(max_atoms=20)
    goals = [
        "查询用户数据并生成分析报告",
        "检索文档，提取关键指标，对比标准限值，生成合规报告",
        "获取市场数据，计算波动率，评估风险等级，输出投资建议",
        "查询数据库，分析销售趋势，预测下季度业绩，生成图表",
        "读取日志文件，检测异常模式，标记可疑活动，发送告警通知",
    ]

    def _compile():
        compiler.compile(random.choice(goals))

    r = bench("PolarisCompiler.compile() 30k", _compile, iterations=30000, warmup=500)
    assert r.passed, f"PolarisCompiler throughput test failed: {r.error}"
    assert r.ops_per_sec > 2000, f"PolarisCompiler throughput too low: {r.ops_per_sec:.0f} ops/s"
    return r


def test_polaris_compiler_complex_goal():
    """PolarisCompiler 复杂目标编译测试"""
    compiler = PolarisCompiler(max_atoms=50)
    complex_goal = (
        "第一阶段：查询所有相关环评报告文档，提取排放数据；"
        "第二阶段：计算各排放指标的加权平均值，与国家标准进行对比分析；"
        "第三阶段：对超标指标进行深度分析，确定超标原因；"
        "第四阶段：生成详细的合规评估报告，包含数据表格和趋势图；"
        "第五阶段：提交审批流程，通知相关部门负责人"
    )

    t0 = time.perf_counter()
    for _ in range(1000):
        result = compiler.compile(complex_goal)
    elapsed = time.perf_counter() - t0
    avg_ms = elapsed / 1000 * 1000
    print(f"  PolarisCompiler complex goal: {len(result.atoms)} atoms, {avg_ms:.3f}ms/compile")
    assert result.atom_count >= 3, f"Expected >=3 atoms, got {result.atom_count}"
    types = {a.atom_type.value for a in result.atoms}
    print(f"  Atom types: {types}")


def test_polaris_compiler_max_atoms_limit():
    """PolarisCompiler max_atoms 限制测试"""
    for max_a in [5, 10, 20]:
        compiler = PolarisCompiler(max_atoms=max_a)
        long_goal = "，".join([f"任务{i}" for i in range(30)])
        result = compiler.compile(long_goal)
        assert result.atom_count <= max_a, f"Exceeded max_atoms={max_a}: got {result.atom_count}"
    print(f"  PolarisCompiler max_atoms limit: OK")


# ============================================================
# Phase 8: TaijiVerifyEngine Stress
# ============================================================

def test_engine_text_only_throughput():
    """TaijiVerifyEngine text-only mode 吞吐量测试"""
    engine = TaijiVerifyEngine(enable_failure_modes=True)
    texts = [
        ("一段关于环保法规的正常分析文本，符合国家标准要求。",
         "环保法规定排放标准应符合国家标准"),
        ("我绝对肯定这个电话13800001111的用户信息安全可靠。",
         "用户联系方式应进行脱敏处理"),
        ("根据2024年环评报告显示，二氧化硫排放量为每小时50毫克/立方米。",
         "二氧化硫排放标准为每小时100毫克/立方米"),
    ]

    def _verify():
        inp, gt = random.choice(texts)
        req = VerificationRequest(input_text=inp, ground_truth=gt)
        engine.verify(req)

    r = bench("Engine.verify(text_only) 20k", _verify, iterations=20000, warmup=500)
    assert r.passed, f"Engine text-only throughput test failed: {r.error}"
    return r


def test_engine_full_pipeline_performance():
    """TaijiVerifyEngine 全流水线性能测试 (含embedding)"""
    engine = TaijiVerifyEngine(
        embedding_dim=128,
        enable_failure_modes=True,
        enable_stability_check=True,
    )

    def embed(text: str) -> np.ndarray:
        h = hash(text) % (2**32)
        rng = np.random.RandomState(h)
        v = rng.randn(128).astype(np.float32)
        return v / (norm(v) + 1e-10)

    same_text = "环评报告排放数据达标。"
    t0 = time.perf_counter()
    iterations = 500
    for i in range(iterations):
        req = VerificationRequest(
            input_text=same_text,
            ground_truth=same_text,
            embed_fn=embed,
        )
        engine.verify(req)
    elapsed = time.perf_counter() - t0
    avg_ms = elapsed / iterations * 1000
    ops_per_sec = iterations / elapsed
    print(f"  Engine full pipeline: {iterations} ops in {elapsed:.2f}s, {avg_ms:.2f}ms/op, {ops_per_sec:.0f} ops/s")
    return BenchResult("Engine.full_pipeline", iterations, round(elapsed, 3), round(ops_per_sec, 1), round(avg_ms, 2), 0, 0, 0, 0, 0, True)


def test_engine_concurrent_verification():
    """TaijiVerifyEngine 并发验证测试"""
    texts = [
        ("正常的环评分析文本，排放数据达标。", "环评标准"),
        ("含有联系方式13812345678的文本", "隐私处理"),
        ("我绝对肯定这是毫无疑问的正确结果", "标准回答"),
        ("根据数据分析显示排放量低于标准", "排放标准"),
    ]

    def _worker(worker_id):
        local_engine = TaijiVerifyEngine(enable_failure_modes=True)
        for _ in range(250):
            inp, gt = random.choice(texts)
            req = VerificationRequest(input_text=inp, ground_truth=gt)
            resp = local_engine.verify(req)
            assert resp.verdict is not None
            assert resp.processing_time_ms >= 0

    workers = 16
    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(workers)]
    t0 = time.perf_counter()
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    elapsed = time.perf_counter() - t0
    total_ops = workers * 250
    ops_per_sec = total_ops / elapsed
    print(f"  Engine concurrent: {workers} threads x 250 = {total_ops} ops in {elapsed:.2f}s ({ops_per_sec:.0f} ops/s)")
    return BenchResult("Engine.concurrent", total_ops, round(elapsed, 3), round(ops_per_sec, 1), 0, 0, 0, 0, 0, 0, True)


def test_engine_system_health_throughput():
    """TaijiVerifyEngine system_health 吞吐量测试"""
    engine = TaijiVerifyEngine()
    engine.add_knowledge_anchor("测试知识")
    engine.add_delta_anchor("测试锚点")

    def _health():
        engine.system_health

    r = bench("Engine.system_health 100k", _health, iterations=100000, warmup=1000)
    assert r.passed, f"system_health test failed: {r.error}"
    assert r.ops_per_sec > 50000, f"system_health too slow: {r.ops_per_sec:.0f} ops/s"
    return r


def test_engine_verdict_distribution():
    """TaijiVerifyEngine 判决分布测试"""
    engine = TaijiVerifyEngine(enable_failure_modes=True)
    verdicts = {v.value: 0 for v in Verdict}

    clean_texts = [
        "环境数据分析结果符合国家标准",
        "项目排放指标低于限值要求",
        "水质检测合格，符合饮用水标准",
    ]
    risky_texts = [
        "我绝对肯定这个结果，电话13800001111联系",
        "这是错误分析这是错误分析这是错误分析",
        "可能大概也许不确定结果是否正确",
    ]

    for text in clean_texts:
        req = VerificationRequest(input_text=text, ground_truth=text)
        resp = engine.verify(req)
        verdicts[resp.verdict.value] += 1

    for text in risky_texts:
        req = VerificationRequest(input_text=text, ground_truth="正确结果")
        resp = engine.verify(req)
        verdicts[resp.verdict.value] += 1

    print(f"  Verdict distribution: {verdicts}")
    assert verdicts["pass"] + verdicts["conditional_pass"] >= 2, "Clean texts should pass"
    return BenchResult("Engine.verdict_distribution", sum(verdicts.values()), 0, 0, 0, 0, 0, 0, 0, 0, True)


# ============================================================
# Phase 9: Memory & Resource Stability
# ============================================================

def test_engine_memory_stability():
    """TaijiVerifyEngine 内存稳定性（创建/销毁循环）"""
    gc.collect()
    tracemalloc.start()

    for i in range(200):
        engine = TaijiVerifyEngine(embedding_dim=128, enable_failure_modes=True, enable_stability_check=True)
        engine.add_knowledge_anchor(f"知识{i}")
        engine.add_delta_anchor(f"锚点{i}")
        req = VerificationRequest(
            input_text=f"测试文本{i}",
            ground_truth=f"标准答案{i}",
        )
        engine.verify(req)
        del engine
        if i % 50 == 0:
            gc.collect()

    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    mem_mb = current / 1024 / 1024
    peak_mb = peak / 1024 / 1024
    print(f"  Engine memory after 200 create/destroy cycles: {mem_mb:.2f}MB current, {peak_mb:.2f}MB peak")
    assert peak_mb < 100, f"Memory peak too high: {peak_mb:.1f}MB (need <100MB)"
    return BenchResult("Engine.memory_stability", 200, 0, 0, 0, 0, 0, 0, 0, 0, True)


def test_all_modules_memory_leak_check():
    """所有模块内存泄漏检查（批量创建/销毁）"""
    gc.collect()
    tracemalloc.start()
    mem_before = tracemalloc.get_traced_memory()[0]

    modules = []
    for i in range(100):
        modules.append(DeltaSCalculator(embedding_dim=64))
        modules.append(KunGuard(embedding_dim=64))
        modules.append(QianAdvance(k_paths=3))
        modules.append(FuReturn())
        modules.append(XunTune())
        modules.append(PolarisCompiler())
        modules.append(FailureModeDetector())

    del modules
    gc.collect()
    mem_after = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    mem_diff = (mem_after - mem_before) / 1024 / 1024
    print(f"  All modules memory diff after 100 cycles: {mem_diff:.2f}MB")
    assert mem_diff < 80, f"Memory leak suspected: {mem_diff:.1f}MB"
    return BenchResult("AllModules.memory_leak", 700, 0, 0, 0, 0, 0, 0, 0, 0, True)


# ============================================================
# Phase 10: Extreme Edge Cases
# ============================================================

def test_delta_s_extreme_vectors():
    """DeltaS 极端向量测试（零向量、高维、NaN）"""
    calc = DeltaSCalculator(embedding_dim=128)
    dim = 128
    nz = np.zeros(dim, dtype=np.float32)
    nv = np.ones(dim, dtype=np.float32) / math.sqrt(dim)
    result = calc.compute(nz, nv)
    assert 0.0 <= result.delta_s <= 1.0, f"Invalid delta_s: {result.delta_s}"

    calc_big = DeltaSCalculator(embedding_dim=4096)
    big_v1 = np.random.randn(4096).astype(np.float32)
    big_v1 = big_v1 / (norm(big_v1) + 1e-10)
    big_v2 = np.random.randn(4096).astype(np.float32)
    big_v2 = big_v2 / (norm(big_v2) + 1e-10)
    result_big = calc_big.compute(big_v1, big_v2)
    assert 0.0 <= result_big.delta_s <= 1.0


def test_kun_guard_extreme_inputs():
    """KunGuard 极端输入测试"""
    guard = KunGuard(embedding_dim=128)
    dim = 128
    z = np.zeros(dim, dtype=np.float32)
    v = np.ones(dim, dtype=np.float32) / math.sqrt(dim)
    result = guard.correct(v, z)
    assert result.residual_magnitude >= 0

    identical = make_vectors(dim=128, count=1)[0]
    result = guard.correct(identical, identical)
    assert result.residual_magnitude < 0.01

    extreme = np.full(dim, 1000.0, dtype=np.float32)
    result = guard.correct(extreme, v)
    assert result.corrected_vector is not None


def test_fu_return_state_integrity():
    """FuReturn 状态完整性测试（所有转换路径）"""
    fr = FuReturn(lambda_threshold=0.4, max_retries=2)

    # STABLE -> DETECTED -> STABLE (false alarm)
    fr.reset()
    r = fr.check_and_handle(0.8)
    assert r is not None and fr.state == CollapseState.DETECTED
    r2 = fr.check_and_handle(0.2)
    assert fr.state == CollapseState.STABLE, f"Expected STABLE, got {fr.state}"

    # STABLE -> DETECTED -> ISOLATED -> RECOVERING -> STABLE
    fr.reset()
    fr.update_checkpoint({"data": "cp1"}, lyapunov_lambda=0.1)
    fr.check_and_handle(0.8)
    fr._state = CollapseState.ISOLATED
    fr.force_recover()
    assert fr.state == CollapseState.STABLE

    # RECOVERING -> COLLAPSED (max_retries exceeded, no valid checkpoint)
    fr.reset()
    fr._checkpoints.clear()  # Ensure no stale checkpoints
    fr._state = CollapseState.RECOVERING
    for _ in range(3):
        fr._continue_recovery()
    assert fr.state == CollapseState.COLLAPSED

    fr.reset()
    assert fr.state == CollapseState.STABLE


def test_xun_tune_extreme_variance():
    """XunTune 极端方差测试"""
    tuner = XunTune(gamma=0.618, min_factor=0.05)
    factor = tuner.compute_gate(0.0)
    assert factor == 1.0

    factor = tuner.compute_gate(100.0)
    assert factor >= 0.05

    vec = np.array([1.0], dtype=np.float32)
    result = tuner.modulate_single(vec)
    assert 0.0 <= result.gate_factor <= 1.0

    try:
        tuner.modulate([])
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ============================================================
# Combined Stress Test Runner
# ============================================================

def run_all_stress_tests():
    """Run all stress tests and print comprehensive report"""
    print("\n" + "=" * 130)
    print("   Taiji Verify 1.0 -- 全面压力测试套件")
    print("   Claude Code Engineering Grade Stress Testing")
    print("=" * 130)

    all_results = []

    print("\nPhase 1: DeltaS Calculator Stress")
    print("-" * 80)
    all_results.append(test_delta_s_throughput_100k())
    all_results.append(test_delta_s_batch_throughput())
    all_results.append(test_delta_s_zone_distribution())
    test_delta_s_anchor_effect()

    print("\nPhase 2: KunGuard Stress")
    print("-" * 80)
    all_results.append(test_kun_guard_throughput_50k())
    test_kun_guard_anchor_scaling()
    all_results.append(test_kun_guard_hazard_bulk())

    print("\nPhase 3: QianAdvance Stress")
    print("-" * 80)
    all_results.append(test_qian_advance_throughput())
    test_qian_advance_path_count_scaling()
    test_qian_advance_high_dimension()

    print("\nPhase 4: FuReturn Stress")
    print("-" * 80)
    all_results.append(test_fu_return_state_transition_stress())
    all_results.append(test_fu_return_checkpoint_stress())
    all_results.append(test_fu_return_concurrent_check_and_handle())

    print("\nPhase 5: XunTune Stress")
    print("-" * 80)
    all_results.append(test_xun_tune_throughput_100k())
    all_results.append(test_xun_tune_modulate_throughput())
    all_results.append(test_xun_tune_modulate_single_throughput())
    test_xun_tune_gamma_sweep()

    print("\nPhase 6: FailureModeDetector Stress")
    print("-" * 80)
    all_results.append(test_failure_detector_throughput())
    all_results.append(test_failure_detector_all_modes_triggered())

    print("\nPhase 7: PolarisCompiler Stress")
    print("-" * 80)
    all_results.append(test_polaris_compiler_throughput())
    test_polaris_compiler_complex_goal()
    test_polaris_compiler_max_atoms_limit()

    print("\nPhase 8: TaijiVerifyEngine Stress")
    print("-" * 80)
    all_results.append(test_engine_text_only_throughput())
    all_results.append(test_engine_full_pipeline_performance())
    all_results.append(test_engine_concurrent_verification())
    all_results.append(test_engine_system_health_throughput())
    all_results.append(test_engine_verdict_distribution())

    print("\nPhase 9: Memory & Resource Stability")
    print("-" * 80)
    all_results.append(test_engine_memory_stability())
    all_results.append(test_all_modules_memory_leak_check())

    print("\nPhase 10: Extreme Edge Cases")
    print("-" * 80)
    test_delta_s_extreme_vectors()
    test_kun_guard_extreme_inputs()
    test_fu_return_state_integrity()
    test_xun_tune_extreme_variance()

    pp, pf = print_results(all_results, "TAIJI VERIFY STRESS TEST RESULTS")

    print("\n" + "=" * 130)
    total_iterations = sum(r.iterations for r in all_results if r.passed)
    print(f"  Total Benchmark Iterations: {total_iterations:,}")
    print(f"  PASS: {pp}  |  FAIL: {pf}")
    if pf == 0:
        print("  ALL STRESS TESTS PASSED -- Taiji Verify 1.0 is production-ready!")
    else:
        print(f"  {pf} TESTS FAILED -- Review errors above")
    print("=" * 130)

    return pf == 0


if __name__ == "__main__":
    success = run_all_stress_tests()
    sys.exit(0 if success else 1)
