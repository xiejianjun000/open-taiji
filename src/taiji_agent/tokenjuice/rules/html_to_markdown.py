"""HTML 转 Markdown 规则"""
import re
from html.parser import HTMLParser
from typing import Optional


class MarkdownHTMLParser(HTMLParser):
    """HTML 转 Markdown 解析器"""

    def __init__(self):
        super().__init__()
        self.output: list[str] = []
        self.tag_stack: list[str] = []
        self._pending_link: Optional[str] = None
        self._list_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        self.tag_stack.append(tag)
        attrs_dict = dict(attrs)

        if tag == "p":
            if self.output and not self.output[-1].endswith("\n\n"):
                self.output.append("\n\n")
        elif tag == "br":
            self.output.append("\n")
        elif tag == "h1":
            self.output.append("# ")
        elif tag == "h2":
            self.output.append("## ")
        elif tag == "h3":
            self.output.append("### ")
        elif tag == "h4":
            self.output.append("#### ")
        elif tag == "h5":
            self.output.append("##### ")
        elif tag == "h6":
            self.output.append("###### ")
        elif tag == "li":
            indent = "  " * self._list_depth
            self.output.append(f"{indent}- ")
        elif tag == "ul":
            self._list_depth += 1
        elif tag == "ol":
            self._list_depth += 1
        elif tag == "a":
            self.output.append("[")
            self._pending_link = attrs_dict.get("href", "")
        elif tag == "img":
            alt = attrs_dict.get("alt", "")
            self.output.append(f"![{alt}]")
        elif tag in ("strong", "b"):
            self.output.append("**")
        elif tag in ("em", "i"):
            self.output.append("*")
        elif tag == "code":
            if self.tag_stack[-2:-1] and self.tag_stack[-2] not in ("pre", "code"):
                self.output.append("`")
        elif tag == "pre":
            self.output.append("\n```\n")
        elif tag == "blockquote":
            self.output.append("> ")
        elif tag == "hr":
            self.output.append("\n---\n")
        elif tag == "div":
            if self.output and not self.output[-1].endswith("\n"):
                self.output.append("\n")

    def handle_endtag(self, tag: str):
        if not self.tag_stack or self.tag_stack[-1] != tag:
            return

        self.tag_stack.pop()

        if tag == "a" and self._pending_link:
            self.output.append(f"]({self._pending_link})")
            self._pending_link = None
        elif tag == "strong" or tag == "b":
            self.output.append("**")
        elif tag == "em" or tag == "i":
            self.output.append("*")
        elif tag == "code":
            if len(self.output) >= 2:
                prev = self.output[-2] if self.output[-1] == "`" else ""
                if prev and prev not in ("```", "\n```", "\n"):
                    self.output.append("`")
        elif tag == "pre":
            self.output.append("\n```\n")
        elif tag == "ol" or tag == "ul":
            self._list_depth = max(0, self._list_depth - 1)

    def handle_data(self, data: str):
        self.output.append(data)

    def get_result(self) -> str:
        result = "".join(self.output)
        result = re.sub(r"\n{3,}", "\n\n", result)
        result = re.sub(r" +\n", "\n", result)
        return result.strip()


def html_to_markdown(html: str) -> str:
    """
    将 HTML 转换为 Markdown

    Args:
        html: HTML 字符串

    Returns:
        str: Markdown 字符串
    """
    if not html:
        return ""

    parser = MarkdownHTMLParser()
    try:
        parser.feed(html)
        return parser.get_result()
    except Exception:
        return html
