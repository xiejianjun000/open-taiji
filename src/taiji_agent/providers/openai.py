"""
OpenAI Provider
"""

import os
from typing import Optional
from collections.abc import AsyncGenerator

from taiji_agent.providers.base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI Provider"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o", base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key, model=model, base_url=base_url, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.client = None

    def _get_client(self):
        """获取客户端"""
        if self.client is None:
            try:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError as e:
                raise ImportError("openai package not installed: pip install openai") from e
        return self.client

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
        client = self._get_client()

        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            request_params["tools"] = tools

        try:
            response = await client.chat.completions.create(**request_params)

            choice = response.choices[0]
            message = choice.message

            return LLMResponse(
                content=message.content,
                tool_calls=[
                    {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                        "id": tc.id,
                    }
                    for tc in (message.tool_calls or [])
                ],
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
                model=self.model,
                raw=response,
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
            )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式聊天"""
        client = self._get_client()

        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            request_params["tools"] = tools

        stream = await client.chat.completions.create(**request_params)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        return len(text) // 4
