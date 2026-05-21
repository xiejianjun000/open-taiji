"""TokenJuice HTML 转 Markdown 规则测试"""
import pytest
from taiji_agent.tokenjuice.rules.html_to_markdown import html_to_markdown


def test_simple_html_conversion():
    """测试简单 HTML 转换"""
    input_html = "<p>Hello <b>World</b></p>"
    expected = "Hello **World**"
    assert html_to_markdown(input_html) == expected


def test_complex_html():
    """测试复杂 HTML"""
    input_html = """
    <div class='container'>
        <h1>Title</h1>
        <p>Paragraph with <a href='http://example.com'>link</a></p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
    </div>
    """
    result = html_to_markdown(input_html)
    assert "# Title" in result
    assert "- Item 1" in result
    assert "[link]" in result


def test_nested_tags():
    """测试嵌套标签"""
    input_html = "<div><p><span>Nested</span></p></div>"
    result = html_to_markdown(input_html)
    assert "Nested" in result


def test_empty_html():
    """测试空 HTML"""
    assert html_to_markdown("") == ""
    assert html_to_markdown(None) == ""


def test_headings():
    """测试标题标签"""
    assert html_to_markdown("<h1>H1</h1>") == "# H1"
    assert html_to_markdown("<h2>H2</h2>") == "## H2"
    assert html_to_markdown("<h3>H3</h3>") == "### H3"


def test_paragraphs():
    """测试段落标签"""
    result = html_to_markdown("<p>First</p><p>Second</p>")
    assert "First" in result
    assert "Second" in result
