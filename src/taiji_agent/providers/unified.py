"""统一模型提供商注册 — 自动发现和切换

支持所有国产大模型的热切换和故障转移。
"""
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class UnifiedProviderRegistry:
    """统一提供商注册表"""

    def __init__(self):
        self._providers: dict[str, Any] = {}
        self._primary: Optional[str] = None
        self._fallbacks: list[str] = []

    def register(self, name: str, provider_cls, **kwargs):
        """注册提供商"""
        self._providers[name] = {"cls": provider_cls, "kwargs": kwargs}

    def set_primary(self, name: str):
        """设置主提供商"""
        self._primary = name

    def add_fallback(self, name: str):
        """添加故障转移"""
        if name not in self._fallbacks:
            self._fallbacks.append(name)

    def get_provider(self, name: str = None):
        """获取提供商实例"""
        name = name or self._primary
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        info = self._providers[name]
        return info["cls"](**info["kwargs"])

    def list_all(self) -> list[str]:
        return list(self._providers.keys())

    @classmethod
    def auto_discover(cls) -> "UnifiedProviderRegistry":
        """自动发现所有可用提供商"""
        reg = cls()

        # Anthropic (默认)
        try:
            from taiji_agent.providers.anthropic import AnthropicProvider
            reg.register("anthropic", AnthropicProvider,
                        api_key=os.getenv("ANTHROPIC_API_KEY"),
                        base_url=os.getenv("ANTHROPIC_BASE_URL"),
                        model=os.getenv("TAIJI_AGENT_MODEL", "deepseek-v4-pro"))
        except ImportError:
            pass

        # OpenAI
        try:
            from taiji_agent.providers.openai import OpenAIProvider
            reg.register("openai", OpenAIProvider)
        except ImportError:
            pass

        # 国产模型 — 自动检测 API key 存在
        chinese_providers = [
            ("deepseek", "DEEPSEEK"),
            ("qwen", "DASHSCOPE"),
            ("glm", "GLM"),
            ("kimi", "MOONSHOT"),
            ("doubao", "DOUBAO"),
            ("qianfan", "QIANFAN"),
            ("hunyuan", "HUNYUAN"),
            ("moonshot", "MOONSHOT"),
            ("minimax", "MINIMAX"),
            ("stepfun", "STEPFUN"),
            ("xiaomi", "XIAOMI"),
        ]

        for name, env_prefix in chinese_providers:
            api_key = os.getenv(f"{env_prefix}_API_KEY")
            if api_key:
                try:
                    mod = __import__(f"taiji_agent.providers.chinese.{name}",
                                   fromlist=[f"{name.capitalize()}Provider"])
                    cls_name = f"{name.capitalize()}Provider" if name != "doubao" else "DoubaoProvider"
                    provider_cls = getattr(mod, cls_name, None)
                    if provider_cls:
                        reg.register(name, provider_cls, api_key=api_key)
                        logger.debug("Auto-discovered provider: %s", name)
                except (ImportError, AttributeError) as e:
                    logger.debug("Provider %s not available: %s", name, e)

        # Default primary
        if "deepseek" in reg._providers:
            reg.set_primary("deepseek")
        elif "anthropic" in reg._providers:
            reg.set_primary("anthropic")

        return reg


# 全局实例
unified_registry = UnifiedProviderRegistry.auto_discover()

# 便捷获取
def get_available_chinese_models() -> list[dict]:
    """获取所有可用的国产模型列表"""
    from taiji_agent.providers.chinese import PROVIDER_META
    available = []
    for key, meta in PROVIDER_META.items():
        env_prefix = key.upper() if key != "doubao" else "DOUBAO"
        if key == "kimi":
            env_prefix = "MOONSHOT"
        if os.getenv(f"{env_prefix}_API_KEY"):
            available.append({
                "key": key,
                "name": meta["name"],
                "models": meta.get("models", []),
                "base_url": meta.get("base_url", ""),
            })
    return available
