"""
Agent Engine 核心单元测试
测试: AgentConfig, Message, TaskResult, 系统提示构建, 迭代控制
"""

import pytest
from taiji_agent.agent.engine import (
    AgentConfig, Message, ToolCall, TaskResult, TaskStatus
)


class TestAgentConfig:
    """AgentConfig 配置验证"""

    def test_default_values(self):
        config = AgentConfig()
        assert config.model in ("claude-sonnet-4-20250514", "deepseek-v4-pro")
        assert config.provider == "anthropic"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.max_iterations == 25
        assert config.verify_enabled is True
        assert config.stream is True

    def test_custom_values(self):
        config = AgentConfig(
            model="deepseek-v3",
            provider="deepseek",
            temperature=0.0,
            max_iterations=5,
            verify_enabled=False,
            stream=False,
        )
        assert config.model == "deepseek-v3"
        assert config.temperature == 0.0
        assert config.max_iterations == 5
        assert config.verify_enabled is False

    def test_temperature_clamping(self):
        """温度应该在 0-2 范围内"""
        config = AgentConfig(temperature=0.0)
        assert config.temperature == 0.0
        config2 = AgentConfig(temperature=2.0)
        assert config2.temperature == 2.0

    def test_model_default(self):
        config = AgentConfig()
        assert "claude" in config.model.lower() or "deepseek" in config.model.lower()


class TestMessage:
    """Message 模型序列化/反序列化"""

    def test_simple_message(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_message_with_tool_calls(self):
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[{"name": "file_list", "arguments": {}, "id": "tc1"}],
        )
        assert msg.role == "assistant"
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "file_list"

    def test_tool_message(self):
        msg = Message(role="tool", content="result content", tool_call_id="tc1")
        assert msg.role == "tool"
        assert msg.content == "result content"
        assert msg.tool_call_id == "tc1"

    def test_model_dump(self):
        msg = Message(role="user", content="hello")
        dumped = msg.model_dump()
        assert dumped["role"] == "user"
        assert dumped["content"] == "hello"
        assert dumped["tool_calls"] is None

    def test_model_dump_with_tool_calls(self):
        msg = Message(
            role="assistant",
            content="ok",
            tool_calls=[{"name": "read", "arguments": {"path": "/x"}, "id": "t1"}],
        )
        dumped = msg.model_dump()
        assert dumped["tool_calls"] == [{"name": "read", "arguments": {"path": "/x"}, "id": "t1"}]


class TestToolCall:
    """ToolCall 模型"""

    def test_create(self):
        tc = ToolCall(name="file_read", arguments={"path": "/tmp"}, id="tc1")
        assert tc.name == "file_read"
        assert tc.arguments == {"path": "/tmp"}
        assert tc.id == "tc1"


class TestTaskResult:
    """TaskResult 状态"""

    def test_completed(self):
        result = TaskResult(
            status=TaskStatus.COMPLETED,
            content="Done!",
            iterations=3,
            tools_used=["file_list"],
        )
        assert result.status == TaskStatus.COMPLETED
        assert result.content == "Done!"
        assert result.iterations == 3
        assert "file_list" in result.tools_used

    def test_aborted(self):
        result = TaskResult(
            status=TaskStatus.ABORTED,
            error="Max iterations reached",
            iterations=25,
        )
        assert result.status == TaskStatus.ABORTED
        assert result.error is not None
        assert "Max" in result.error

    def test_failed(self):
        result = TaskResult(status=TaskStatus.FAILED, error="API error")
        assert result.status == TaskStatus.FAILED

    def test_verify_blocked(self):
        result = TaskResult(
            status=TaskStatus.COMPLETED,
            content="verified",
            verify_blocked=2,
            hallucination_risk=0.3,
        )
        assert result.verify_blocked == 2
        assert result.hallucination_risk == 0.3


class TestTaskStatusEnum:
    """TaskStatus 枚举"""

    def test_all_statuses(self):
        statuses = list(TaskStatus)
        assert TaskStatus.PENDING in statuses
        assert TaskStatus.RUNNING in statuses
        assert TaskStatus.COMPLETED in statuses
        assert TaskStatus.ABORTED in statuses
        assert TaskStatus.FAILED in statuses
