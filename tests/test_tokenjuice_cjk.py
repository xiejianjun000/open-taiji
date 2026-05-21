"""TokenJuice CJK 保留规则测试"""
import pytest
from taiji_agent.tokenjuice.rules.cjk_preserver import preserve_cjk, is_cjk


def test_preserve_chinese():
    """测试保留中文"""
    text = "这是一段中文文本"
    result = preserve_cjk(text)
    assert result == text


def test_preserve_japanese():
    """测试保留日文"""
    text = "これは日本語のテキストです"
    result = preserve_cjk(text)
    assert "日本" in result


def test_preserve_korean():
    """测试保留韩文"""
    text = "안녕하세요 한국어 텍스트입니다"
    result = preserve_cjk(text)
    assert "한국어" in result


def test_mixed_content():
    """测试混合内容"""
    text = "Hello 你好 World 世界"
    result = preserve_cjk(text)
    assert "你好" in result
    assert "世界" in result


def test_is_cjk():
    """测试 CJK 字符检测"""
    assert is_cjk("中") == True
    assert is_cjk("日") == True
    assert is_cjk("한") == True
    assert is_cjk("a") == False
    assert is_cjk("A") == False


def test_empty_text():
    """测试空文本"""
    assert preserve_cjk("") == ""
    assert preserve_cjk(None) == ""
