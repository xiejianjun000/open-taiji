"""
TAIJI-AGENT ↔ LiteLLM 适配器
让 TAIJI-AGENT 通过 LiteLLM 代理调用本地/云端模型
"""

import os
from typing import Any, Optional

from taiji_agent.providers.base import LLMProvider, LLMResponse


class LiteLLMProvider(LLMProvider):
    """
    LiteLLM 统一代理 Provider

    支持:
    - 通过 LiteLLM 代理调用任意模型
    - 本地 vLLM 模型服务
    - 云端 API (OpenAI/Qwen/GLM)
    - 开发模式 Mock
    """

    def __init__(
        self,
        model: str = "qwen3",
        api_base: str = "http://localhost:4000",
        api_key: str | None = None,
        litellm_config: dict | None = None,
        **kwargs,
    ):
        super().__init__(
            api_key=api_key or os.getenv("LITELLM_API_KEY", "sk-ecomind-litellm-local"),
            model=model,
            base_url=api_base,
        )
        self.litellm_config = litellm_config or {}
        self._client = None

    def _get_client(self):
        """获取 OpenAI 兼容客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError("openai package not installed: pip install openai")
        return self._client

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse:
        """发送聊天请求通过 LiteLLM 代理"""
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
                } if response.usage else None,
                model=self.model,
                raw=response,
            )
        except Exception as e:
            return LLMResponse(
                content=f"LiteLLM Error: {str(e)}",
            )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
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


class MockLiteLLMProvider(LLMProvider):
    """
    Mock LiteLLM Provider
    本地开发模式，无需真实 API Key
    """

    def __init__(self, model: str = "mock-qwen3"):
        super().__init__(api_key="mock", model=model, base_url="mock://localhost")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse:
        """模拟 LiteLLM 响应"""
        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")

        # 模拟模型响应
        response_text = (
            f"[Mock-LiteLLM] 收到请求: \"{user_msg[:50]}...\"\n"
            f"\n基于生态环境监测数据分析：\n"
            f"- 空气质量指数(AQI): 65 (良)\n"
            f"- PM2.5浓度: 35μg/m³\n"
            f"- 水质达标率: 92.3%\n"
            f"\n建议：加强污染源管控，持续改善区域环境质量。[来源:生态环境部]"
        )

        return LLMResponse(
            content=response_text,
            tool_calls=None,
            usage={"input_tokens": 50, "output_tokens": 100},
            model=self.model,
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
        """模拟流式响应"""
        response_text = (
            "[Mock-LiteLLM] 模拟流式输出："
            "生态环境保护是国策，需要全社会共同参与。"
        )
        for char in response_text:
            yield char

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
