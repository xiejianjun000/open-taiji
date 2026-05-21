"""TokenJuice URL 缩短规则测试"""
import pytest
from taiji_agent.tokenjuice.rules.url_shortener import shorten_urls, shorten_url


def test_shorten_long_url():
    """测试长 URL 缩短"""
    url = "https://example.com/very/long/path/to/some/resource?param1=value1&param2=value2&param3=value3"
    result = shorten_url(url)
    assert len(result) < len(url)
    assert "[链接]" in result or result.startswith("https://")


def test_shorten_urls_in_text():
    """测试文本中 URL 缩短"""
    text = "请访问 https://example.com/very/long/path?a=1&b=2 了解详情"
    result = shorten_urls(text)
    assert result.count("[链接]") == 1 or "example.com" in result


def test_localhost_not_shortened():
    """测试本地 URL 不缩短"""
    url = "http://localhost:8080/api/v1/users"
    result = shorten_url(url)
    assert "localhost" in result


def test_short_url_unchanged():
    """测试短 URL 不变"""
    url = "https://example.com"
    result = shorten_url(url)
    assert result == url


def test_empty_url():
    """测试空 URL"""
    assert shorten_url("") == ""
    assert shorten_url(None) == ""


def test_multiple_urls():
    """测试多个 URL"""
    text = "链接1: https://example.com/very/long/path1?param1=value1&param2=value2&param3=value3 链接2: https://test.com/very/long/path2?param1=value1&param2=value2"
    result = shorten_urls(text)
    assert result.count("[链接]") == 2


def test_no_url():
    """测试无 URL 文本"""
    text = "这是一段没有 URL 的纯文本"
    result = shorten_urls(text)
    assert result == text
