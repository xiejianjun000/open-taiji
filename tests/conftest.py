"""
Taiji Agent — 共享测试夹具与环境隔离

融合 Hermes Agent 的严密环境隔离 + OpenClaw OPC 的分层测试架构：

Hermetic 测试不变量 (enforced here):
1. **无凭据泄漏** — 所有 API_KEY/TOKEN/SECRET 环境变量在测试前清除
2. **隔离的 TAIJI_HOME** — 每测试使用独立 tempdir，不触碰 ~/.taiji/
3. **确定性运行时** — TZ=UTC, LANG=C.UTF-8, PYTHONHASHSEED=0
4. **模块状态重置** — 单例/ContextVar/模块级状态在测试间清零
5. **禁止变更检测测试** — 不硬编码枚举数量、模型列表等易变数据

测试分层 (OpenClaw 风格):
  unit/         — 纯逻辑，不依赖外部服务
  integration/  — 跨模块集成，Mock LLM
  e2e/          — 端到端流程，使用真实 API (需 API key)
  stress/       — 并发/压力/边界测试
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Ensure project source is importable
PROJECT_ROOT = Path(__file__).parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# =========================================================================
# 1. 凭据环境变量过滤 (Hermes 风格)
# =========================================================================

_CREDENTIAL_SUFFIXES = (
    "_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS",
    "_ACCESS_KEY", "_SECRET_ACCESS_KEY", "_PRIVATE_KEY",
    "_OAUTH_TOKEN", "_WEBHOOK_SECRET", "_ENCRYPT_KEY",
    "_APP_SECRET", "_CLIENT_SECRET", "_CORP_SECRET", "_AES_KEY",
)

_CREDENTIAL_NAMES = frozenset({
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
    "QWEN_API_KEY", "DASHSCOPE_API_KEY", "GLM_API_KEY", "ZAI_API_KEY",
    "KIMI_API_KEY", "MOONSHOT_API_KEY", "DOUBAO_API_KEY",
    "QIANFAN_API_KEY", "HUNYUAN_API_KEY", "MINIMAX_API_KEY",
    "STEPFUN_API_KEY", "XIAOMI_API_KEY",
    "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_ENCRYPT_KEY",
    "DINGTALK_APP_KEY", "DINGTALK_APP_SECRET",
    "WECOM_CORP_ID", "WECOM_SECRET",
    "WEIXIN_APP_ID", "WEIXIN_APP_SECRET",
    "QQ_APP_ID", "QQ_CLIENT_SECRET",
    "TAVILY_API_KEY", "ANTHROPIC_BASE_URL", "OPENAI_BASE_URL",
})


def _looks_like_credential(name: str) -> bool:
    if name in _CREDENTIAL_NAMES:
        return True
    return any(name.endswith(suf) for suf in _CREDENTIAL_SUFFIXES)


_TAIJI_BEHAVIORAL_VARS = frozenset({
    "TAIJI_HOME", "TAIJI_AGENT_MODEL", "TAIJI_AGENT_PROVIDER",
    "TAIJI_VERIFY_ENABLED", "TAIJI_STREAM", "TAIJI_MAX_ITERATIONS",
    "TAIJI_TEMPERATURE", "TAIJI_SOUL", "TAIJI_LOG_LEVEL",
    "DREAM_ENABLED", "DREAM_INTERVAL_HOURS",
})


# =========================================================================
# 2. 环境隔离 autouse fixture (Hermes 风格)
# =========================================================================

@pytest.fixture(autouse=True)
def _hermetic_environment(tmp_path, monkeypatch):
    """每个测试前强制执行环境隔离。"""
    # 1. 清除凭据变量
    for name in list(os.environ.keys()):
        if _looks_like_credential(name):
            monkeypatch.delenv(name, raising=False)

    # 2. 清除行为变量
    for name in _TAIJI_BEHAVIORAL_VARS:
        monkeypatch.delenv(name, raising=False)

    # 3. 隔离的 TAIJI_HOME
    fake_home = tmp_path / "taiji_test"
    fake_home.mkdir()
    for subdir in ["souls", "memory", "skills", "cron", "logs", "exports"]:
        (fake_home / subdir).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TAIJI_HOME", str(fake_home))

    # 4. 确定性环境
    monkeypatch.setenv("TZ", "UTC")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    monkeypatch.setenv("PYTHONHASHSEED", "0")

    # 5. 禁用网络发现
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


# =========================================================================
# 3. 模块状态重置 (Hermes 风格)
# =========================================================================

@pytest.fixture(autouse=True)
def _reset_module_state():
    """清除模块级可变状态，防止测试间泄漏。"""
    logging.disable(logging.NOTSET)
    for logger_name in ("taiji_agent", "taiji_agent.tools", "taiji_agent.agent"):
        lg = logging.getLogger(logger_name)
        lg.disabled = False
        lg.setLevel(logging.NOTSET)
        lg.propagate = True

    try:
        from taiji_agent.skills.provenance import reset_write_origin
        reset_write_origin("test_reset")
    except Exception:
        pass


# =========================================================================
# 4. 常用 Mock Fixtures
# =========================================================================

@pytest.fixture
def mock_llm_provider():
    """Mock LLM Provider — 返回可控响应，不调用真实 API"""
    from taiji_agent.providers.base import LLMResponse, LLMProvider

    provider = MagicMock(spec=LLMProvider)
    provider.model = "mock-model"
    provider.api_key = "mock-key"
    provider.base_url = "http://mock.test"

    default_response = LLMResponse(
        content="你好，我是太极助手。",
        tool_calls=None,
        usage={"input_tokens": 10, "output_tokens": 5},
        model="mock-model",
        raw=None,
    )

    async def _mock_chat(*args, **kwargs):
        return default_response

    provider.chat = _mock_chat

    async def _mock_stream_chat(*args, **kwargs):
        for char in "你好，我是太极助手。":
            yield char

    provider.stream_chat = _mock_stream_chat
    provider.estimate_tokens = MagicMock(return_value=42)
    return provider


@pytest.fixture
def mock_llm_with_tools():
    """Mock LLM Provider — 返回带工具调用的响应"""
    from taiji_agent.providers.base import LLMResponse, LLMProvider

    provider = MagicMock(spec=LLMProvider)
    provider.model = "mock-model"

    tool_response = LLMResponse(
        content="",
        tool_calls=[{
            "name": "file_list",
            "arguments": {"path": "/tmp"},
            "id": "tc_mock_001",
        }],
        usage={"input_tokens": 20, "output_tokens": 15},
        model="mock-model",
        raw=None,
    )

    async def _mock_chat(*args, **kwargs):
        return tool_response

    provider.chat = _mock_chat
    provider.stream_chat = AsyncMock()
    provider.estimate_tokens = MagicMock(return_value=42)
    return provider


@pytest.fixture
def temp_taiji_home(tmp_path):
    """创建临时 TAIJI_HOME 并返回路径"""
    home = tmp_path / "taiji"
    home.mkdir()
    for subdir in ["souls", "memory", "skills", "cron", "logs"]:
        (home / subdir).mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def agent_config():
    """基础 AgentConfig 供测试使用"""
    from taiji_agent.agent.engine import AgentConfig
    return AgentConfig(
        model="mock-model",
        provider="anthropic",
        temperature=0.0,
        max_iterations=3,
        verify_enabled=False,
        stream=False,
    )


@pytest.fixture
def sample_messages():
    """标准测试用消息列表"""
    from taiji_agent.agent.engine import Message
    return [
        Message(role="system", content="[System prompt]"),
        Message(role="user", content="你好"),
        Message(role="assistant", content="你好！有什么可以帮助你的？"),
        Message(role="user", content="列出当前目录的文件"),
    ]


# =========================================================================
# 5. Async 支持
# =========================================================================

@pytest.fixture(scope="session")
def event_loop():
    """创建 session 级 event loop 供 async 测试使用"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
