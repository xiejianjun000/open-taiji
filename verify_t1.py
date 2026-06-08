"""
T1: TAIJI-AGENT 本地启动验证脚本

验证项:
1. 依赖安装验证 - 所有模块可正常导入
2. Agent 实例化验证 - TaijiAgent 可正常创建
3. Agent Loop 验证 - 使用 MockProvider 完成 请求→推理→返回结果 全流程
4. 事件总线验证 - Agent Loop 事件正常触发
5. WFGY 防幻觉验证 - Taiji Verify 正常工作
6. 工具注册验证 - 内置工具可正常注册和执行

验收标准：单个 Agent 能接收请求→推理→返回结果
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Any

# ============================================================
# 验证1: 依赖安装验证
# ============================================================
def verify_dependencies():
    """验证所有核心模块可正常导入"""
    print("=" * 60)
    print("验证1: 依赖安装验证")
    print("=" * 60)

    modules_to_check = [
        ("taiji_agent", "主模块"),
        ("taiji_agent.agent.engine", "Agent 引擎"),
        ("taiji_agent.providers.base", "LLM Provider 基类"),
        ("taiji_agent.providers.openai", "OpenAI Provider"),
        ("taiji_agent.providers.anthropic", "Anthropic Provider"),
        ("taiji_agent.providers.chinese.qwen", "Qwen Provider"),
        ("taiji_agent.providers.chinese.glm", "GLM Provider"),
        ("taiji_agent.providers.chinese.kimi", "Kimi Provider"),
        ("taiji_agent.tools.registry", "工具注册表"),
        ("taiji_agent.wfgy.verifier", "WFGY 防幻觉验证器"),
        ("taiji_agent.events.bus", "事件总线"),
        ("taiji_agent.memory.session", "会话记忆"),
        ("taiji_agent.souls.loader", "Soul 加载器"),
    ]

    results = []
    for module_name, desc in modules_to_check:
        try:
            __import__(module_name)
            results.append((module_name, desc, "OK", ""))
            print(f"  [OK] {desc} ({module_name})")
        except Exception as e:
            results.append((module_name, desc, "FAIL", str(e)))
            print(f"  [FAIL] {desc} ({module_name}): {e}")

    passed = sum(1 for r in results if r[2] == "OK")
    total = len(results)
    print(f"\n  结果: {passed}/{total} 模块导入成功\n")
    return passed == total


# ============================================================
# 验证2: Agent 实例化验证
# ============================================================
def verify_agent_instantiation():
    """验证 TaijiAgent 可正常实例化"""
    print("=" * 60)
    print("验证2: Agent 实例化验证")
    print("=" * 60)

    try:
        from taiji_agent.agent.engine import TaijiAgent, AgentConfig, TaskStatus, TaskResult

        # 使用 MockProvider 避免需要真实 API Key
        config = AgentConfig(
            provider="openai",
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:9999/v1",
            taiji_verify_enabled=True,
            max_iterations=5,
        )

        # 注入 MockProvider
        agent = TaijiAgent(config=config, provider=MockProvider())

        print(f"  [OK] TaijiAgent 实例化成功")
        print(f"  [OK] 配置: provider={config.provider}, model={config.model}")
        print(f"  [OK] WFGY 验证: {'启用' if config.taiji_verify_enabled else '禁用'}")
        print(f"  [OK] 事件总线: {type(agent.event_bus).__name__}")
        print(f"  [OK] 工具注册: {len(agent.tools.list_tools())} 个内置工具")
        print(f"  [OK] 记忆系统: {type(agent.memory).__name__}")
        print(f"  [OK] Soul 加载: {type(agent.soul_loader).__name__}")

        # 验证 TaskStatus 枚举
        statuses = [s.value for s in TaskStatus]
        print(f"  [OK] 任务状态: {statuses}")

        return True, agent
    except Exception as e:
        print(f"  [FAIL] Agent 实例化失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


# ============================================================
# MockProvider - 模拟 LLM 提供商
# ============================================================
class MockProvider:
    """模拟 LLM 提供商，用于本地验证 Agent Loop"""

    def __init__(self, response_content: str = "这是一个模拟响应。根据分析，生态环境保护是当前的重要任务。"):
        self.api_key = "mock-key"
        self.model = "mock-model"
        self.base_url = "mock://localhost"
        self.response_content = response_content
        self.call_count = 0

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs,
    ):
        """模拟聊天响应"""
        from taiji_agent.providers.base import LLMResponse

        self.call_count += 1

        # 提取用户请求内容，模拟推理过程
        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")

        # 模拟推理结果
        reasoning = f"基于对「{user_msg[:30]}...」的分析，"
        content = f"{reasoning}{self.response_content}"

        return LLMResponse(
            content=content,
            tool_calls=None,
            usage={"input_tokens": 100, "output_tokens": 50},
            model="mock-model",
            raw=None,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
        """模拟流式聊天"""
        for char in self.response_content:
            yield char

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        return len(text) // 4


# ============================================================
# 验证3: Agent Loop 验证 (核心验收项)
# ============================================================
async def verify_agent_loop():
    """验证 Agent Loop: 请求→推理→返回结果"""
    print("=" * 60)
    print("验证3: Agent Loop 验证 (核心验收项)")
    print("=" * 60)

    try:
        from taiji_agent.agent.engine import TaijiAgent, AgentConfig, TaskStatus

        config = AgentConfig(
            provider="openai",
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:9999/v1",
            taiji_verify_enabled=True,
            taiji_verify_threshold=0.7,
            max_iterations=5,
            stream=False,
        )

        mock_provider = MockProvider(
            response_content="根据生态环境监测数据分析，该区域空气质量指数(AQI)为65，"
            "属于良级别。PM2.5浓度为35μg/m³，符合国家二级标准。"
            "建议继续加强污染源管控，持续改善区域环境质量。[来源: 生态环境部2024年报]"
        )

        agent = TaijiAgent(config=config, provider=mock_provider)

        # 记录事件
        events_received = []

        def event_handler(event):
            events_received.append(event.name)
            return None

        agent.event_bus.on("agent:start", event_handler)
        agent.event_bus.on("agent:end", event_handler)
        agent.event_bus.on("llm:request", event_handler)
        agent.event_bus.on("llm:response", event_handler)
        agent.event_bus.on("loop:start", event_handler)
        agent.event_bus.on("prompt:assemble", event_handler)

        # 执行 Agent Loop
        print("\n  发送请求: '请分析当前区域生态环境状况'")
        start_time = time.time()
        result = await agent.run("请分析当前区域生态环境状况")
        elapsed = time.time() - start_time

        # 验证结果
        print(f"\n  [验证] 任务状态: {result.status.value}")
        print(f"  [验证] 响应内容: {result.content[:100]}..." if result.content else "  [验证] 响应内容: None")
        print(f"  [验证] 迭代次数: {result.iterations}")
        print(f"  [验证] 使用工具: {result.tools_used}")
        print(f"  [验证] 幻觉风险: {result.hallucination_risk:.2f}")
        print(f"  [验证] 耗时: {elapsed:.3f}秒")
        print(f"  [验证] 接收事件: {events_received}")

        # 验收判断
        success = True
        if result.status != TaskStatus.COMPLETED:
            print(f"\n  [FAIL] 任务未完成，状态: {result.status.value}")
            success = False
        if not result.content:
            print(f"\n  [FAIL] 返回内容为空")
            success = False
        if "agent:start" not in events_received:
            print(f"\n  [FAIL] agent:start 事件未触发")
            success = False
        if "llm:request" not in events_received:
            print(f"\n  [FAIL] llm:request 事件未触发")
            success = False
        if "llm:response" not in events_received:
            print(f"\n  [FAIL] llm:response 事件未触发")
            success = False

        if success:
            print(f"\n  [OK] Agent Loop 验证通过！单个 Agent 能接收请求→推理→返回结果")
        else:
            print(f"\n  [FAIL] Agent Loop 验证未通过")

        return success

    except Exception as e:
        print(f"  [FAIL] Agent Loop 验证异常: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 验证4: 事件总线验证
# ============================================================
async def verify_event_bus():
    """验证事件总线正常工作"""
    print("=" * 60)
    print("验证4: 事件总线验证")
    print("=" * 60)

    try:
        from taiji_agent.events.bus import EventBus, Events

        bus = EventBus()
        captured_events = []

        def handler(event):
            captured_events.append(event)
            return None

        # 订阅预定义事件
        event_names = [
            Events.AGENT_START,
            Events.AGENT_END,
            Events.LLM_REQUEST,
            Events.LLM_RESPONSE,
            Events.TOOL_REQUEST,
            Events.TOOL_RESULT,
        ]

        for name in event_names:
            bus.on(name, handler)

        # 发出事件
        bus.emit_sync(Events.AGENT_START, {"task": "test"})
        bus.emit_sync(Events.LLM_REQUEST, {"iteration": 0})
        bus.emit_sync(Events.LLM_RESPONSE, {"has_content": True})

        print(f"  [OK] 订阅事件: {len(event_names)} 个")
        print(f"  [OK] 捕获事件: {len(captured_events)} 个")
        print(f"  [OK] 事件名称: {[e.name for e in captured_events]}")

        # 验证事件历史
        history = bus.get_history(limit=10)
        print(f"  [OK] 事件历史: {len(history)} 条")

        return len(captured_events) >= 3

    except Exception as e:
        print(f"  [FAIL] 事件总线验证失败: {e}")
        return False


# ============================================================
# 验证5: WFGY 防幻觉验证
# ============================================================
def verify_wfgy():
    """验证 WFGY 防幻觉系统正常工作"""
    print("=" * 60)
    print("验证5: WFGY 防幻觉验证")
    print("=" * 60)

    try:
        from taiji_agent.wfgy.verifier import (
            TaijiVerifier,
            HallucinationDetector,
            SelfConsistencyChecker,
            SourceTracer,
        )

        # 5.1 TaijiVerifier
        verifier = TaijiVerifier()
        verifier.add_rule(
            pattern=r"绝对不可能",
            expected=False,
            name="no_absolute_denial",
        )
        verifier.add_knowledge("PM2.5", "细颗粒物，空气动力学当量直径≤2.5μm", source="GB 3095-2012")

        test_content_good = "该区域PM2.5浓度为35μg/m³，符合国家标准。"
        test_content_bad = "这绝对不可能发生，PM2.5永远不会超标。"

        result_good = verifier.verify(test_content_good)
        result_bad = verifier.verify(test_content_bad)

        print(f"  [OK] TaijiVerifier 正常内容: {'通过' if result_good else '未通过'}")
        print(f"  [OK] TaijiVerifier 违规内容: {'通过' if result_bad else '未通过(预期)'}")

        # 5.2 HallucinationDetector
        detector = HallucinationDetector()
        risk_low = detector.detect("根据生态环境部2024年报，AQI为65[来源:生态环境部]")
        risk_high = detector.detect("大概也许是据我所知通常情况下可能是这样")

        print(f"  [OK] 幻觉检测(低风险): {risk_low:.2f}")
        print(f"  [OK] 幻觉检测(高风险): {risk_high:.2f}")

        # 5.3 SelfConsistencyChecker
        checker = SelfConsistencyChecker()
        checker.add_sample("生态环境质量总体良好")
        checker.add_sample("生态环境质量总体良好")
        checker.add_sample("生态环境质量较差")
        is_consistent, score = checker.check()

        print(f"  [OK] 自一致性检查: consistent={is_consistent}, score={score:.2f}")

        # 5.4 SourceTracer
        tracer = SourceTracer()
        tracer.add_source("PM2.5标准限值为35μg/m³", source_url="https://example.com/gb3095", source_title="GB 3095-2012")
        sources = tracer.trace("PM2.5标准限值")
        coverage = tracer.get_coverage("PM2.5标准限值")

        print(f"  [OK] 知识溯源: 找到 {len(sources)} 条来源, 覆盖率={coverage:.2f}")

        all_pass = result_good and not result_bad and risk_high > risk_low
        return all_pass

    except Exception as e:
        print(f"  [FAIL] WFGY 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 验证6: 工具注册验证
# ============================================================
def verify_tools():
    """验证内置工具可正常注册和执行"""
    print("=" * 60)
    print("验证6: 工具注册验证")
    print("=" * 60)

    try:
        from taiji_agent.tools.registry import ToolRegistry

        registry = ToolRegistry()
        tools = registry.list_tools()

        print(f"  [OK] 已注册工具数量: {len(tools)}")
        print(f"  [OK] 工具列表: {tools}")

        # 验证关键工具存在
        required_tools = ["file_read", "file_write", "file_list", "shell", "web_search", "git_status"]
        missing = [t for t in required_tools if t not in tools]
        if missing:
            print(f"  [FAIL] 缺少工具: {missing}")
            return False

        print(f"  [OK] 关键工具验证通过: {required_tools}")

        # 验证工具 Schema
        schemas = registry.get_schemas()
        print(f"  [OK] 工具 Schema 数量: {len(schemas)}")

        # 验证同步工具可执行 (file_list)
        result = registry._file_list(path=".")
        print(f"  [OK] file_list 执行成功, 内容长度={len(result)}")

        return True

    except Exception as e:
        print(f"  [FAIL] 工具注册验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 验证7: 流式运行验证
# ============================================================
async def verify_stream_run():
    """验证流式 Agent 运行"""
    print("=" * 60)
    print("验证7: 流式运行验证")
    print("=" * 60)

    try:
        from taiji_agent.agent.engine import TaijiAgent, AgentConfig

        config = AgentConfig(
            provider="openai",
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:9999/v1",
            taiji_verify_enabled=True,
            stream=True,
        )

        mock_provider = MockProvider(response_content="流式响应：生态环境保护需要全社会共同参与。")

        agent = TaijiAgent(config=config, provider=mock_provider)

        chunks = []
        async for chunk in agent.stream_run("请简述生态保护措施"):
            chunks.append(chunk)

        full_response = "".join(chunks)
        print(f"  [OK] 流式输出块数: {len(chunks)}")
        print(f"  [OK] 完整响应: {full_response[:80]}...")

        return len(chunks) > 0 and len(full_response) > 0

    except Exception as e:
        print(f"  [FAIL] 流式运行验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 主验证流程
# ============================================================
async def main():
    """运行所有验证项"""
    print("\n" + "=" * 60)
    print("  TAIJI-AGENT 2.0.0 本地启动验证")
    print("  EcoMind OS Phase 1A - T1 Task")
    print("=" * 60 + "\n")

    results = {}

    # 验证1: 依赖安装
    results["1.依赖安装"] = verify_dependencies()

    # 验证2: Agent 实例化
    inst_result, agent = verify_agent_instantiation()
    results["2.Agent实例化"] = inst_result

    # 验证3: Agent Loop (核心)
    results["3.Agent Loop"] = await verify_agent_loop()

    # 验证4: 事件总线
    results["4.事件总线"] = await verify_event_bus()

    # 验证5: WFGY 防幻觉
    results["5.WFGY防幻觉"] = verify_wfgy()

    # 验证6: 工具注册
    results["6.工具注册"] = verify_tools()

    # 验证7: 流式运行
    results["7.流式运行"] = await verify_stream_run()

    # 汇总
    print("\n" + "=" * 60)
    print("  验证结果汇总")
    print("=" * 60)

    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        icon = "✓" if passed else "✗"
        print(f"  [{icon}] {name}: {status}")
        if not passed:
            all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("  验收结论: ALL PASS")
        print("  T1 验收标准: 单个 Agent 能接收请求→推理→返回结果 ✓")
    else:
        print("  验收结论: HAS FAILURES")
        failed = [name for name, passed in results.items() if not passed]
        print(f"  失败项: {failed}")
    print("=" * 60 + "\n")

    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
