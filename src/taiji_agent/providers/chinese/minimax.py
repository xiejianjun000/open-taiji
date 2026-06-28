"""MiniMax provider — OpenAI-compatible API"""

import os
from typing import Optional
from openai import AsyncOpenAI
from taiji_agent.providers.base import LLMProvider, LLMResponse


class MinimaxProvider(LLMProvider):
    """MiniMax LLM Provider (OpenAI-compatible)"""

    def __init__(self, api_key=None, model=None, base_url=None, **kwargs):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        self.base_url = base_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
        self.model = model or os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
        super().__init__(api_key=self.api_key, model=self.model, base_url=self.base_url, **kwargs)
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    async def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096, stream=False, **kwargs):
        client = self._get_client()
        req = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            req["tools"] = tools
        try:
            resp = await client.chat.completions.create(**req)
            msg = resp.choices[0].message
            tcs = None
            if msg.tool_calls:
                tcs = [{"name": tc.function.name, "arguments": tc.function.arguments, "id": tc.id} for tc in msg.tool_calls]
            return LLMResponse(content=msg.content, tool_calls=tcs, usage={"input_tokens": resp.usage.prompt_tokens if resp.usage else 0, "output_tokens": resp.usage.completion_tokens if resp.usage else 0}, model=self.model, raw=resp)
        except Exception as e:
            return LLMResponse(content=f"Error: {str(e)}", raw=None)

    async def stream_chat(self, messages, tools=None, temperature=0.7, max_tokens=4096, **kwargs):
        client = self._get_client()
        req = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        if tools:
            req["tools"] = tools
        try:
            stream = await client.chat.completions.create(**req)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception:
            yield ""

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
