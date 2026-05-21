"""TokenJuice 主压缩引擎测试"""
import pytest
from taiji_agent.tokenjuice.compressor import (
    TokenJuiceCompressor,
    CompressedContent,
    TRIGGER_THRESHOLD_TOKENS
)


class MockLLMProvider:
    """模拟 LLM 提供商"""
    def chat(self, messages, **kwargs):
        class Response:
            content = "这是摘要后的内容"
        return Response()


@pytest.fixture
def compressor():
    return TokenJuiceCompressor()


@pytest.fixture
def compressor_with_llm():
    return TokenJuiceCompressor(llm_provider=MockLLMProvider())


def test_compress_short_content(compressor):
    """测试压缩短内容（不触发摘要）"""
    content = "<p>Hello <b>World</b></p>"
    result = compressor.compress(content)
    assert isinstance(result, CompressedContent)
    assert result.tokens < 100
    assert "Hello **World**" in result.text


def test_compress_with_context(compressor):
    """测试带上下文压缩"""
    content = "Some content"
    result = compressor.compress(content, context="Previous context")
    assert result.text is not None


def test_estimate_savings(compressor):
    """测试节省估算"""
    original = "A" * 1000
    compressed = compressor.compress(original)
    savings = compressor.estimate_savings(original, compressed.text)
    assert savings >= 0


def test_html_conversion(compressor):
    """测试 HTML 转换"""
    html = "<div><p>Test</p></div>"
    result = compressor.compress(html)
    assert "Test" in result.text
    assert "<" not in result.text


def test_empty_content(compressor):
    """测试空内容"""
    result = compressor.compress("")
    assert result.text == ""
    assert result.tokens == 0


def test_long_content_with_llm(compressor_with_llm):
    """测试长内容 LLM 摘要"""
    content = "这是测试内容。" * 2000
    result = compressor_with_llm.compress(content)
    assert result.original_tokens >= TRIGGER_THRESHOLD_TOKENS


def test_threshold_constant():
    """测试阈值常量"""
    assert TRIGGER_THRESHOLD_TOKENS == 3000
