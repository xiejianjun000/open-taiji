"""
OpenTaiji 2.0 全面压力测试
"""

import asyncio
import time
import sys
import gc
import tracemalloc
from pathlib import Path
from typing import List

# 添加 src 目录到路径
test_dir = Path(__file__).parent
project_root = test_dir.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

print("=" * 70)
print("OpenTaiji 2.0 全面压力测试")
print("=" * 70)
print()


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.duration = 0.0
        self.error = None
        self.metrics = {}

    def mark_pass(self, duration: float, metrics: dict = None):
        self.passed = True
        self.duration = duration
        self.metrics = metrics or {}

    def mark_fail(self, duration: float, error: str):
        self.passed = False
        self.duration = duration
        self.error = error


results: List[TestResult] = []


def run_test(name: str, test_func):
    """运行单个测试"""
    result = TestResult(name)
    start = time.perf_counter()
    
    try:
        metrics = test_func()
        duration = time.perf_counter() - start
        result.mark_pass(duration, metrics)
        status = "✅ PASS"
    except Exception as e:
        duration = time.perf_counter() - start
        result.mark_fail(duration, str(e))
        status = "❌ FAIL"
    
    results.append(result)
    
    print(f"{status} | {name:40s} | {duration:.4f}s", end="")
    if result.error:
        print(f" | Error: {result.error[:50]}")
    else:
        metrics_str = " | ".join([f"{k}={v}" for k, v in result.metrics.items()])
        if metrics_str:
            print(f" | {metrics_str}")
        else:
            print()
    
    return result


# ============================================================
# 1. 模块导入测试
# ============================================================
print("\n【1. 模块导入测试】")
print("-" * 70)


def test_import_core():
    """测试核心模块导入"""
    tracemalloc.start()
    start_mem = tracemalloc.get_traced_memory()[0]
    
    from taiji_agent import (
        TaijiAgent, AgentConfig,
        WFGYVerifier, HallucinationDetector,
        SoulLoader, Soul,
        SessionMemory, ToolRegistry,
    )
    
    current_mem = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    
    return {"memory_mb": current_mem / 1024 / 1024}


run_test("核心模块导入", test_import_core)


def test_import_providers():
    """测试 Provider 导入"""
    from taiji_agent.providers.anthropic import AnthropicProvider
    from taiji_agent.providers.openai import OpenAIProvider
    from taiji_agent.providers.chinese import (
        QwenProvider, GLMProvider, KimiProvider, DoubaoProvider
    )
    return {"providers": 6}


run_test("Provider 模块导入", test_import_providers)


def test_import_gateway():
    """测试网关导入"""
    from taiji_agent.gateway import (
        MessageGateway, create_gateway,
        TelegramAdapter, DiscordAdapter,
        WeChatWorkAdapter, DingTalkAdapter, FeishuAdapter
    )
    return {"platforms": 5}


run_test("网关模块导入", test_import_gateway)


def test_import_skills():
    """测试技能模块导入"""
    from taiji_agent.skills import SkillManager, Skill, SkillCreator
    return {}


run_test("技能模块导入", test_import_skills)


def test_import_learning():
    """测试学习模块导入"""
    from taiji_agent.learning import HonchoMemory, SelfImprovingLoop
    return {}


run_test("学习模块导入", test_import_learning)


# ============================================================
# 2. 实例化测试
# ============================================================
print("\n【2. 实例化测试】")
print("-" * 70)


def test_instance_agent():
    """测试 Agent 实例化"""
    tracemalloc.start()
    
    from taiji_agent import TaijiAgent, AgentConfig
    
    agent = TaijiAgent(config=AgentConfig())
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return {"agents": 1, "peak_mem_mb": peak / 1024 / 1024}


run_test("Agent 实例化", test_instance_agent)


def test_instance_verifiers():
    """测试验证器实例化"""
    from taiji_agent import WFGYVerifier, HallucinationDetector
    
    verifiers = [WFGYVerifier() for _ in range(100)]
    detectors = [HallucinationDetector() for _ in range(100)]
    
    return {"verifiers": 100, "detectors": 100}


run_test("验证器批量实例化 (100x)", test_instance_verifiers)


def test_instance_soul_loader():
    """测试 Soul 加载器"""
    from taiji_agent import SoulLoader
    
    loader = SoulLoader()
    souls = loader.list_souls()
    
    loaded = [loader.load(s) for s in souls]
    
    return {"souls_loaded": len(loaded)}


run_test("Soul 加载器", test_instance_soul_loader)


def test_instance_tool_registry():
    """测试工具注册表"""
    from taiji_agent import ToolRegistry
    
    registry = ToolRegistry()
    tools = registry.list_tools()
    
    return {"tools": len(tools)}


run_test("工具注册表", test_instance_tool_registry)


def test_instance_skill_manager():
    """测试技能管理器"""
    from taiji_agent.skills import SkillManager
    
    manager = SkillManager()
    skills = manager.list()
    market = manager.browse_market()
    
    return {"skills": len(skills), "market": len(market)}


run_test("技能管理器", test_instance_skill_manager)


def test_instance_honcho():
    """测试 Honcho 记忆"""
    from taiji_agent.learning import HonchoMemory
    
    honcho = HonchoMemory()
    
    return {"peer_cards": len(honcho._peer_cards)}


run_test("Honcho 记忆", test_instance_honcho)


# ============================================================
# 3. WFGY 性能测试
# ============================================================
print("\n【3. WFGY 防幻觉性能测试】")
print("-" * 70)


def test_wfgy_verify():
    """测试 WFGY 验证性能"""
    from taiji_agent import WFGYVerifier
    
    verifier = WFGYVerifier()
    verifier.add_rule(r"\d+%", True, "百分比")
    verifier.add_rule(r"据我所知", False, "不确定表达")
    
    test_content = "这是一个测试内容，包含一些数字如95%和不确定的表达如据我所知。"
    
    iterations = 10000
    start = time.perf_counter()
    
    for _ in range(iterations):
        verifier.verify(test_content)
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration,
        "avg_ms": duration / iterations * 1000
    }


run_test("WFGY 验证 (10,000次)", test_wfgy_verify)


def test_hallucination_detect():
    """测试幻觉检测性能"""
    from taiji_agent import HallucinationDetector
    
    detector = HallucinationDetector()
    
    test_contents = [
        "这是一个正常的内容。",
        "据我所知，这可能是正确的，但我不确定。",
        "绝对没有问题，所有人都知道这是100%正确的。",
        "根据研究显示，大约有50%的可能性，以及一些据我所知的情况。",
        "这是一段很长的文本，包含了各种可能的内容，包括数字如12345和百分比99.9%，以及一些模糊的表达如据我所知和一般来说。",
    ]
    
    iterations = 5000
    start = time.perf_counter()
    
    for _ in range(iterations):
        for content in test_contents:
            detector.detect(content)
    
    total_ops = iterations * len(test_contents)
    duration = time.perf_counter() - start
    
    return {
        "total_ops": total_ops,
        "ops_per_sec": total_ops / duration,
        "avg_ms": duration / total_ops * 1000
    }


run_test("幻觉检测 (25,000次)", test_hallucination_detect)


def test_wfgy_consistency():
    """测试一致性检查"""
    from taiji_agent.taiji_verify import SelfConsistencyChecker
    
    checker = SelfConsistencyChecker()
    
    samples = [
        "答案确实是42。",
        "答案是42，这是确定的。",
        "我确认答案是42。",
        "答案应该是42。",
        "答案是四十二。",
    ]
    
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        for sample in samples:
            checker.add_sample(sample)
        checker.check()
        checker.clear()
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("自一致性检查 (1,000次)", test_wfgy_consistency)


# ============================================================
# 4. 并发测试
# ============================================================
print("\n【4. 并发测试】")
print("-" * 70)


async def async_test_concurrent_verification():
    """并发验证测试"""
    from taiji_agent import WFGYVerifier
    
    verifier = WFGYVerifier()
    
    async def verify():
        verifier.verify("测试内容")
    
    tasks = [verify() for _ in range(1000)]
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - start
    
    return {
        "concurrent_tasks": 1000,
        "duration": duration,
        "ops_per_sec": 1000 / duration
    }


def test_concurrent_verification():
    return asyncio.run(async_test_concurrent_verification())


run_test("并发验证 (1,000任务)", test_concurrent_verification)


async def async_test_concurrent_memory():
    """并发记忆操作测试"""
    from taiji_agent import SessionMemory
    
    mem = SessionMemory()
    
    async def save_and_get(i):
        key = f"test_key_{i}"
        mem.save(key, f"test_value_{i}")
        mem.get(key)
    
    tasks = [save_and_get(i) for i in range(500)]
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - start
    
    return {
        "operations": 500,
        "duration": duration,
        "ops_per_sec": 500 / duration
    }


def test_concurrent_memory():
    return asyncio.run(async_test_concurrent_memory())


run_test("并发记忆操作 (500任务)", test_concurrent_memory)


# ============================================================
# 5. 记忆系统测试
# ============================================================
print("\n【5. 记忆系统测试】")
print("-" * 70)


def test_memory_save_get():
    """测试记忆保存和获取"""
    from taiji_agent import SessionMemory
    
    mem = SessionMemory()
    
    iterations = 1000
    start = time.perf_counter()
    
    for i in range(iterations):
        key = f"perf_test_{i}"
        value = f"测试内容 {i} " * 10
        mem.save(key, value)
        result = mem.get(key)
        assert result == value
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("记忆保存/获取 (1,000次)", test_memory_save_get)


def test_memory_search():
    """测试记忆搜索"""
    from taiji_agent import SessionMemory
    
    mem = SessionMemory()
    
    for i in range(100):
        mem.save(f"key_{i}", f"这是包含关键词的测试内容 {i}")
    
    iterations = 100
    start = time.perf_counter()
    
    for _ in range(iterations):
        mem.search("关键词")
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("记忆搜索 (100次)", test_memory_search)


def test_memory_todo():
    """测试 Todo 功能"""
    from taiji_agent import SessionMemory
    
    mem = SessionMemory()
    
    iterations = 500
    start = time.perf_counter()
    
    for i in range(iterations):
        mem.add_todo(f"任务 {i}")
    
    todos = mem.get_todos()
    
    for todo in todos[:10]:
        mem.done_todo(todo["task"])
    
    duration = time.perf_counter() - start
    
    return {
        "added": iterations,
        "completed": 10,
        "ops_per_sec": iterations / duration
    }


run_test("Todo 操作 (500次)", test_memory_todo)


# ============================================================
# 6. 技能系统测试
# ============================================================
print("\n【6. 技能系统测试】")
print("-" * 70)


def test_skill_browse():
    """测试技能浏览"""
    from taiji_agent.skills import SkillManager
    
    manager = SkillManager()
    
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        manager.browse_market()
        manager.list()
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("技能浏览 (1,000次)", test_skill_browse)


def test_skill_create():
    """测试技能创建"""
    from taiji_agent.skills import SkillManager
    
    manager = SkillManager()
    
    iterations = 50
    start = time.perf_counter()
    
    created_ids = []
    for i in range(iterations):
        skill = asyncio.run(manager.create(
            name=f"测试技能 {i}",
            description=f"测试描述 {i}",
            instructions=f"测试指令 {i}",
        ))
        created_ids.append(skill.id)
    
    duration = time.perf_counter() - start
    
    for skill_id in created_ids:
        manager.delete(skill_id)
    
    return {
        "created": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("技能创建 (50次)", test_skill_create)


def test_skill_use():
    """测试技能使用"""
    from taiji_agent.skills import SkillManager
    
    manager = SkillManager()
    
    manager.install("code-review")
    
    iterations = 500
    start = time.perf_counter()
    
    for _ in range(iterations):
        manager.use("code-review")
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("技能使用 (500次)", test_skill_use)


# ============================================================
# 7. 工具系统测试
# ============================================================
print("\n【7. 工具系统测试】")
print("-" * 70)


def test_tool_list():
    """测试工具列表"""
    from taiji_agent import ToolRegistry
    
    registry = ToolRegistry()
    
    iterations = 5000
    start = time.perf_counter()
    
    for _ in range(iterations):
        registry.list_tools()
        registry.get_schemas()
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("工具列表 (5,000次)", test_tool_list)


def test_tool_execution():
    """测试工具执行"""
    from taiji_agent.tools import ToolRegistry
    
    registry = ToolRegistry()
    
    iterations = 100
    start = time.perf_counter()
    
    class MockToolCall:
        def __init__(self, name, arguments):
            self.name = name
            self.arguments = arguments
    
    for i in range(iterations):
        tool_call = MockToolCall("file_list", {"path": "."})
        registry.execute(tool_call)
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("工具执行 (100次)", test_tool_execution)


# ============================================================
# 8. Soul 系统测试
# ============================================================
print("\n【8. Soul 系统测试】")
print("-" * 70)


def test_soul_load():
    """测试 Soul 加载"""
    from taiji_agent import SoulLoader
    
    loader = SoulLoader()
    
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        soul = loader.load("default")
        assert soul is not None
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration
    }


run_test("Soul 加载 (1,000次)", test_soul_load)


def test_soul_inject():
    """测试 Soul 注入"""
    from taiji_agent.souls import SoulLoader, inject_soul
    
    loader = SoulLoader()
    soul = loader.load("default")
    
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        prompt = inject_soul(soul)
        assert len(prompt) > 0
    
    duration = time.perf_counter() - start
    
    return {
        "iterations": iterations,
        "ops_per_sec": iterations / duration,
        "avg_prompt_chars": len(prompt)
    }


run_test("Soul 注入 (1,000次)", test_soul_inject)


# ============================================================
# 9. 内存压力测试
# ============================================================
print("\n【9. 内存压力测试】")
print("-" * 70)


def test_memory_pressure():
    """内存压力测试"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    gc.collect()
    mem_before = process.memory_info().rss / 1024 / 1024
    
    from taiji_agent import TaijiAgent, AgentConfig
    from taiji_agent import WFGYVerifier, HallucinationDetector
    from taiji_agent import SessionMemory, ToolRegistry
    
    agents = []
    verifiers = []
    memories = []
    registries = []
    
    for i in range(50):
        agents.append(TaijiAgent(config=AgentConfig()))
        verifiers.append(WFGYVerifier())
        memories.append(SessionMemory())
        registries.append(ToolRegistry())
    
    gc.collect()
    mem_after = process.memory_info().rss / 1024 / 1024
    mem_increase = mem_after - mem_before
    
    del agents, verifiers, memories, registries
    gc.collect()
    
    return {
        "mem_before_mb": mem_before,
        "mem_after_mb": mem_after,
        "mem_increase_mb": mem_increase
    }


run_test("内存压力测试 (50实例)", test_memory_pressure)


# ============================================================
# 10. 错误处理测试
# ============================================================
print("\n【10. 错误处理测试】")
print("-" * 70)


def test_error_invalid_provider():
    """测试无效 Provider"""
    from taiji_agent import TaijiAgent, AgentConfig
    
    try:
        agent = TaijiAgent(config=AgentConfig(provider="invalid_provider"))
        agent._init_provider()
        return {"error_caught": False}
    except ValueError:
        return {"error_caught": True}


run_test("无效 Provider 错误处理", test_error_invalid_provider)


def test_error_missing_tool():
    """测试缺失工具"""
    from taiji_agent.tools import ToolRegistry
    
    registry = ToolRegistry()
    
    class MockToolCall:
        name = "nonexistent_tool"
        arguments = {}
    
    result = asyncio.run(registry.execute(MockToolCall()))
    
    return {"error_caught": not result.success}


run_test("缺失工具错误处理", test_error_missing_tool)


def test_error_empty_content():
    """测试空内容"""
    from taiji_agent import WFGYVerifier, HallucinationDetector
    
    verifier = WFGYVerifier()
    detector = HallucinationDetector()
    
    passed = verifier.verify("")
    risk = detector.detect("")
    
    return {"passed": passed, "risk": risk}


run_test("空内容处理", test_error_empty_content)


# ============================================================
# 测试报告
# ============================================================
print()
print("=" * 70)
print("压力测试报告")
print("=" * 70)

total = len(results)
passed = sum(1 for r in results if r.passed)
failed = total - passed
total_duration = sum(r.duration for r in results)

print(f"\n总测试数: {total}")
print(f"通过: {passed} ({passed/total*100:.1f}%)")
print(f"失败: {failed} ({failed/total*100:.1f}%)")
print(f"总耗时: {total_duration:.2f}s")
print()

if failed > 0:
    print("失败测试:")
    for r in results:
        if not r.passed:
            print(f"  - {r.name}: {r.error}")
    print()

print("性能统计:")
print("-" * 70)

# 按性能分类
fast_tests = [r for r in results if r.duration < 0.01 and r.passed]
medium_tests = [r for r in results if 0.01 <= r.duration < 0.1 and r.passed]
slow_tests = [r for r in results if r.duration >= 0.1 and r.passed]

print(f"极速 (<10ms):   {len(fast_tests)} 个")
print(f"快速 (10-100ms): {len(medium_tests)} 个")
print(f"正常 (>100ms):   {len(slow_tests)} 个")
print()

print("详细结果:")
print("-" * 70)
for r in sorted(results, key=lambda x: x.duration):
    status = "✅" if r.passed else "❌"
    print(f"{status} {r.name:45s} {r.duration*1000:8.2f}ms")

print()
print("=" * 70)

if failed == 0:
    print("🎉 所有测试通过! OpenTaiji 2.0 压力测试完成!")
else:
    print(f"⚠️  {failed} 个测试失败，请检查错误日志")
    
print("=" * 70)
