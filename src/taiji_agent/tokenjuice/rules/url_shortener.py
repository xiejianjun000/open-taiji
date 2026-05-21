"""URL 缩短规则"""
import re
from urllib.parse import urlparse
from typing import Optional


def shorten_url(url: str, max_length: int = 50) -> str:
    """
    缩短单个 URL

    Args:
        url: 原始 URL
        max_length: 最大长度

    Returns:
        str: 缩短后的 URL 或 [链接] 占位符
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return url

        if parsed.scheme in ("localhost", "file"):
            return url

        if len(url) <= max_length:
            return url

        display = parsed.netloc + parsed.path
        if len(display) > max_length:
            display = display[: max_length - 3] + "..."

        return f"[链接]({display})"
    except Exception:
        return "[链接]"


def shorten_urls(text: str) -> str:
    """
    缩短文本中的所有 URL

    Args:
        text: 包含 URL 的文本

    Returns:
        str: URL 被缩短的文本
    """
    if not text:
        return ""

    url_pattern = re.compile(
        r"https?://[^\s<>\[\]\"'\(\)]+", re.IGNORECASE
    )

    def replace_url(match: re.Match) -> str:
        return shorten_url(match.group(0))

    return url_pattern.sub(replace_url, text)
