"""
后台审查引擎单元测试
测试: should_review 判定, 记忆价值判断, dict+Pydantic 兼容
"""
import pytest
from pydantic import BaseModel
from taiji_agent.review.engine import (
    BackgroundReviewEngine, _msg_role, _msg_content,
)


class PMsg(BaseModel):
    role: str
    content: str


class TestShouldReview:
    """审查触发判定"""

    def test_enough_activity_triggers_both(self):
        engine = BackgroundReviewEngine()
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "user", "content": "help"},
            {"role": "tool", "content": "r1"},
            {"role": "tool", "content": "r2"},
            {"role": "tool", "content": "r3"},
        ]
        mem, skills = engine.should_review(msgs)
        assert mem is True
        assert skills is True

    def test_only_user_turns_triggers_memory(self):
        engine = BackgroundReviewEngine()
        msgs = [
            {"role": "user", "content": "q1"},
            {"role": "user", "content": "q2"},
        ]
        mem, skills = engine.should_review(msgs)
        assert mem is True
        assert skills is False

    def test_only_tool_calls_no_review(self):
        engine = BackgroundReviewEngine()
        msgs = [
            {"role": "tool", "content": "r1"},
            {"role": "tool", "content": "r2"},
            {"role": "tool", "content": "r3"},
        ]
        mem, skills = engine.should_review(msgs)
        assert mem is False
        assert skills is True

    def test_insufficient_activity(self):
        engine = BackgroundReviewEngine()
        msgs = [{"role": "user", "content": "hi"}]
        mem, skills = engine.should_review(msgs)
        assert mem is False
        assert skills is False

    def test_empty_messages(self):
        engine = BackgroundReviewEngine()
        mem, skills = engine.should_review([])
        assert mem is False
        assert skills is False


class TestShouldReviewPydantic:
    """Pydantic Message 对象兼容"""

    def test_pydantic_enough_activity(self):
        engine = BackgroundReviewEngine()
        msgs = [
            PMsg(role="user", content="q1"),
            PMsg(role="user", content="q2"),
            PMsg(role="tool", content="r1"),
            PMsg(role="tool", content="r2"),
            PMsg(role="tool", content="r3"),
        ]
        mem, skills = engine.should_review(msgs)
        assert mem is True
        assert skills is True

    def test_pydantic_insufficient(self):
        engine = BackgroundReviewEngine()
        msgs = [PMsg(role="user", content="hi")]
        mem, skills = engine.should_review(msgs)
        assert mem is False

    def test_mixed_types(self):
        engine = BackgroundReviewEngine()
        msgs = [
            PMsg(role="user", content="q1"),
            {"role": "user", "content": "q2"},
            PMsg(role="tool", content="r1"),
            {"role": "tool", "content": "r2"},
            {"role": "tool", "content": "r3"},
        ]
        mem, skills = engine.should_review(msgs)
        assert mem is True
        assert skills is True


class TestMemoryValueDetection:
    """记忆价值判断"""

    def test_memory_keywords_chinese(self):
        engine = BackgroundReviewEngine()
        assert engine._has_memory_value("我喜欢用黑色主题") is True
        assert engine._has_memory_value("请记住我的偏好是简洁风格") is True
        assert engine._has_memory_value("这个很重要，每次都这样") is True

    def test_memory_keywords_english(self):
        engine = BackgroundReviewEngine()
        assert engine._has_memory_value("I prefer dark mode always") is True
        assert engine._has_memory_value("remember to use port 8080") is True

    def test_no_memory_value(self):
        engine = BackgroundReviewEngine()
        assert engine._has_memory_value("hello world") is False
        assert engine._has_memory_value("今天的天气不错") is False

    def test_short_text_ignored(self):
        engine = BackgroundReviewEngine()
        # _has_memory_value 只检查关键词，长度检查在 _review_memory 中
        assert engine._has_memory_value("记住") is True  # 有关键词
        assert engine._has_memory_value("hi") is False     # 无关键词


class TestHelperFunctions:
    """_msg_role 和 _msg_content 兼容函数"""

    def test_dict_access(self):
        assert _msg_role({"role": "user", "content": "hi"}) == "user"
        assert _msg_content({"role": "user", "content": "hello"}) == "hello"

    def test_pydantic_access(self):
        msg = PMsg(role="assistant", content="response")
        assert _msg_role(msg) == "assistant"
        assert _msg_content(msg) == "response"

    def test_missing_role_dict(self):
        assert _msg_role({"content": "no role"}) == ""

    def test_missing_role_pydantic(self):
        msg = PMsg(role="", content="empty")
        assert _msg_role(msg) == ""
