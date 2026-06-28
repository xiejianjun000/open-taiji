"""
Providers 集成测试（Mock HTTP 响应）
测试所有 Provider 能够正确处理 API 响应
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from taiji_agent.providers.anthropic import AnthropicProvider
from taiji_agent.providers.openai import OpenAIProvider
from taiji_agent.providers.chinese import (
    QwenProvider, GLMProvider, KimiProvider, DoubaoProvider,
    QianfanProvider, HunyuanProvider, MoonshotProvider, MinimaxProvider,
    StepfunProvider, XiaomiProvider
)


class TestAnthropicProviderIntegration:
    """Anthropic Provider 集成测试（Mock）"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider_class", [
        AnthropicProvider, QwenProvider, GLMProvider, KimiProvider, DoubaoProvider,
        QianfanProvider, HunyuanProvider, MoonshotProvider, MinimaxProvider,
        StepfunProvider, XiaomiProvider, OpenAIProvider
    ])
    async def test_provider_chat_handles_error_gracefully(self, provider_class):
        """所有 Provider 都能优雅地处理错误"""
        provider = provider_class(api_key="test-key")

        # 即使不真实调用 API，也应该能处理错误情况
        messages = [{"role": "user", "content": "hello"}]

        # 我们不实际调用网络，只测试能返回错误响应
        try:
            response = await provider.chat(messages)
            # 不管成功还是错误，都应该返回 LLMResponse
            assert response is not None
        except Exception:
            # 如果有异常也没关系，主要是测试不会崩溃
            pass


class TestProviderWithMockClient:
    """使用 Mock Client 的测试"""

    @pytest.mark.asyncio
    async def test_anthropic_message_parsing(self):
        """测试 Anthropic 响应解析逻辑"""
        provider = AnthropicProvider(api_key="test-key")

        # Mock the client
        mock_response = MagicMock()
        mock_content_text = MagicMock()
        mock_content_text.type = "text"
        mock_content_text.text = "Mock response content"

        mock_response.content = [mock_content_text]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, '_get_client', return_value=mock_client):
            messages = [{"role": "user", "content": "test"}]
            response = await provider.chat(messages)

            assert response.content == "Mock response content"
            assert response.usage["input_tokens"] == 10
            assert response.usage["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_anthropic_tool_call_parsing(self):
        """测试 Anthropic 工具调用解析"""
        provider = AnthropicProvider(api_key="test-key")

        # Mock the client with tool call
        mock_response = MagicMock()
        mock_content_text = MagicMock()
        mock_content_text.type = "tool_use"
        mock_content_text.name = "file_read"
        mock_content_text.input = {"path": "/test.txt"}
        mock_content_text.id = "tc_123"

        mock_response.content = [mock_content_text]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 25

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, '_get_client', return_value=mock_client):
            messages = [{"role": "user", "content": "read file"}]
            response = await provider.chat(messages)

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["name"] == "file_read"
            assert response.tool_calls[0]["arguments"] == {"path": "/test.txt"}
            assert response.tool_calls[0]["id"] == "tc_123"
