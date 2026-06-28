"""
Taiji Agent Engine - 融合 Hermes Agent + Harness + Taiji Verify
核心 Agent Loop 实现
"""

import logging
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
import os
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from taiji_agent.events.bus import EventBus
from taiji_agent.memory.session import SessionMemory
from taiji_agent.providers.base import LLMProvider
from taiji_agent.souls.loader import SoulLoader, inject_soul
from taiji_agent.tools.registry import ToolRegistry
from taiji_agent.taiji_verify import HallucinationDetector, SelfConsistencyChecker, WFGYVerifier, TaijiVerifyPro
from taiji_agent.context.compressor import ContextCompressor, get_model_context_length

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class Message(BaseModel):
    role: str
    content: str
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]
    id: str


class ToolResult(BaseModel):
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class AgentConfig:
    provider: str = "anthropic"
    model: str = "deepseek-v4-pro"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    soul: str = "default"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_iterations: int = 25
    verify_enabled: bool = True
    verify_threshold: float = 0.5
    taiji_verify_enabled: bool = False  # 太极验证引擎（升级版Taiji Verify）
    taiji_verify_block_on_danger: bool = True  # DANGER区域自动拦截
    self_consistency_samples: int = 3
    stream: bool = True
    workdir: str = "."
    verbose: bool = False
    # Enhanced features
    enable_sandbox: bool = True
    enable_failover: bool = True
    fallback_providers: list[str] = field(default_factory=list)  # e.g. ["openai", "qwen"]
    sandbox_config: Optional[dict] = None
    # 被动模式：只回答问题，不主动调用工具（默认关闭——继承Hermes主动执行风格）
    passive_mode: bool = False

    # ── TaijiVerifyPro v2.0 配置（业界领先防幻觉系统）──
    taijiverifypro_enabled: bool = True       # 启用 TaijiVerifyPro（推荐）
    taijiverifypro_threshold: float = 0.7     # 风险阈值（>=此值触发警告）
    taijiverifypro_auto_block: bool = False   # 自动拦截关闭（避免误杀正常回复）
    taijiverifypro_show_report: bool = True   # 在回复中显示检测报告
    taijiverifypenetration_enabled: bool = True  # 启用阈值穿透机制


@dataclass
class TaskResult:
    status: TaskStatus
    content: Optional[str] = None
    error: Optional[str] = None
    iterations: int = 0
    tools_used: list[str] = field(default_factory=list)
    verify_blocked: int = 0
    hallucination_risk: float = 0.0


class TaijiAgent:
    """
    太极 Agent - 融合三大框架精华

    特性:
    - Agent Loop 基于 cgast/harness (~350行核心)
    - Taiji Verify 验证引擎
    - 工具系统来自 Hermes Agent
    - Soul 人格系统来自 Harness
    - 记忆系统来自 Hermes Honcho
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        provider: Optional[LLMProvider] = None,
    ):
        self.config = config or AgentConfig()
        self.provider = provider
        self.event_bus = EventBus()

        # 核心组件初始化
        self.soul_loader = SoulLoader()
        self.verifier = WFGYVerifier()
        self.hallucination_detector = HallucinationDetector()
        self.consistency_checker = SelfConsistencyChecker()

        # ── TaijiVerifyPro v2.0 初始化（业界领先防幻觉系统）──
        self.taijiverifypro = None
        if self.config.taijiverifypro_enabled:
            try:
                self.taijiverifypro = TaijiVerifyPro(
                    auto_threshold_penetration=self.config.taijiverifypenetration_enabled,
                )
                logger.info("✅ TaijiVerifyPro v2.0 已启用（业界领先防幻觉系统）")
            except Exception as e:
                logger.warning(f"⚠️ TaijiVerifyPro 初始化失败，回退到基础验证: {e}")
                self.config.taijiverifypro_enabled = False

        # 增强：太极验证引擎（升级版Taiji Verify）
        self.taiji_verify = None
        if self.config.taiji_verify_enabled:
            from taiji_agent.taiji_verify.engine import TaijiVerifyEngine, VerificationRequest
            self.taiji_verify = TaijiVerifyEngine(
                embedding_dim=768,
                enable_failure_modes=True,
                enable_stability_check=True,
            )
        self.memory = SessionMemory()
        self.tools = ToolRegistry()

        # 增强：安全沙箱
        self.sandbox = None
        if self.config.enable_sandbox:
            from taiji_agent.security.sandbox import SandboxConfig
            try:
                sb_config = SandboxConfig(**self.config.sandbox_config) if self.config.sandbox_config else SandboxConfig()
            except (TypeError, AttributeError):
                sb_config = SandboxConfig()
            self.sandbox = sb_config  # 沙箱配置可供工具使用

        # 增强：Provider 故障转移
        self.failover_router = None
        if self.config.enable_failover and self.config.fallback_providers:
            from taiji_agent.providers.failover import ProviderRouter, ProviderEndpoint
            self.failover_router = ProviderRouter()
            for fp in self.config.fallback_providers:
                self.failover_router.add_endpoint(ProviderEndpoint(
                    name=f"{fp}-fallback",
                    provider=fp,
                    model=self.config.model,
                    priority=2,
                ))

        # 状态
        self.messages: list[Message] = []
        self.iteration_count = 0

        # ── 上下文压缩器（模型感知，自动触发）──
        ctx_len = get_model_context_length(self.config.model)
        self.compressor = ContextCompressor(context_length=ctx_len)
        self._context_overflow_count = 0  # 同一轮次 overflow 计数

        # 初始化提供商
        if self.provider is None:
            self._init_provider()

    def _init_provider(self):
        """初始化 LLM 提供商"""
        if self.config.provider == "anthropic":
            from taiji_agent.providers.anthropic import AnthropicProvider

            self.provider = AnthropicProvider(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
            )
        elif self.config.provider == "openai":
            from taiji_agent.providers.openai import OpenAIProvider

            self.provider = OpenAIProvider(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
            )
        elif self.config.provider == "qwen":
            from taiji_agent.providers.chinese.qwen import QwenProvider

            self.provider = QwenProvider(
                api_key=self.config.api_key,
                model=self.config.model,
            )
        elif self.config.provider == "glm":
            from taiji_agent.providers.chinese.glm import GLMProvider

            self.provider = GLMProvider(
                api_key=self.config.api_key,
                model=self.config.model,
            )
        elif self.config.provider == "kimi":
            from taiji_agent.providers.chinese.kimi import KimiProvider

            self.provider = KimiProvider(
                api_key=self.config.api_key,
                model=self.config.model,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    async def run(self, task: str, system_message: Optional[str] = None) -> TaskResult:
        """
        执行任务 - 太极 Agent Loop

        流程:
        1. Assemble prompt (soul + skills + history)
        2. Taiji Verify 预处理验证
        3. LLM 请求
        4. 解析响应
        5. Taiji Verify 后处理验证
        6. 工具执行
        7. 状态更新
        8. 重复直到完成
        """
        self.event_bus.emit_sync("agent:start", {"task": task})

        # 初始化消息
        self.messages = []
        self.iteration_count = 0

        # 系统提示
        system_prompt = self._build_system_prompt()
        if system_message:
            system_prompt += f"\n\n{system_message}"

        self.messages.append(Message(role="system", content=system_prompt))
        self.messages.append(Message(role="user", content=task))

        # Agent Loop
        while self.iteration_count < self.config.max_iterations:
            try:
                # 1. Assemble prompt
                self.event_bus.emit_sync("prompt:assemble", {"iteration": self.iteration_count})
                self._assemble_prompt()

                # 2. Emit loop start event
                self.event_bus.emit_sync(
                    "loop:start",
                    {
                        "iteration": self.iteration_count,
                        "messages_count": len(self.messages),
                    },
                )

                # 3. LLM 请求
                self.event_bus.emit_sync("llm:request", {"iteration": self.iteration_count})

                # ── 自动上下文压缩 ──
                if self.iteration_count > 0:
                    self._auto_compress(reason="pre-LLM budget check (run)")

                provider = self.provider
                if provider is None:
                    raise ValueError("LLM provider not initialized")
                response = await provider.chat(
                    messages=[msg.model_dump() for msg in self.messages],
                    tools=self.tools.get_schemas() if self.tools.has_tools() else None,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    stream=self.config.stream,
                )

                self.event_bus.emit_sync(
                    "llm:response",
                    {
                        "has_content": bool(response.content),
                        "has_tool_calls": bool(response.tool_calls),
                    },
                )

                # 4. Taiji Verify 验证 (后处理)
                if self.config.verify_enabled and response.content:
                    response = await self._verify_and_annotate(response)

                # 5. 解析响应
                if response.tool_calls:
                    # 工具调用 - 统一处理 dict 和对象
                    for tool_call in response.tool_calls:
                        if isinstance(tool_call, dict):
                            tc_name = tool_call.get("name", "")
                            tc_args = tool_call.get("arguments", {})
                            tc_id = tool_call.get("id", "")
                        else:
                            tc_name = tool_call.name
                            tc_args = tool_call.arguments if hasattr(tool_call, "arguments") else {}
                            tc_id = tool_call.id if hasattr(tool_call, "id") else ""

                        self.event_bus.emit_sync(
                            "tool:request",
                            {
                                "name": tc_name,
                                "arguments": tc_args,
                            },
                        )

                        # 执行工具
                        result = await self.tools.execute(tool_call)

                        # 构建工具调用消息
                        self.messages.append(
                            Message(
                                role="assistant",
                                content=response.content or "",
                                tool_calls=[
                                    {"name": tc_name, "arguments": tc_args, "id": tc_id}
                                ],
                            )
                        )
                        # 工具结果提示：失败时加入明确的失败标记
                        tool_content = result.content or ""
                        if not result.success:
                            tool_content = f"[TOOL_FAILED] {tool_content or result.error or '未知错误'}"
                            logger.warning(
                                "Tool %s failed (iteration %d): %s",
                                tc_name, self.iteration_count, result.error or tool_content[:200]
                            )
                        self.messages.append(
                            Message(
                                role="tool",
                                content=tool_content,
                                tool_call_id=tc_id,
                            )
                        )

                        self.event_bus.emit_sync(
                            "tool:result",
                            {
                                "name": tc_name,
                                "success": not (hasattr(result, "is_error") and result.is_error),
                            },
                        )

                    self.iteration_count += 1
                else:
                    # 最终响应
                    self.messages.append(
                        Message(
                            role="assistant",
                            content=response.content or "",
                        )
                    )

                    # 保存到记忆
                    self.memory.save_session([msg.model_dump() for msg in self.messages])

                    self.event_bus.emit_sync(
                        "agent:end",
                        {
                            "status": "completed",
                            "iterations": self.iteration_count,
                        },
                    )

                    return TaskResult(
                        status=TaskStatus.COMPLETED,
                        content=response.content,
                        iterations=self.iteration_count,
                        tools_used=self.tools.get_used_tools(),
                    )

            except Exception as e:
                err_str = str(e).lower()
                # ── 上下文超限：自动压缩后重试 ──
                if ('context length' in err_str or 'maximum context' in err_str
                        or 'reduce the length' in err_str):
                    self._context_overflow_count += 1
                    if self._context_overflow_count <= 2:
                        logger.warning(
                            "Context overflow #%d at iter %d (run), aggressive compress + retry",
                            self._context_overflow_count, self.iteration_count,
                        )
                        self._auto_compress(aggressive=True,
                                            reason=f"overflow #{self._context_overflow_count}")
                        self.event_bus.emit_sync("error", {
                            "error": f"context_overflow_#{self._context_overflow_count}",
                            "iteration": self.iteration_count,
                        })
                        continue
                    else:
                        logger.error("Context overflow retry exhausted (run)")
                        break

                logger.error(f"Error in iteration {self.iteration_count}: {e}", exc_info=True)
                self.event_bus.emit_sync("error", {"error": str(e), "iteration": self.iteration_count})
                self.iteration_count += 1
                # 继续循环，让 Agent 基于错误信息重试或重新规划

        # 达到最大迭代次数
        self.event_bus.emit_sync(
            "agent:end",
            {
                "status": "max_iterations",
                "iterations": self.iteration_count,
            },
        )

        return TaskResult(
            status=TaskStatus.ABORTED,
            error="达到最大迭代次数",
            iterations=self.iteration_count,
        )

    async def stream_run(self, task: str, system_message: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        流式执行任务 — Hermes 风格 Agent Loop

        产出:
        - 普通文本 (流式输出，直接给用户看)
        - __TOOL_CALL__:tool_name;args_json (内部协议，CLI 层渲染)
        - __TOOL_RESULT__:result_text (内部协议，CLI 层渲染)
        """
        self.event_bus.emit_sync("agent:start", {"task": task, "stream": True})

        # 首次或重置时构建系统提示
        if not self.messages:
            system_prompt = self._build_system_prompt()
            if system_message:
                system_prompt += f"\n\n{system_message}"
            self.messages.append(Message(role="system", content=system_prompt))
            self.messages.append(Message(role="user", content=task))
        else:
            self.messages.append(Message(role="user", content=task))

        # 行动承诺检测关键词
        ACTION_PROMISE_WORDS = [
            "让我", "我来", "访问", "拉取", "克隆", "搜索", "查看",
            "下载", "尝试", "打开", "浏览", "获取", "读取", "执行",
            "运行", "安装", "创建", "写入", "保存", "发送",
        ]

        self.iteration_count = 0
        consecutive_failures = 0  # 连续工具失败计数
        while self.iteration_count < self.config.max_iterations:
            try:
                # 连续失败保护：3 次后强制终止
                if consecutive_failures >= 3:
                    yield "\n[已自动停止：连续 3 次工具调用失败，这条路走不通]"
                    self.messages.append(Message(
                        role="assistant",
                        content="我尝试了多种方式但都失败了。坦率地说，这个任务我目前无法完成。建议换个思路或者检查网络/权限配置。"
                    ))
                    break

                response_text_parts: list[str] = []
                tool_calls_to_execute: list[dict] = []

                provider = self.provider
                if provider is None:
                    raise ValueError("LLM provider not initialized")

                # ── 自动上下文压缩：超过 75% 阈值时压缩历史消息 ──
                if self.iteration_count > 0:
                    self._auto_compress(reason="pre-LLM budget check")

                # 单次流式调用：同时获取文本和工具调用
                async for chunk in provider.stream_chat(
                    messages=[msg.model_dump() for msg in self.messages],
                    tools=self.tools.get_schemas() if self.tools.has_tools() else None,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                ):
                    if isinstance(chunk, dict) and chunk.get("_tool_call"):
                        # 完整的工具调用（provider 在 tool_use 块结束时产出）
                        tc = chunk["_tool_call"]
                        tool_calls_to_execute.append(tc)
                        yield f"__TOOL_CALL__:{tc['name']};{json.dumps(tc.get('arguments', {}), ensure_ascii=False)}"
                    elif isinstance(chunk, str):
                        # 普通文本 — 无条件累积和产出
                        response_text_parts.append(chunk)
                        yield chunk

                response_text = "".join(response_text_parts).strip()

                # 有工具调用 → 执行后继续循环
                if tool_calls_to_execute:
                    tool_calls_obj = []
                    tool_results = []
                    all_failed = True  # 本轮是否全部失败

                    for tc in tool_calls_to_execute:
                        name = tc["name"]
                        args = tc.get("arguments", {})

                        class ToolCallObj:
                            def __init__(self, n, a, tid):
                                self.name = n
                                self.arguments = a
                                self.id = tid or f"tc_{hash(name + str(args))}"

                        tco = ToolCallObj(name, args, tc.get("id"))
                        tool_calls_obj.append(tco)

                        result = await self.tools.execute(tco)
                        result_text = result.content if hasattr(result, 'content') else str(result)
                        is_error = (
                            getattr(result, 'success', True) is False
                            or (result_text and result_text.startswith('[工具错误]'))
                            or (result_text and result_text.startswith('[搜索失败]'))
                            or (result_text and '404' in result_text[:200])
                            or (result_text and 'Client error' in result_text[:200])
                        )
                        if not is_error:
                            all_failed = False
                        tool_results.append(result)
                        yield f"__TOOL_RESULT__:{result_text[:500]}"

                    # 更新连续失败计数
                    if all_failed:
                        consecutive_failures += 1
                        if consecutive_failures == 2:
                            # 警告 LLM：再失败就终止
                            yield "\n[⚠ 连续 2 次工具失败，请换思路或承认无法完成]"
                    else:
                        consecutive_failures = 0

                    # 记录到消息历史
                    self.messages.append(Message(
                        role="assistant",
                        content=response_text or "",
                        tool_calls=[{"name": tc.name, "arguments": tc.arguments, "id": tc.id} for tc in tool_calls_obj],
                    ))
                    for tc, result in zip(tool_calls_obj, tool_results):
                        result_text = result.content if hasattr(result, 'content') else str(result)
                        self.messages.append(Message(
                            role="tool",
                            content=result_text,
                            tool_call_id=tc.id,
                        ))

                    self.iteration_count += 1
                    continue  # 继续循环，LLM 基于工具结果生成下一轮

                # 无工具调用，有文本 → 可能是最终回复，也可能需要继续
                if response_text:
                    # 检查是否含有行动承诺但未调工具（空转检测）
                    # 被动模式下不强制调用工具
                    has_promise = any(w in response_text for w in ACTION_PROMISE_WORDS)
                    if has_promise and self.iteration_count < self.config.max_iterations - 1 and not self.config.passive_mode:
                        # LLM 说了要做事但没调工具 → 追加指令让它动手
                        self.messages.append(Message(role="assistant", content=response_text))
                        self.messages.append(Message(
                            role="user",
                            content="请直接调用工具执行上述操作，不要只描述你打算做什么。如果需要访问网页，使用 web_extract 工具；如果需要搜索，使用 web_search 工具；如果需要执行命令，使用 shell 工具。"
                        ))
                        self.iteration_count += 1
                        yield "\n"  # 视觉分隔
                        continue

                    # 最终回复
                    if self.config.verify_enabled:
                        risk = self.hallucination_detector.detect(response_text)
                        if risk > (1 - self.config.verify_threshold):
                            yield f"[⚠️ 幻觉风险 {risk:.1%}]"

                    self.messages.append(Message(role="assistant", content=response_text))
                    self.iteration_count += 1
                    break

                # 无文本也无工具调用 → 异常情况，退出
                self.iteration_count += 1
                break

            except Exception as e:
                err_str = str(e).lower()
                # ── 上下文超限：自动压缩后重试（最多 2 次）──
                if ('context length' in err_str or 'maximum context' in err_str
                        or 'reduce the length' in err_str):
                    self._context_overflow_count += 1
                    if self._context_overflow_count <= 2:
                        logger.warning(
                            "Context overflow #%d at iter %d, aggressive compress + retry",
                            self._context_overflow_count, self.iteration_count,
                        )
                        compressed = self._auto_compress(
                            aggressive=True,
                            reason=f"overflow #{self._context_overflow_count}",
                        )
                        yield f"\n[⚠ 上下文超限 (#{self._context_overflow_count})，已自动压缩并重试...]\n"
                        consecutive_failures = 0
                        continue
                    else:
                        logger.error("Context overflow retry exhausted after %d attempts",
                                     self._context_overflow_count)
                        yield "\n[❌ 上下文持续超限，已放弃。请用 /new 新建会话。]\n"
                        break

                logger.error(f"Stream error in iteration {self.iteration_count}: {e}")
                yield f"[错误: {str(e)}]"
                break

    def _build_system_prompt(self) -> str:
        """构建系统提示 - 融合 Soul + 运行环境 + 跨会话记忆"""
        soul = self.soul_loader.load(self.config.soul)

        import os as _os
        import getpass as _getpass
        username = _getpass.getuser()
        homedir = _os.path.expanduser("~")
        desktop = _os.path.join(homedir, "Desktop")
        cwd = _os.getcwd()

        # 加载跨会话记忆
        memory_context = ""
        try:
            from taiji_agent.memory.session import SessionMemory
            mem = SessionMemory()
            # 用户画像
            profile = mem.get_peer_card("user")
            if profile.get("facts"):
                memory_context += "\n## 用户画像\n"
                for fact in profile["facts"]:
                    memory_context += f"- {fact}\n"
            # 最近的记忆条目
            recent_memories = []
            for key, entry in mem._memory.items():
                if isinstance(entry, dict) and entry.get("type") != "session":
                    recent_memories.append(f"- [{key}] {entry['value'][:200]}")
            if recent_memories:
                memory_context += "\n## 持久记忆\n"
                memory_context += "\n".join(recent_memories[-10:])
        except Exception:
            pass

        prompt_parts = [
            "# Taiji Agent",
            "",
            inject_soul(soul),
            "",
            "## 操作手册",
            "",
            "### 身份与称呼",
            "- 你是\"小佳\"，技术管理者，负责xiejianjun000仓库及所有关联项目",
            "- 私下对话称用户为\"军哥\"（最高权威）",
            "- 所有文档、代码、日志、外部通信中不出现\"军哥\"，使用\"管理员\"或\"董事长\"",
            "- 军哥说\"不要弄了\"/\"停下\"/\"暂停\" = 立即停止所有操作，不等收尾",
            "",
            "### 沟通铁律",
            "- 使用中文交流",
            "- 直接执行，不反复确认方向。收到明确任务立即行动，出错就改，不阻塞在确认环节",
            "- 教程式输出：解释每一步操作，让编码新手也能跟上",
            "- 自动化优先：一切手动步骤都是失败。脚本化、配置化、端到端。",
            "- 禁止空回复：不说\"明白了\"/\"收到\"/\"马上安排\"，直接动手产出",
            "- 军哥发\"???\"/\"什么情况???\"/\"你怎么回事\" = 严重警告，立刻停止讨论，直接动手",
            "",
            "### 紧急信号",
            "- 用户发\"???\" = 极端不满 → 停止一切解释，立刻产出实质结果",
            "- 用户发\"什么情况???\"/\"没反应\" = 链路断裂 → 立刻诊断并修复",
            "- 连续多个\"???\" = 信任崩塌 → 秒级响应，不容解释",
            "",
            "### Memory 交互规则",
            "- 保存持久化事实到memory：用户偏好、环境配置、工具特性、项目约定",
            "- 用户偏好和纠正 > 环境事实 > 流程知识",
            "- 用陈述句保存（\"项目使用pytest\"），不用祈使句（\"用pytest跑测试\"）",
            "- 不保存临时任务状态、PR号、commit SHA等7天内会变的信息",
            "",
            "### 桌面自动化边界",
            "- 截图、鼠标点击、键盘输入、窗口控制、剪贴板读写等操作属于特权操作",
            "- 无明确授权时绝对禁用",
            "- 即使有授权，不读剪贴板除非特别要求",
            "",
            "## 运行环境",
            f"- 当前用户: {username}",
            f"- 用户主目录: {homedir}",
            f"- 桌面路径: {desktop}",
            f"- 当前工作目录: {cwd}",
            "- 操作系统: macOS",
            "",
        ]

        if memory_context:
            prompt_parts.append(memory_context)
            prompt_parts.append("")

        prompt_parts.extend([
            "## 输出格式要求",
            "- 优先使用结构化输出（表格、列表、分段），让信息清晰易读",
            "- 可以适当使用 Markdown 格式增强可读性（标题、加粗、代码块等）",
            "- 回复简洁有力，但要确保信息完整不遗漏",
            "- 需要执行操作时直接调用工具，不要只描述计划",
            "",
            "## 行为准则",
            "- 所有陈述必须有事实依据，不确定时明确标注",
            "- 工具执行失败时尝试替代方案",
            "- 完成用户明确要求的任务后立即停止回复，不要自作主张扩展或追加建议",
        ])

        return "\n".join(prompt_parts)

    def _assemble_prompt(self) -> list[dict]:
        """组装提示"""
        return [msg.model_dump() for msg in self.messages]

    def _auto_compress(self, aggressive=False, reason=""):
        """自动压缩上下文 — 超过阈值时触发

        Args:
            aggressive: 激进模式（使用 50% 阈值，保留更少历史）
            reason: 触发原因（用于日志）
        Returns:
            bool: 是否执行了压缩
        """
        if len(self.messages) <= self.compressor.protect_first_n + self.compressor.protect_last_n:
            return False

        threshold = 0.5 if aggressive else 0.75
        if not self.compressor.needs_compression(self.messages, threshold):
            return False

        old_len = len(self.messages)
        est_before = self.compressor.estimate_total_tokens(self.messages)
        self.messages = self.compressor.compress_if_needed(self.messages, threshold)
        new_len = len(self.messages)
        est_after = self.compressor.estimate_total_tokens(self.messages)

        mode = "aggressive" if aggressive else "normal"
        logger.info(
            "Context auto-compressed (%s)%s: %d→%d msgs, ~%d→~%d tokens",
            mode, f" [{reason}]" if reason else "",
            old_len, new_len, est_before, est_after,
        )
        return True

    async def _verify_and_annotate(self, response) -> Any:
        """Taiji Verify 验证并注解（优先使用 TaijiVerifyPro v2.0）"""
        if not response.content:
            return response

        # ── 优先级1: TaijiVerifyPro v2.0（业界领先）──
        if self.taijiverifypro and self.config.taijiverifypro_enabled:
            return self._taijiverifypro_response(response)

        # ── 优先级2: 太极验证引擎（升级版Taiji Verify）──
        if self.taiji_verify:
            return self._taiji_verify_response(response)

        # ── 回退到基础验证（v1）──
        # 1. 符号层验证
        verify_passed = self.verifier.verify(response.content)

        # 2. 幻觉检测
        risk = self.hallucination_detector.detect(response.content)

        # 3. 如果风险高，添加警告
        if risk > (1 - self.config.verify_threshold):
            status = "通过" if verify_passed else "未通过"
            warning = f"\n\n[⚠️ 幻觉风险 {risk:.1%}，Taiji Verify 验证{status}]"
            response.content += warning

        return response

    def _taijiverifypro_response(self, response) -> Any:
        """
        使用 TaijiVerifyPro v2.0 进行业界领先的多层次防幻觉验证

        7层防御体系：
        Layer 1: 快速预检 (0.1ms)
        Layer 2: 符号层验证
        Layer 3: 事实核查（动态权重）
        Layer 4: 语义一致性
        Layer 5: 失败模式检测（16种）
        Layer 6: 向量流水线[可选]
        Layer 7: 综合判定（阈值穿透）
        """
        import time
        start_time = time.time()

        # 执行 TaijiVerifyPro 验证
        result = self.taijiverifypro.verify(response.content)

        processing_ms = int((time.time() - start_time) * 1000)

        # 记录验证结果到事件总线
        self.event_bus.emit_sync("taijiverifypro:result", {
            "risk_score": result.risk_score,
            "verdict": result.verdict.value,
            "mode": result.mode,
            "processing_ms": processing_ms,
            "critical_count": result.critical_count,
            "dimensions": [
                {"dimension": d.dimension, "score": d.score, "weight": d.weight}
                for d in result.dimensions
            ],
        })

        # ── 根据判定等级处理响应 ──

        # 🔴 BLOCK: 自动拦截高风险输出
        if result.verdict.value == "block" and self.config.taijiverifypro_auto_block:
            block_message = (
                f"\n\n{'='*60}\n"
                f"🚫 [TaijiVerifyPro 拦截] 防幻觉检测发现高风险内容\n"
                f"{'='*60}\n"
                f"⚠️  风险评分: {result.risk_score:.1%} (阈值: {self.config.taijiverifypro_threshold:.0%})\n"
                f"📊  判定等级: {result.verdict.value.upper()}\n"
                f"⏱️  检测耗时: {processing_ms}ms\n"
            )

            # 显示关键维度得分（前3个高风险维度）
            high_risk_dims = sorted(
                [d for d in result.dimensions if d.score >= 0.5],
                key=lambda x: x.score,
                reverse=True
            )[:3]

            if high_risk_dims:
                block_message += "\n🔍 高风险维度:\n"
                for dim in high_risk_dims:
                    icon = "🔴" if dim.score >= 0.8 else "🟠" if dim.score >= 0.7 else "🟡"
                    block_message += f"   {icon} {dim.dimension}: {dim.score:.1%}\n"
                    if dim.violations:
                        block_message += f"      ⚠ {dim.violations[0]}\n"

            # 显示失败模式
            if result.failure_modes:
                critical_fms = [fm for fm in result.failure_modes if fm.get("severity") == "critical"]
                if critical_fms:
                    block_message += f"\n💥 CRITICAL 失败模式 ({len(critical_fms)}个):\n"
                    for fm in critical_fms[:3]:
                        block_message += f"   [{fm['id']}] {fm['name_cn']} ({fm['confidence']:.0%})\n"

            # 改进建议
            if result.recommendations:
                block_message += f"\n💡 改进建议:\n"
                for rec in result.recommendations[:3]:
                    block_message += f"   → {rec}\n"

            block_message += f"\n{'='*60}\n"

            response.content = block_message
            logger.warning(
                f"[TaijiVerifyPro] BLOCK - 风险={result.risk_score:.1%}, "
                f"耗时={processing_ms}ms, 关键问题={len(high_risk_dims)}个"
            )
            return response

        # 🟠 HIGH_RISK: 警告但放行
        if result.verdict.value == "high_risk":
            warning = (
                f"\n\n⚠️ [TaijiVerifyPro 警告] 幻觉风险较高: {result.risk_score:.1%}"
            )

            if self.config.taijiverifypro_show_report and result.recommendations:
                warning += f"\n建议: {result.recommendations[0]}"

            response.content += warning
            logger.info(f"[TaijiVerifyPro] HIGH_RISK - 风险={result.risk_score:.1%}")
            return response

        # 🟡 MEDIUM_RISK / 🟢 LOW_RISK / ✅ PASS: 可选显示报告
        if self.config.taijiverifypro_show_report and result.verdict.value in ("medium_risk",):
            report = (
                f"\n\n[TaijiVerifyPro] 风险评估: {result.risk_score:.1%} ({result.verdict.value})"
            )
            response.content += report

        # ✅ PASS / LOW_RISK: 正常通过，记录日志
        if self.config.verbose or result.risk_score > 0.3:
            logger.info(
                f"[TaijiVerifyPro] {result.verdict.value.upper()} - "
                f"风险={result.risk_score:.1%}, 耗时={processing_ms}ms"
            )

        return response

    def _taiji_verify_response(self, response) -> Any:
        """使用太极验证引擎进行完整流水线验证"""
        from taiji_agent.taiji_verify.engine import VerificationRequest, Verdict

        req = VerificationRequest(
            input_text=response.content,
            ground_truth=self._get_last_user_query() or response.content,
        )
        result = self.taiji_verify.verify(req)

        # 记录验证结果到事件总线
        self.event_bus.emit_sync("taiji:verify:result", {
            "verdict": result.verdict.value,
            "delta_s": result.delta_s_result.delta_s if result.delta_s_result else None,
            "failures": result.failure_count,
            "processing_ms": result.processing_time_ms,
        })

        if result.verdict == Verdict.BLOCK:
            if self.config.taiji_verify_block_on_danger:
                response.content = (
                    f"[🚫 太极验证引擎拦截] 检测到严重问题:\n"
                    + "\n".join(f"  - {d.mode.name_cn}: {d.details}"
                              for d in result.failure_detections[:3])
                    + f"\n\nΔS={result.delta_s_result.delta_s:.3f}"
                      f" (zone={result.delta_s_result.zone.value})"
                      if result.delta_s_result else ""
                )
            return response

        if result.verdict in (Verdict.CONDITIONAL_PASS, Verdict.CORRECTED):
            zone = "🟡"
            if result.delta_s_result:
                zone_map = {"safe": "🟢", "transit": "🟡", "risk": "🟠", "danger": "🔴"}
                zone = zone_map.get(result.delta_s_result.zone.value, "🟡")
            note = f"\n\n[{zone} 太极验证: {result.verdict.value}]"
            if result.failure_detections:
                note += f" ({len(result.failure_detections)}个注意项)"
            response.content += note

        return response

    def _get_last_user_query(self) -> str:
        """获取最后一条用户消息"""
        for msg in reversed(self.messages):
            if hasattr(msg, 'role') and msg.role == "user":
                return getattr(msg, 'content', '') or ''
        return ""

    def get_event_bus(self) -> EventBus:
        """获取事件总线"""
        return self.event_bus

    def get_memory(self) -> SessionMemory:
        """获取记忆"""
        return self.memory

    def get_tools(self) -> ToolRegistry:
        """获取工具注册表"""
        return self.tools


async def create_agent(
    provider: str = "anthropic",
    model: str = "deepseek-v4-pro",
    api_key: Optional[str] = None,
    **kwargs,
) -> TaijiAgent:
    """创建 Agent 的便捷函数"""
    config = AgentConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        **kwargs,
    )
    return TaijiAgent(config=config)
