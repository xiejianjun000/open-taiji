"""
Taiji Agent Engine - 融合 Hermes Agent + Harness + Taiji Verify
核心 Agent Loop 实现
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel

from taiji_agent.events.bus import EventBus
from taiji_agent.memory.session import SessionMemory
from taiji_agent.providers.base import LLMProvider
from taiji_agent.souls.loader import SoulLoader, inject_soul
from taiji_agent.tools.registry import ToolRegistry
from taiji_agent.wfgy.verifier import HallucinationDetector, SelfConsistencyChecker, TaijiVerifier

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
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


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
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None
    base_url: str | None = None
    soul: str = "default"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_iterations: int = 25
    taiji_verify_enabled: bool = True
    taiji_verify_threshold: float = 0.7
    self_consistency_samples: int = 3
    stream: bool = True
    workdir: str = "."
    verbose: bool = False


@dataclass
class TaskResult:
    status: TaskStatus
    content: str | None = None
    error: str | None = None
    iterations: int = 0
    tools_used: list[str] = field(default_factory=list)
    verify_blocked: int = 0
    hallucination_risk: float = 0.0


class TaijiAgent:
    """
    太极 Agent - 融合三大框架精华

    特性:
    - Agent Loop 基于 cgast/harness (~350行核心)
    - Taiji Verify 防幻觉验证
    - 工具系统来自 Hermes Agent
    - Soul 人格系统来自 Harness
    - 记忆系统来自 Hermes Honcho
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        provider: LLMProvider | None = None,
    ):
        self.config = config or AgentConfig()
        self.provider = provider
        self.event_bus = EventBus()

        self.soul_loader = SoulLoader()
        self.taiji_verifier = TaijiVerifier()
        self.hallucination_detector = HallucinationDetector()
        self.consistency_checker = SelfConsistencyChecker()
        self.memory = SessionMemory()
        self.tools = ToolRegistry()

        self.messages: list[Message] = []
        self.iteration_count = 0

        if self.provider is None:
            self._init_provider()

    def _init_provider(self):
        """初始化 LLM 提供商"""
        if self.config.provider == "anthropic":
            from taiji_agent.providers.anthropic import AnthropicProvider

            self.provider = AnthropicProvider(
                api_key=self.config.api_key,
                model=self.config.model,
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

    async def run(self, task: str, system_message: str | None = None) -> TaskResult:
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

        self.messages = []
        self.iteration_count = 0

        system_prompt = self._build_system_prompt()
        if system_message:
            system_prompt += f"\n\n{system_message}"

        self.messages.append(Message(role="system", content=system_prompt))
        self.messages.append(Message(role="user", content=task))

        while self.iteration_count < self.config.max_iterations:
            try:
                self.event_bus.emit_sync("prompt:assemble", {"iteration": self.iteration_count})
                self._assemble_prompt()

                self.event_bus.emit_sync(
                    "loop:start",
                    {
                        "iteration": self.iteration_count,
                        "messages_count": len(self.messages),
                    },
                )

                self.event_bus.emit_sync("llm:request", {"iteration": self.iteration_count})

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

                if self.config.taiji_verify_enabled and response.content:
                    response = await self._verify_and_annotate(response)

                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        self.event_bus.emit_sync(
                            "tool:request",
                            {
                                "name": tool_call.name,
                                "arguments": tool_call.arguments,
                            },
                        )

                        result = await self.tools.execute(tool_call)

                        self.messages.append(
                            Message(
                                role="assistant",
                                content=response.content or "",
                                tool_calls=[tc.model_dump() for tc in response.tool_calls],
                            )
                        )
                        self.messages.append(
                            Message(
                                role="tool",
                                content=result.content,
                                tool_call_id=tool_call.id,
                            )
                        )

                        self.event_bus.emit_sync(
                            "tool:result",
                            {
                                "name": tool_call.name,
                                "success": not (hasattr(result, "is_error") and result.is_error),
                            },
                        )

                    self.iteration_count += 1
                else:
                    self.messages.append(
                        Message(
                            role="assistant",
                            content=response.content or "",
                        )
                    )

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
                logger.error(f"Error in iteration {self.iteration_count}: {e}")
                self.event_bus.emit_sync("error", {"error": str(e)})

                if "max iterations" in str(e).lower():
                    return TaskResult(
                        status=TaskStatus.ABORTED,
                        error=str(e),
                        iterations=self.iteration_count,
                    )

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

    async def stream_run(self, task: str, system_message: str | None = None) -> AsyncGenerator[str, None]:
        """
        流式执行任务
        """
        self.event_bus.emit_sync("agent:start", {"task": task, "stream": True})

        self.messages = []
        self.iteration_count = 0

        system_prompt = self._build_system_prompt()
        if system_message:
            system_prompt += f"\n\n{system_message}"

        self.messages.append(Message(role="system", content=system_prompt))
        self.messages.append(Message(role="user", content=task))

        while self.iteration_count < self.config.max_iterations:
            try:
                response_text = ""

                provider = self.provider
                if provider is None:
                    raise ValueError("LLM provider not initialized")
                async for chunk in provider.stream_chat(
                    messages=[msg.model_dump() for msg in self.messages],
                    tools=self.tools.get_schemas() if self.tools.has_tools() else None,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                ):
                    if chunk:
                        response_text += chunk
                        yield chunk

                if self.config.taiji_verify_enabled and response_text:
                    risk = self.hallucination_detector.detect(response_text)
                    if risk > (1 - self.config.taiji_verify_threshold):
                        yield f"\n\n[⚠️ 幻觉风险 {risk:.1%}]"

                self.iteration_count += 1
                break

            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"\n\n[错误: {str(e)}]"
                break

    def _build_system_prompt(self) -> str:
        """构建系统提示 - 融合 Soul + Taiji Verify + 太极哲学"""
        soul = self.soul_loader.load(self.config.soul)

        prompt_parts = [
            "# 太极 Agent (Taiji Agent 2.0)",
            "",
            inject_soul(soul),
            "",
            "## Taiji Verify 防幻觉指南",
            "- 所有陈述必须有事实依据",
            "- 不确定时明确标注 [不确定]",
            "- 引用来源时必须准确",
            "- 被验证拦截的内容必须重写",
            "",
            "## 太极思维",
            "- 阳: 分析、推理、逻辑",
            "- 阴: 直觉、创造、共情",
            "- 在确定性和创造性之间找到平衡",
        ]

        return "\n".join(prompt_parts)

    def _assemble_prompt(self) -> list[dict]:
        """组装提示"""
        return [msg.model_dump() for msg in self.messages]

    async def _verify_and_annotate(self, response) -> Any:
        """Taiji Verify 验证并注解"""
        if not response.content:
            return response

        verify_passed = self.taiji_verifier.verify(response.content)

        risk = self.hallucination_detector.detect(response.content)

        if risk > (1 - self.config.taiji_verify_threshold):
            status = "通过" if verify_passed else "未通过"
            warning = f"\n\n[⚠️ 幻觉风险 {risk:.1%}，Taiji Verify 验证{status}]"
            response.content += warning

        return response

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
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None,
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
