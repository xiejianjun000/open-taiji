"""
LLM Provider 基类
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMResponse:
    """LLM 响应"""

    content: Optional[str] = None
    tool_calls: Optional[list] = None
    usage: Optional[dict] = None
    model: Optional[str] = None
    raw: Optional[Any] = None


class LLMProvider(ABC):
    """LLM Provider 基类"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4", base_url: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse:
        """发送聊天请求"""
        pass

    async def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式聊天"""
        response = await self.chat(
            messages=messages, tools=tools, temperature=temperature, max_tokens=max_tokens, stream=True, **kwargs
        )

        if response.content:
            for char in response.content:
                yield char

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        return len(text) // 4
