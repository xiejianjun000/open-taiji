"""TokenJuice 去重规则测试"""
import pytest
from taiji_agent.tokenjuice.rules.deduplicator import deduplicate


def test_remove_duplicate_sentences():
    """测试去除重复句子"""
    text = "这是第一句话\n这是第二句话\n这是第一句话\n这是第三句话"
    result = deduplicate(text)
    assert result.count("这是第一句话") == 1
    assert result.count("这是第二句话") == 1
    assert result.count("这是第三句话") == 1


def test_no_duplicates():
    """测试无重复文本"""
    text = "第一句。第二句。第三句。"
    result = deduplicate(text)
    assert result == text


def test_similar_lines():
    """测试去除相似行"""
    text = "Line 1: Hello World\nLine 2: Different content\nLine 1: Hello World"
    result = deduplicate(text)
    assert result.count("Hello World") == 1


def test_empty_text():
    """测试空文本"""
    assert deduplicate("") == ""
    assert deduplicate(None) == ""


def test_preserve_whitespace():
    """测试保留空白"""
    text = "第一行\n\n第二行\n\n第一行"
    result = deduplicate(text)
    assert "\n" in result


def test_case_insensitive():
    """测试大小写不敏感"""
    text = "Hello World\nhello world\nHELLO WORLD"
    result = deduplicate(text)
    assert result.count("Hello") == 1
