"""Anthropic Provider — 兼容 Anthropic/DeepSeek API"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any, Optional, Union

import httpx

from taiji_agent.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude / DeepSeek Provider"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514", base_url: Optional[str] = None, 
                 timeout: float = 120.0, max_retries: int = 2, **kwargs):
        super().__init__(api_key=api_key, model=model, base_url=base_url, **kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = None

    def _get_client(self):
        if self.client is None:
            try:
                from anthropic import AsyncAnthropic
                kwargs = {
                    "api_key": self.api_key,
                    "timeout": httpx.Timeout(self.timeout, connect=30.0, read=self.timeout, write=60.0, pool=10.0),
                    "max_retries": self.max_retries,
                }
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self.client = AsyncAnthropic(**kwargs)
            except ImportError as e:
                raise ImportError("anthropic package not installed: pip install anthropic") from e
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
        client = self._get_client()

        # 转换消息格式：system 角色转为顶层参数（Anthropic 原生不支持 messages 中的 system）
        formatted_messages: list[dict[str, Any]] = []
        system_content = None
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "tool":
                formatted_messages.append({
                    "role": "user",
                    "content": json.dumps({
                        "tool_result": {
                            "tool_call_id": msg.get("tool_call_id", "unknown"),
                            "content": msg["content"],
                        }
                    }, ensure_ascii=False)
                })
            else:
                formatted_messages.append(msg)

        request_params: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_content:
            request_params["system"] = system_content

        if tools:
            request_params["tools"] = self._convert_tools(tools)

        try:
            response = await client.messages.create(**request_params)

            text_content = None
            tool_calls = None

            for block in response.content:
                if block.type == "text":
                    text_content = block.text
                elif block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "name": block.name,
                        "arguments": block.input,
                        "id": block.id,
                    })

            return LLMResponse(
                content=text_content,
                tool_calls=tool_calls,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                model=self.model,
                raw=response,
            )
        except httpx.TimeoutException:
            logger.error(f"[Timeout] LLM request timed out after {self.timeout}s: model={self.model}")
            return LLMResponse(
                content=f"[Timeout] LLM 请求超时（{self.timeout}秒），请稍后重试。若持续出现请检查 API 配额和网络。",
                raw=None,
            )
        except Exception as e:
            logger.error(f"[Provider Error] {type(e).__name__}: {e}")
            return LLMResponse(
                content=f"[Provider Error] {type(e).__name__}: {e}",
                raw=None,
            )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str | dict, None]:
        """流式聊天 — 产出两种 token: 文本字符串 或 完整 _tool_call dict"""
        client = self._get_client()

        formatted_messages: list[dict[str, Any]] = []
        system_content = None
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "tool":
                formatted_messages.append({
                    "role": "user",
                    "content": json.dumps({
                        "tool_result": {
                            "tool_call_id": msg.get("tool_call_id", "unknown"),
                            "content": msg["content"],
                        }
                    }, ensure_ascii=False)
                })
            else:
                formatted_messages.append(msg)

        request_params: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_content:
            request_params["system"] = system_content

        if tools:
            request_params["tools"] = self._convert_tools(tools)

        # 工具调用追踪
        current_tool_name = None
        current_tool_id = None
        current_tool_args_parts: list[str] = []

        async with client.messages.stream(**request_params) as stream:
            async for event in stream:
                try:
                    if event.type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block is None:
                            continue
                        block_type = getattr(block, "type", None)

                        if block_type == "tool_use":
                            current_tool_name = getattr(block, "name", "unknown")
                            current_tool_id = getattr(block, "id", "")
                            current_tool_args_parts = []
                        # thinking 和 text 的 start 忽略，内容在 delta 中

                    elif event.type == "content_block_delta":
                        delta = event.delta

                        # 文本内容 — 直接产出
                        if hasattr(delta, "text") and delta.text:
                            yield delta.text

                        # 工具参数片段 — 累积，不产出
                        elif hasattr(delta, "partial_json") and delta.partial_json:
                            current_tool_args_parts.append(delta.partial_json)

                        # thinking 内容 — 完全忽略，不暴露给用户
                        # (DeepSeek extended thinking 在此被拦截)

                    elif event.type == "content_block_stop":
                        # 工具调用块结束 — 产出完整的 _tool_call
                        if current_tool_name and current_tool_args_parts:
                            args_str = "".join(current_tool_args_parts)
                            try:
                                args = json.loads(args_str)
                            except json.JSONDecodeError:
                                args = {}
                            yield {
                                "_tool_call": {
                                    "name": current_tool_name,
                                    "arguments": args,
                                    "id": current_tool_id,
                                }
                            }
                            current_tool_name = None
                            current_tool_id = None
                            current_tool_args_parts = []

                    # 忽略: message_start, message_stop, message_delta, thinking, signature, input_json
                except Exception:
                    pass

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    @staticmethod
    def _convert_tools(tools: list[dict]) -> list[dict]:
        """OpenAI-format parameters → Anthropic-format input_schema"""
        converted = []
        for tool in tools:
            t = dict(tool)
            if "parameters" in t and "input_schema" not in t:
                t["input_schema"] = t.pop("parameters")
            converted.append(t)
        return converted
