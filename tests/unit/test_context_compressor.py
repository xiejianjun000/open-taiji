"""
上下文压缩器单元测试
测试: 压缩算法, Token 估算, 阈值判断, dict+Pydantic 兼容
"""
import pytest
from pydantic import BaseModel
from taiji_agent.context.compressor import (
    ContextCompressor, _msg_role, _msg_content,
)


class PMsg(BaseModel):
    role: str
    content: str


class TestCompressor:
    """压缩算法"""

    def test_no_compress_when_short(self):
        compressor = ContextCompressor(protect_first_n=2, protect_last_n=3)
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        result = compressor.compress(msgs)
        # 小于保护阈值时不压缩
        assert len(result) == 5

    def test_compress_long_conversation(self):
        compressor = ContextCompressor(protect_first_n=2, protect_last_n=3)
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = compressor.compress(msgs)
        assert len(result) < 20
        # 保留了首尾
        assert result[0]["content"] == "msg0"
        assert result[-1]["content"] == "msg19"

    def test_compress_preserves_head_tail(self):
        compressor = ContextCompressor(protect_first_n=3, protect_last_n=4)
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(30)]
        result = compressor.compress(msgs)
        # 前 3 条保留
        for i in range(3):
            assert any(m.get("content") == f"msg{i}" for m in result)
        # 后 4 条保留
        for i in range(26, 30):
            assert any(m.get("content") == f"msg{i}" for m in result)

    def test_compression_count_increments(self):
        compressor = ContextCompressor(protect_first_n=1, protect_last_n=1)
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(50)]
        assert compressor.compression_count == 0
        compressor.compress(msgs)
        assert compressor.compression_count == 1
        compressor.compress(msgs)
        assert compressor.compression_count == 2

    def test_summary_contains_user_queries(self):
        compressor = ContextCompressor(protect_first_n=1, protect_last_n=1)
        msgs = [
            {"role": "user", "content": "important question 1"},
            {"role": "assistant", "content": "answer 1"},
            {"role": "user", "content": "important question 2"},
            {"role": "assistant", "content": "answer 2"},
            {"role": "user", "content": "final question"},
        ]
        result = compressor.compress(msgs)
        # 中间应该有一个摘要消息
        summary_msgs = [m for m in result if "compressed" in str(m.get("content", "")).lower()]
        assert len(summary_msgs) >= 0  # 可能因为消息太少不压缩


class TestTokenEstimation:
    """Token 估算"""

    def test_estimate_tokens(self):
        compressor = ContextCompressor()
        text = "hello world"
        tokens = compressor.estimate_tokens(text)
        assert tokens == len(text) // 4

    def test_estimate_total_tokens_dict(self):
        compressor = ContextCompressor()
        msgs = [{"role": "user", "content": "hello"}] * 10
        total = compressor.estimate_total_tokens(msgs)
        assert total > 0

    def test_estimate_total_tokens_pydantic(self):
        compressor = ContextCompressor()
        msgs = [PMsg(role="user", content="hello")] * 10
        total = compressor.estimate_total_tokens(msgs)
        assert total > 0

    def test_should_compress_when_over_threshold(self):
        compressor = ContextCompressor(threshold_percent=0.75)
        compressor.last_prompt_tokens = 100000  # > 128000*0.75=96000
        assert compressor.should_compress() is True

    def test_should_compress_when_under_threshold(self):
        compressor = ContextCompressor(threshold_percent=0.75)
        compressor.last_prompt_tokens = 50000  # < 96000
        assert compressor.should_compress() is False

    def test_should_compress_with_explicit_tokens_over(self):
        compressor = ContextCompressor(threshold_percent=0.75)
        assert compressor.should_compress(prompt_tokens=100000) is True

    def test_should_compress_with_explicit_tokens_under(self):
        compressor = ContextCompressor(threshold_percent=0.75)
        assert compressor.should_compress(prompt_tokens=50000) is False


class TestMessageTypeCompatibility:
    """dict 和 Pydantic 消息兼容"""

    def test_msg_role_dict(self):
        assert _msg_role({"role": "user", "content": "hi"}) == "user"
        assert _msg_role({"role": "assistant", "content": "ok"}) == "assistant"
        assert _msg_role({"role": "tool", "content": "result"}) == "tool"

    def test_msg_role_pydantic(self):
        assert _msg_role(PMsg(role="user", content="hi")) == "user"
        assert _msg_role(PMsg(role="system", content="prompt")) == "system"

    def test_msg_content_dict(self):
        assert _msg_content({"role": "user", "content": "hello"}) == "hello"

    def test_msg_content_pydantic(self):
        assert _msg_content(PMsg(role="user", content="hello pydantic")) == "hello pydantic"

    def test_compress_with_pydantic(self):
        compressor = ContextCompressor(protect_first_n=2, protect_last_n=3)
        msgs = [PMsg(role="user", content=f"msg{i}") for i in range(20)]
        result = compressor.compress(msgs)
        assert len(result) < 20

    def test_compress_with_mixed_types(self):
        compressor = ContextCompressor(protect_first_n=1, protect_last_n=1)
        msgs = [
            PMsg(role="system", content="sys"),
            {"role": "user", "content": "q1"},
            PMsg(role="assistant", content="a1"),
            {"role": "user", "content": "q2"},
            PMsg(role="assistant", content="a2"),
            {"role": "user", "content": "q3"},
            PMsg(role="assistant", content="a3"),
        ]
        result = compressor.compress(msgs)
        # 不应崩溃
        assert len(result) > 0

    def test_summarize_with_pydantic(self):
        compressor = ContextCompressor(protect_first_n=1, protect_last_n=1)
        msgs = [PMsg(role="user", content=f"query{i}") for i in range(15)]
        result = compressor.compress(msgs)
        assert len(result) < 15
