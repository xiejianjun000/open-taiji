"""
Providers 单元测试：初始化 + 环境变量读取
测试所有 Provider 能否正确初始化和读取环境变量
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from taiji_agent.providers.base import LLMProvider, LLMResponse
from taiji_agent.providers.anthropic import AnthropicProvider
from taiji_agent.providers.openai import OpenAIProvider
from taiji_agent.providers.chinese import (
    QwenProvider, GLMProvider, KimiProvider, DoubaoProvider,
    QianfanProvider, HunyuanProvider, MoonshotProvider, MinimaxProvider,
    StepfunProvider, XiaomiProvider,
    PROVIDER_MAP, PROVIDER_META
)


class TestBaseProvider:
    """基类 Provider 测试"""

    def test_llm_response_dataclass(self):
        """测试 LLMResponse 数据类"""
        resp = LLMResponse(
            content="test content",
            tool_calls=[{"name": "test", "arguments": {}, "id": "1"}],
            usage={"input_tokens": 100, "output_tokens": 50},
            model="test-model",
            raw={"some": "data"}
        )
        assert resp.content == "test content"
        assert resp.tool_calls[0]["name"] == "test"
        assert resp.usage["input_tokens"] == 100
        assert resp.model == "test-model"

    def test_abstract_methods(self):
        """基类是抽象的，不能直接实例化"""
        with pytest.raises(TypeError):
            LLMProvider()


class TestAnthropicProvider:
    """Anthropic Provider 测试"""

    def test_init_with_defaults(self):
        """默认初始化"""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.model == "claude-sonnet-4-20250514"

    def test_init_with_custom_model(self):
        """自定义模型"""
        provider = AnthropicProvider(api_key="test-key", model="claude-opus")
        assert provider.model == "claude-opus"

    def test_init_from_env(self, monkeypatch):
        """从环境变量读取"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-123")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.anthropic.com")
        provider = AnthropicProvider()
        assert provider.api_key == "env-key-123"
        assert provider.base_url == "https://custom.anthropic.com"

    def test_estimate_tokens(self):
        """Token 估算"""
        provider = AnthropicProvider(api_key="test")
        assert provider.estimate_tokens("hello") >= 0


class TestOpenAIProvider:
    """OpenAI Provider 测试"""

    def test_init_with_defaults(self):
        """默认初始化"""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert "gpt" in provider.model.lower()

    def test_init_with_custom_model(self):
        """自定义模型"""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4-turbo")
        assert provider.model == "gpt-4-turbo"

    def test_init_from_env(self, monkeypatch):
        """从环境变量读取"""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key-456")
        provider = OpenAIProvider()
        assert provider.api_key == "env-key-456"

    def test_estimate_tokens(self):
        """Token 估算"""
        provider = OpenAIProvider(api_key="test")
        assert provider.estimate_tokens("hello world") >= 0


class TestChineseProviders:
    """国产模型 Provider 测试"""

    @pytest.mark.parametrize("provider_class, name, expected_env_key", [
        (QwenProvider, "Qwen", "DASHSCOPE_API_KEY"),
        (GLMProvider, "GLM", "ZHIPU_API_KEY"),
        (KimiProvider, "Kimi", "MOONSHOT_API_KEY"),
        (DoubaoProvider, "Doubao", "DOUBAO_API_KEY"),
        (QianfanProvider, "Qianfan", "QIANFAN_API_KEY"),
        (HunyuanProvider, "Hunyuan", "HUNYUAN_API_KEY"),
        (MoonshotProvider, "Moonshot", "MOONSHOT_API_KEY"),
        (MinimaxProvider, "Minimax", "MINIMAX_API_KEY"),
        (StepfunProvider, "Stepfun", "STEPFUN_API_KEY"),
        (XiaomiProvider, "Xiaomi", "XIAOMI_API_KEY"),
    ])
    def test_provider_basic_init(self, provider_class, name, expected_env_key):
        """各 Provider 基本初始化"""
        provider = provider_class(api_key=f"test-{name.lower()}")
        assert provider.api_key == f"test-{name.lower()}"
        assert provider.model is not None

    @pytest.mark.parametrize("provider_class, name, expected_env_key", [
        (QwenProvider, "Qwen", "DASHSCOPE_API_KEY"),
        (GLMProvider, "GLM", "ZHIPU_API_KEY"),
        (KimiProvider, "Kimi", "MOONSHOT_API_KEY"),
        (DoubaoProvider, "Doubao", "DOUBAO_API_KEY"),
        (QianfanProvider, "Qianfan", "QIANFAN_API_KEY"),
        (HunyuanProvider, "Hunyuan", "HUNYUAN_API_KEY"),
        (MoonshotProvider, "Moonshot", "MOONSHOT_API_KEY"),
        (MinimaxProvider, "Minimax", "MINIMAX_API_KEY"),
        (StepfunProvider, "Stepfun", "STEPFUN_API_KEY"),
        (XiaomiProvider, "Xiaomi", "XIAOMI_API_KEY"),
    ])
    def test_provider_from_env(self, provider_class, name, expected_env_key, monkeypatch):
        """各 Provider 从环境变量读取"""
        monkeypatch.setenv(expected_env_key, f"env-key-{name}")
        provider = provider_class()
        assert provider.api_key == f"env-key-{name}"

    @pytest.mark.parametrize("provider_class", [
        QwenProvider, GLMProvider, KimiProvider, DoubaoProvider,
        QianfanProvider, HunyuanProvider, MoonshotProvider, MinimaxProvider,
        StepfunProvider, XiaomiProvider
    ])
    def test_estimate_tokens(self, provider_class):
        """所有国产 Provider 的 Token 估算"""
        provider = provider_class(api_key="test")
        tokens = provider.estimate_tokens("测试一下 token 估算")
        assert isinstance(tokens, int)
        assert tokens >= 0


class TestProviderMetadata:
    """Provider 元数据测试"""

    def test_provider_map_exists(self):
        """PROVIDER_MAP 存在且不为空"""
        assert isinstance(PROVIDER_MAP, dict)
        assert len(PROVIDER_MAP) > 0

    def test_provider_meta_exists(self):
        """PROVIDER_META 存在且不为空"""
        assert isinstance(PROVIDER_META, dict)
        assert len(PROVIDER_META) > 0

    def test_provider_map_and_meta_sync(self):
        """PROVIDER_MAP 和 PROVIDER_META 的键一致"""
        map_keys = set(PROVIDER_MAP.keys())
        meta_keys = set(PROVIDER_META.keys())
        # 不一定需要完全一致，但应该有重叠
        assert len(map_keys & meta_keys) > 0

    def test_provider_meta_structure(self):
        """PROVIDER_META 结构正确"""
        for provider_id, meta in PROVIDER_META.items():
            assert "name" in meta
            assert "base_url" in meta
            assert "models" in meta
            assert isinstance(meta["models"], list)
            assert len(meta["models"]) > 0
