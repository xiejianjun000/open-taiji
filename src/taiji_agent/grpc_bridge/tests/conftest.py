"""
Pytest 配置文件

配置测试环境和 fixtures。
"""

import asyncio
import logging
import os
import sys
from typing import Generator

import pytest

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


# ============================================================
# Pytest 配置
# ============================================================

def pytest_configure(config):
    """Pytest 配置"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环（用于异步测试）"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_channel():
    """模拟 gRPC 通道"""
    from unittest.mock import MagicMock
    channel = MagicMock()
    channel.is_active = MagicMock(return_value=True)
    channel.close = asyncio.coroutine(lambda: None)
    return channel


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        "address": "localhost:50051",
        "timeout": 10.0,
        "enable_retry": True,
        "enable_pool": False,
    }


@pytest.fixture
def sample_messages():
    """示例对话消息"""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"},
        {"role": "user", "content": "Can you help me with coding?"},
    ]


@pytest.fixture
def sample_tool():
    """示例工具定义"""
    return {
        "name": "get_weather",
        "description": "Get the current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city name",
                }
            },
            "required": ["location"],
        },
        "type": 1,  # FUNCTION
    }


@pytest.fixture
def sample_memory():
    """示例记忆数据"""
    return {
        "content": "User prefers dark mode interface",
        "type": 2,  # EPISODIC
        "session_id": "test-session-001",
        "metadata": {
            "source": "user_preference",
            "importance": "high",
        },
    }


@pytest.fixture
def sample_skill():
    """示例技能数据"""
    return {
        "name": "Code Review",
        "description": "Perform code review and provide suggestions",
        "content": """# Code Review Skill

## Description
Review code and provide constructive feedback.

## Usage
Use this skill when you need to review code.

## Steps
1. Read the code carefully
2. Identify potential issues
3. Provide recommendations
""",
        "category": "development",
        "tags": ["code", "review", "quality"],
        "metadata": {
            "version": "1.0.0",
            "author": "Taiji Team",
        },
    }


# ============================================================
# 异步测试帮助函数
# ============================================================

async def async_timeout(coro, timeout: float):
    """异步超时包装器"""
    return await asyncio.wait_for(coro, timeout=timeout)


# ============================================================
# Mock 帮助函数
# ============================================================

def create_mock_request(**kwargs):
    """创建模拟请求对象"""
    from unittest.mock import MagicMock
    
    request = MagicMock()
    for key, value in kwargs.items():
        setattr(request, key, value)
    
    # 默认 HasField 返回 False
    request.HasField = MagicMock(return_value=False)
    
    return request


def create_mock_context():
    """创建模拟 gRPC 上下文"""
    from unittest.mock import MagicMock
    
    context = MagicMock()
    context.is_active = MagicMock(return_value=True)
    context.set_code = MagicMock()
    context.set_details = MagicMock()
    context.abort = MagicMock()
    
    return context
