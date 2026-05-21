"""TokenJuice 主压缩引擎"""
from dataclasses import dataclass
from typing import Optional

from .rules.html_to_markdown import html_to_markdown
from .rules.url_shortener import shorten_urls
from .rules.deduplicator import deduplicate
from .rules.cjk_preserver import preserve_cjk

TRIGGER_THRESHOLD_TOKENS = 3000


@dataclass
class CompressedContent:
    """压缩后的内容"""
    text: str
    tokens: int
    was_summarized: bool = False
    original_tokens: Optional[int] = None


class TokenJuiceCompressor:
    """TokenJuice 压缩引擎"""

    def __init__(self, llm_provider=None):
        """
        初始化压缩引擎

        Args:
            llm_provider: LLM 提供商（用于摘要）
        """
        self.llm_provider = llm_provider

    def compress(
        self, content: str, context: str = ""
    ) -> CompressedContent:
        """
        压缩内容

        Args:
            content: 原始内容
            context: 当前上下文

        Returns:
            CompressedContent: 压缩后的内容
        """
        if not content:
            return CompressedContent(text="", tokens=0)

        original_tokens = self._estimate_tokens(content)

        text = content

        text = html_to_markdown(text)

        text = shorten_urls(text)

        text = deduplicate(text)

        text = preserve_cjk(text)

        text = text.strip()

        was_summarized = False
        if original_tokens > TRIGGER_THRESHOLD_TOKENS and self.llm_provider:
            text, was_summarized = self._summarize_if_needed(text, context)
            if was_summarized:
                text = preserve_cjk(text)

        return CompressedContent(
            text=text,
            tokens=self._estimate_tokens(text),
            was_summarized=was_summarized,
            original_tokens=original_tokens
        )

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        return len(text) // 4

    def _summarize_if_needed(
        self, content: str, context: str
    ) -> tuple[str, bool]:
        """LLM 摘要（如果需要）"""
        if not self.llm_provider:
            return content, False

        try:
            prompt = f"""请将以下内容压缩为关键摘要，保留重要信息：

上下文: {context}

内容:
{content}

摘要（保留关键信息，不要遗漏重要细节）:"""

            response = self.llm_provider.chat([
                {"role": "user", "content": prompt}
            ])

            summarized = response.content if response.content else content
            return summarized, True
        except Exception:
            return content, False

    def estimate_savings(
        self, original: str, compressed: str
    ) -> float:
        """估算节省比例"""
        original_tokens = self._estimate_tokens(original)
        compressed_tokens = self._estimate_tokens(compressed)

        if original_tokens == 0:
            return 0.0

        return (1 - compressed_tokens / original_tokens) * 100
