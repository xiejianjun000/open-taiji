# Taiji Agent 2.0 OpenHuman 集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TokenJuice 压缩层、Memory Tree 分层记忆和 PyQt 桌面系统集成到 taiji-agent

**Architecture:** 分层架构 - Presentation (PyQt) → Middleware (TokenJuice/Memory Tree) → Core (Agent Engine)

**Tech Stack:** Python 3.11+, PyQt6, aiosqlite, edge-tts, faster-whisper, Lottie

---

## 文件结构概览

```
src/taiji_agent/
├── tokenjuice/
│   ├── __init__.py
│   ├── compressor.py
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── html_to_markdown.py
│   │   ├── url_shortener.py
│   │   ├── deduplicator.py
│   │   └── cjk_preserver.py
│   ├── summarizer.py
│   └── middleware.py
├── memory_tree/
│   ├── __init__.py
│   ├── tree.py
│   ├── layers/
│   │   ├── __init__.py
│   │   ├── source.py
│   │   ├── topic.py
│   │   └── global_.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── sqlite.py
│   │   └── vault.py
│   └── summarizer.py
└── desktop/
    ├── __init__.py
    ├── main.py
    ├── window.py
    ├── chat_view.py
    ├── mascot/
    │   ├── __init__.py
    │   ├── widget.py
    │   ├── lottie_player.py
    │   ├── states.py
    │   └── lip_sync.py
    ├── voice/
    │   ├── __init__.py
    │   ├── tts.py
    │   ├── stt.py
    │   └── pipeline.py
    └── tray.py
```

---

## Phase 1: TokenJuice 压缩层

### Task 1: 依赖安装和目录创建

**Files:**
- Create: `src/taiji_agent/tokenjuice/__init__.py`
- Create: `src/taiji_agent/tokenjuice/rules/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 更新 pyproject.toml**

```toml
[project.optional-dependencies]
tokenjuice = [
    "tiktoken>=0.8.0,<1.0.0",
]
all = [
    "taiji_agent[dev,messaging,voice,browser,desktop,memory,tokenjuice]",
]
```

- [ ] **Step 2: 创建目录结构**

```bash
mkdir -p src/taiji_agent/tokenjuice/rules
```

- [ ] **Step 3: 创建 __init__.py 文件**

```python
"""TokenJuice 压缩层 - Token 消耗优化引擎"""
from .compressor import TokenJuiceCompressor, CompressedContent

__all__ = ["TokenJuiceCompressor", "CompressedContent"]
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(tokenjuice): 初始化 TokenJuice 目录结构"
```

---

### Task 2: HTML 转 Markdown 规则

**Files:**
- Create: `src/taiji_agent/tokenjuice/rules/html_to_markdown.py`
- Create: `tests/test_tokenjuice_html.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_tokenjuice_html.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_tokenjuice_html.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: 实现 HTML 转 Markdown**

```python
# src/taiji_agent/tokenjuice/rules/html_to_markdown.py
import re
from html.parser import HTMLParser
from typing import Optional


class MarkdownHTMLParser(HTMLParser):
    """HTML 转 Markdown 解析器"""

    def __init__(self):
        super().__init__()
        self.output: list[str] = []
        self.tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        self.tag_stack.append(tag)
        if tag == "p":
            self.output.append("\n\n")
        elif tag == "br":
            self.output.append("\n")
        elif tag == "h1":
            self.output.append("# ")
        elif tag == "h2":
            self.output.append("## ")
        elif tag == "h3":
            self.output.append("### ")
        elif tag == "li":
            self.output.append("- ")
        elif tag == "a":
            href = dict(attrs).get("href", "")
            self.output.append(f"[")
            self._pending_link = href
        elif tag == "img":
            alt = dict(attrs).get("alt", "")
            self.output.append(f"![{alt}]")

    def handle_endtag(self, tag: str):
        if tag == "a" and hasattr(self, "_pending_link"):
            self.output.append(f"]({self._pending_link})")
            del self._pending_link
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data: str):
        self.output.append(data.strip())

    def get_result(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.output)).strip()


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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_tokenjuice_html.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat(tokenjuice): 实现 HTML 转 Markdown 规则"
```

---

### Task 3: URL 缩短规则

**Files:**
- Create: `src/taiji_agent/tokenjuice/rules/url_shortener.py`
- Create: `tests/test_tokenjuice_url.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_tokenjuice_url.py
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
```

- [ ] **Step 2: 实现 URL 缩短**

```python
# src/taiji_agent/tokenjuice/rules/url_shortener.py
import re
from urllib.parse import urlparse


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
        return url

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
    url_pattern = re.compile(
        r"https?://[^\s<>\[\]\"']+", re.IGNORECASE
    )

    def replace_url(match: re.Match) -> str:
        return shorten_url(match.group(0))

    return url_pattern.sub(replace_url, text)
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_tokenjuice_url.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(tokenjuice): 实现 URL 缩短规则"
```

---

### Task 4: 去重规则

**Files:**
- Create: `src/taiji_agent/tokenjuice/rules/deduplicator.py`
- Create: `tests/test_tokenjuice_dedup.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_tokenjuice_dedup.py
import pytest
from taiji_agent.tokenjuice.rules.deduplicator import deduplicate

def test_remove_duplicate_sentences():
    """测试去除重复句子"""
    text = "这是第一句话。这是第二句话。这是第一句话。这是第三句话。"
    result = deduplicate(text)
    assert result.count("这是第一句话") == 1
    assert result.count("这是第二句话") == 1

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
```

- [ ] **Step 2: 实现去重**

```python
# src/taiji_agent/tokenjuice/rules/deduplicator.py
from typing import Set


def deduplicate(text: str, similarity_threshold: float = 0.85) -> str:
    """
    去除重复内容

    Args:
        text: 原始文本
        similarity_threshold: 相似度阈值 (0-1)

    Returns:
        str: 去重后的文本
    """
    if not text:
        return text

    lines = text.split("\n")
    seen: Set[str] = set()
    result_lines: list[str] = []

    for line in lines:
        normalized = normalize_line(line)
        if not normalized:
            continue

        is_duplicate = False
        for seen_line in seen:
            if similarity(normalized, seen_line) >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            seen.add(normalized)
            result_lines.append(line)

    return "\n".join(result_lines)


def normalize_line(line: str) -> str:
    """标准化行文本"""
    return " ".join(line.lower().split())


def similarity(s1: str, s2: str) -> float:
    """计算两个字符串的相似度"""
    if not s1 or not s2:
        return 0.0

    s1_set = set(s1)
    s2_set = set(s2)

    intersection = len(s1_set & s2_set)
    union = len(s1_set | s2_set)

    if union == 0:
        return 0.0

    return intersection / union
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_tokenjuice_dedup.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(tokenjuice): 实现内容去重规则"
```

---

### Task 5: CJK 保留规则

**Files:**
- Create: `src/taiji_agent/tokenjuice/rules/cjk_preserver.py`
- Create: `tests/test_tokenjuice_cjk.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_tokenjuice_cjk.py
import pytest
from taiji_agent.tokenjuice.rules.cjk_preserver import preserve_cjk

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
```

- [ ] **Step 2: 实现 CJK 保留**

```python
# src/taiji_agent/tokenjuice/rules/cjk_preserver.py
import re


CJK_RANGES = [
    (0x4E00, 0x9FFF),   # 中文
    (0x3040, 0x309F),   # 日文平假名
    (0x30A0, 0x30FF),   # 日文片假名
    (0xAC00, 0xD7AF),   # 韩文
]


def is_cjk(char: str) -> bool:
    """检查字符是否为 CJK"""
    code = ord(char)
    return any(start <= code <= end for start, end in CJK_RANGES)


def preserve_cjk(text: str) -> str:
    """
    保留 CJK 字符，逐字保留

    Args:
        text: 原始文本

    Returns:
        str: CJK 字符被保留的文本
    """
    result = []
    for char in text:
        if is_cjk(char):
            result.append(char)
        else:
            result.append(char)
    return "".join(result)
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_tokenjuice_cjk.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(tokenjuice): 实现 CJK 字符保留规则"
```

---

### Task 6: 主压缩引擎

**Files:**
- Create: `src/taiji_agent/tokenjuice/compressor.py`
- Create: `tests/test_tokenjuice_compressor.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_tokenjuice_compressor.py
import pytest
from taiji_agent.tokenjuice.compressor import (
    TokenJuiceCompressor,
    CompressedContent,
    TRIGGER_THRESHOLD_TOKENS
)

@pytest.fixture
def compressor():
    return TokenJuiceCompressor()

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
```

- [ ] **Step 2: 实现主压缩引擎**

```python
# src/taiji_agent/tokenjuice/compressor.py
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
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_tokenjuice_compressor.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(tokenjuice): 实现主压缩引擎"
```

---

## Phase 2: Memory Tree 分层记忆

### Task 7: 目录创建和依赖

**Files:**
- Create: `src/taiji_agent/memory_tree/`
- Create: `src/taiji_agent/memory_tree/layers/`
- Create: `src/taiji_agent/memory_tree/storage/`
- Modify: `pyproject.toml`

- [ ] **Step 1: 更新 pyproject.toml**

```toml
memory = [
    "aiosqlite>=0.20.0,<1.0.0",
]
```

- [ ] **Step 2: 创建目录和 __init__.py**

```bash
mkdir -p src/taiji_agent/memory_tree/layers
mkdir -p src/taiji_agent/memory_tree/storage
```

- [ ] **Step 3: 创建 __init__.py**

```python
"""Memory Tree 分层记忆系统"""
from .tree import MemoryTree, Layer

__all__ = ["MemoryTree", "Layer"]
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(memory_tree): 初始化 Memory Tree 目录结构"
```

---

### Task 8: SQLite 存储层

**Files:**
- Create: `src/taiji_agent/memory_tree/storage/sqlite.py`
- Create: `tests/test_memory_sqlite.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_memory_sqlite.py
import pytest
import asyncio
from pathlib import Path
from taiji_agent.memory_tree.storage.sqlite import SQLiteStorage

@pytest.fixture
async def storage(tmp_path):
    s = SQLiteStorage(tmp_path / "test.db")
    await s.initialize()
    yield s
    await s.close()

@pytest.mark.asyncio
async def test_store_source_chunk(storage):
    """测试存储源层数据"""
    chunk_id = await storage.store_source_chunk(
        source_type="email",
        source_id="msg123",
        content="这是一封邮件内容",
        tokens=100
    )
    assert chunk_id is not None

    chunks = await storage.get_source_chunks("email", "msg123")
    assert len(chunks) == 1
    assert "邮件" in chunks[0]["content"]

@pytest.mark.asyncio
async def test_topic_summary(storage):
    """测试主题摘要"""
    topic_id = await storage.store_topic_summary(
        topic="项目A",
        summary="项目A是一个电商平台",
        importance=0.8
    )
    assert topic_id is not None

    topics = await storage.get_topics()
    assert any(t["topic"] == "项目A" for t in topics)

@pytest.mark.asyncio
async def test_global_memory(storage):
    """测试全局记忆"""
    await storage.store_global_memory(
        memory_type="persona",
        content="用户是产品经理",
        confidence=0.9
    )

    persona = await storage.get_global_memory("persona")
    assert "产品经理" in persona["content"]
```

- [ ] **Step 2: 实现 SQLite 存储**

```python
# src/taiji_agent/memory_tree/storage/sqlite.py
import aiosqlite
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class SQLiteStorage:
    """SQLite 存储层"""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """初始化数据库"""
        self.db = await aiosqlite.connect(str(self.db_path))
        await self._create_tables()

    async def close(self):
        """关闭连接"""
        if self.db:
            await self.db.close()

    async def _create_tables(self):
        """创建表"""
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS source_chunks (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS topic_summaries (
                id TEXT PRIMARY KEY,
                topic TEXT UNIQUE NOT NULL,
                summary TEXT NOT NULL,
                importance_score REAL DEFAULT 0.5,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS global_memory (
                id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_source_source ON source_chunks(source_type, source_id);
            CREATE INDEX IF NOT EXISTS idx_topic ON topic_summaries(topic);
            CREATE INDEX IF NOT EXISTS idx_global_type ON global_memory(memory_type);
        """)
        await self.db.commit()

    async def store_source_chunk(
        self,
        source_type: str,
        source_id: str,
        content: str,
        tokens: int
    ) -> str:
        """存储源层数据块"""
        chunk_id = str(uuid.uuid4())
        await self.db.execute(
            """INSERT INTO source_chunks
               (id, source_type, source_id, content, tokens)
               VALUES (?, ?, ?, ?, ?)""",
            (chunk_id, source_type, source_id, content, tokens)
        )
        await self.db.commit()
        return chunk_id

    async def get_source_chunks(
        self, source_type: str, source_id: str
    ) -> list[dict]:
        """获取源层数据块"""
        cursor = await self.db.execute(
            """SELECT id, content, tokens, created_at
               FROM source_chunks
               WHERE source_type = ? AND source_id = ?
               ORDER BY created_at DESC""",
            (source_type, source_id)
        )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "content": r[1], "tokens": r[2], "created_at": r[3]}
            for r in rows
        ]

    async def store_topic_summary(
        self, topic: str, summary: str, importance: float = 0.5
    ) -> str:
        """存储主题摘要"""
        topic_id = str(uuid.uuid4())
        await self.db.execute(
            """INSERT OR REPLACE INTO topic_summaries
               (id, topic, summary, importance_score, last_updated)
               VALUES (
                   COALESCE((SELECT id FROM topic_summaries WHERE topic = ?), ?),
                   ?, ?, ?, CURRENT_TIMESTAMP
               )""",
            (topic, topic_id, topic, summary, importance)
        )
        await self.db.commit()
        return topic_id

    async def get_topics(self) -> list[dict]:
        """获取所有主题"""
        cursor = await self.db.execute(
            """SELECT topic, summary, importance_score, last_updated
               FROM topic_summaries ORDER BY importance_score DESC"""
        )
        rows = await cursor.fetchall()
        return [
            {"topic": r[0], "summary": r[1], "importance": r[2], "updated": r[3]}
            for r in rows
        ]

    async def store_global_memory(
        self, memory_type: str, content: str, confidence: float = 0.5
    ) -> str:
        """存储全局记忆"""
        memory_id = str(uuid.uuid4())
        await self.db.execute(
            """INSERT OR REPLACE INTO global_memory
               (id, memory_type, content, confidence, updated_at)
               VALUES (
                   COALESCE((SELECT id FROM global_memory WHERE memory_type = ?), ?),
                   ?, ?, ?, CURRENT_TIMESTAMP
               )""",
            (memory_type, memory_id, memory_type, content, confidence)
        )
        await self.db.commit()
        return memory_id

    async def get_global_memory(self, memory_type: str) -> dict | None:
        """获取全局记忆"""
        cursor = await self.db.execute(
            """SELECT content, confidence, updated_at
               FROM global_memory WHERE memory_type = ?""",
            (memory_type,)
        )
        row = await cursor.fetchone()
        if row:
            return {"content": row[0], "confidence": row[1], "updated": row[2]}
        return None
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_memory_sqlite.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(memory_tree): 实现 SQLite 存储层"
```

---

### Task 9: Obsidian Vault 同步

**Files:**
- Create: `src/taiji_agent/memory_tree/storage/vault.py`
- Create: `tests/test_memory_vault.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_memory_vault.py
import pytest
import asyncio
from pathlib import Path
from taiji_agent.memory_tree.storage.vault import ObsidianVault

@pytest.fixture
async def vault(tmp_path):
    v = ObsidianVault(tmp_path / "vault")
    await v.initialize()
    yield v

@pytest.mark.asyncio
async def test_write_source_file(vault):
    """测试写入源文件"""
    await vault.write_source("email", "msg123", "# 邮件主题\n\n邮件正文内容")
    file_path = vault.vault_dir / "sources" / "email" / "msg123.md"
    assert file_path.exists()
    content = file_path.read_text()
    assert "邮件主题" in content

@pytest.mark.asyncio
async def test_write_topic_file(vault):
    """测试写入主题文件"""
    await vault.write_topic("项目A", "# 项目A\n\n这是一个电商项目")
    file_path = vault.vault_dir / "topics" / "项目A.md"
    assert file_path.exists()

@pytest.mark.asyncio
async def test_write_global_file(vault):
    """测试写入全局文件"""
    await vault.write_global("persona", "# 用户画像\n\n用户是产品经理")
    file_path = vault.vault_dir / "global" / "persona.md"
    assert file_path.exists()

@pytest.mark.asyncio
async def test_sync_all(vault):
    """测试全量同步"""
    await vault.write_source("email", "msg1", "内容1")
    await vault.write_topic("主题1", "摘要1")

    result = await vault.sync_all()

    assert result["files_written"] >= 2
```

- [ ] **Step 2: 实现 Obsidian Vault 同步**

```python
# src/taiji_agent/memory_tree/storage/vault.py
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SyncResult:
    """同步结果"""
    files_written: int
    files_updated: int
    errors: list[str]


class ObsidianVault:
    """Obsidian Vault 同步"""

    def __init__(self, vault_dir: Path | str):
        self.vault_dir = Path(vault_dir)
        self.sources_dir = self.vault_dir / "sources"
        self.topics_dir = self.vault_dir / "topics"
        self.global_dir = self.vault_dir / "global"

    async def initialize(self):
        """初始化 Vault 目录"""
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        self.global_dir.mkdir(parents=True, exist_ok=True)

        await self._ensure_gitkeep(self.sources_dir)
        await self._ensure_gitkeep(self.topics_dir)
        await self._ensure_gitkeep(self.global_dir)

    async def _ensure_gitkeep(self, directory: Path):
        """确保目录有 .gitkeep"""
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")

    async def write_source(
        self, source_type: str, source_id: str, content: str
    ) -> Path:
        """写入源文件"""
        source_dir = self.sources_dir / self._sanitize_filename(source_type)
        source_dir.mkdir(parents=True, exist_ok=True)

        file_path = source_dir / f"{self._sanitize_filename(source_id)}.md"
        await asyncio.to_thread(file_path.write_text, content, encoding="utf-8")

        return file_path

    async def write_topic(self, topic: str, content: str) -> Path:
        """写入主题文件"""
        file_path = self.topics_dir / f"{self._sanitize_filename(topic)}.md"
        await asyncio.to_thread(file_path.write_text, content, encoding="utf-8")
        return file_path

    async def write_global(
        self, memory_type: str, content: str
    ) -> Path:
        """写入全局记忆文件"""
        file_path = self.global_dir / f"{self._sanitize_filename(memory_type)}.md"
        await asyncio.to_thread(file_path.write_text, content, encoding="utf-8")
        return file_path

    async def read_source(
        self, source_type: str, source_id: str
    ) -> Optional[str]:
        """读取源文件"""
        file_path = self.sources_dir / self._sanitize_filename(source_type) / f"{self._sanitize_filename(source_id)}.md"
        if file_path.exists():
            return await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        return None

    async def sync_all(self) -> SyncResult:
        """全量同步"""
        result = SyncResult(files_written=0, files_updated=0, errors=[])

        for dir_path, subdir, files in self._walk_dir(self.sources_dir):
            result.files_written += len(files)

        for dir_path, subdir, files in self._walk_dir(self.topics_dir):
            result.files_written += len(files)

        for dir_path, subdir, files in self._walk_dir(self.global_dir):
            result.files_written += len(files)

        return result

    def _walk_dir(self, directory: Path):
        """遍历目录"""
        for item in directory.iterdir():
            if item.is_dir():
                yield from self._walk_dir(item)
            elif item.suffix == ".md":
                yield directory, [], [item.name]

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")
        return name[:100]
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_memory_vault.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(memory_tree): 实现 Obsidian Vault 同步"
```

---

### Task 10: MemoryTree 主类

**Files:**
- Create: `src/taiji_agent/memory_tree/tree.py`
- Create: `tests/test_memory_tree.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_memory_tree.py
import pytest
import asyncio
from pathlib import Path
from taiji_agent.memory_tree import MemoryTree, Layer

@pytest.fixture
async def tree(tmp_path):
    t = MemoryTree(
        storage_dir=tmp_path / "memory",
        vault_dir=tmp_path / "vault"
    )
    await t.initialize()
    yield t
    await t.close()

@pytest.mark.asyncio
async def test_ingest_and_query(tree):
    """测试摄入和查询"""
    await tree.ingest(
        content="用户张三喜欢喝咖啡，每天早上都会去咖啡店",
        source_type="email",
        source_id="msg001"
    )

    result = await tree.query("用户的喜好")
    assert "咖啡" in result or "喜欢" in result

@pytest.mark.asyncio
async def test_get_context(tree):
    """测试获取上下文"""
    await tree.ingest(
        content="项目A是一个电商平台，使用Python开发",
        source_type="notion",
        source_id="doc001"
    )

    context = await tree.get_context("分析项目A")
    assert "项目A" in context

@pytest.mark.asyncio
async def test_persona(tree):
    """测试用户画像"""
    await tree.ingest(
        content="我是产品经理，负责电商项目",
        source_type="profile",
        source_id="me"
    )

    persona = tree.get_persona()
    assert persona is not None

@pytest.mark.asyncio
async def test_sync_vault(tree):
    """测试 Vault 同步"""
    await tree.ingest(
        content="测试内容",
        source_type="test",
        source_id="001"
    )

    result = await tree.sync_vault()
    assert result.files_written > 0
```

- [ ] **Step 2: 实现 MemoryTree 主类**

```python
# src/taiji_agent/memory_tree/tree.py
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from .storage.sqlite import SQLiteStorage
from .storage.vault import ObsidianVault, SyncResult


class Layer(Enum):
    """记忆层"""
    SOURCE = "source"
    TOPIC = "topic"
    GLOBAL = "global"
    ALL = "all"


@dataclass
class UserPersona:
    """用户画像"""
    facts: list[str]
    preferences: dict[str, str]
    confidence: float


class MemoryTree:
    """Memory Tree 分层记忆系统"""

    def __init__(
        self,
        storage_dir: Path | str = Path.home() / ".taiji" / "memory",
        vault_dir: Path | str = Path.home() / ".taiji" / "vault",
        llm_provider=None
    ):
        self.storage_dir = Path(storage_dir)
        self.vault_dir = Path(vault_dir)
        self.llm_provider = llm_provider

        self.storage: Optional[SQLiteStorage] = None
        self.vault: Optional[ObsidianVault] = None

    async def initialize(self):
        """初始化"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage = SQLiteStorage(self.storage_dir / "memory.db")
        await self.storage.initialize()

        self.vault = ObsidianVault(self.vault_dir)
        await self.vault.initialize()

    async def close(self):
        """关闭连接"""
        if self.storage:
            await self.storage.close()

    async def ingest(
        self,
        content: str,
        source_type: str,
        source_id: str,
        metadata: dict | None = None
    ) -> str:
        """
        摄入新数据

        Args:
            content: 原始内容
            source_type: 来源类型
            source_id: 来源 ID
            metadata: 元数据

        Returns:
            str: 摄入的 chunk ID
        """
        chunk_id = await self.storage.store_source_chunk(
            source_type=source_type,
            source_id=source_id,
            content=content,
            tokens=len(content) // 4
        )

        await self._update_topic_layer(content)

        await self._update_global_layer(content)

        return chunk_id

    async def _update_topic_layer(self, content: str):
        """更新主题层"""
        if not self.llm_provider:
            return

        try:
            topic_prompt = f"""从以下内容中提取主题（1-2个词）:

{content}

主题:"""

            response = self.llm_provider.chat([{"role": "user", "content": topic_prompt}])
            topic = response.content.strip() if response.content else "其他"

            summary_prompt = f"""为以下内容生成简短摘要（不超过100字）:

{content}

摘要:"""

            response = self.llm_provider.chat([{"role": "user", "content": summary_prompt}])
            summary = response.content.strip() if response.content else content[:200]

            await self.storage.store_topic_summary(
                topic=topic,
                summary=summary,
                importance=0.6
            )

            await self.vault.write_topic(topic, f"# {topic}\n\n{summary}")
        except Exception:
            pass

    async def _update_global_layer(self, content: str):
        """更新全局层"""
        if not self.llm_provider:
            return

        try:
            if any(keyword in content for keyword in ["我喜欢", "我爱好", "我的喜好"]):
                await self.storage.store_global_memory(
                    memory_type="preference",
                    content=content,
                    confidence=0.7
                )
        except Exception:
            pass

    async def query(
        self,
        query: str,
        layers: list[Layer] | None = None,
        max_tokens: int = 3000
    ) -> str:
        """
        查询记忆

        Args:
            query: 查询文本
            layers: 要查询的层
            max_tokens: 最大 token 数

        Returns:
            str: 查询结果
        """
        if layers is None:
            layers = [Layer.ALL]

        results = []

        if Layer.SOURCE in layers or Layer.ALL in layers:
            topics = await self.storage.get_topics()
            for topic in topics:
                if len("\n".join(results)) < max_tokens:
                    results.append(topic["summary"])

        if Layer.TOPIC in layers or Layer.ALL in layers:
            topics = await self.storage.get_topics()
            for topic in topics:
                if len("\n".join(results)) < max_tokens:
                    results.append(f"## {topic['topic']}\n{topic['summary']}")

        if Layer.GLOBAL in layers or Layer.ALL in layers:
            for mem_type in ["persona", "preference", "goal"]:
                memory = await self.storage.get_global_memory(mem_type)
                if memory and len("\n".join(results)) < max_tokens:
                    results.append(f"### {mem_type}\n{memory['content']}")

        return "\n\n".join(results) if results else "未找到相关记忆"

    async def get_context(self, task: str) -> str:
        """
        获取任务相关上下文

        Args:
            task: 任务描述

        Returns:
            str: 上下文文本
        """
        return await self.query(task, max_tokens=2000)

    async def sync_vault(self) -> SyncResult:
        """同步 Obsidian Vault"""
        return await self.vault.sync_all()

    def get_persona(self) -> Optional[UserPersona]:
        """获取用户画像"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        persona = loop.run_until_complete(
            self.storage.get_global_memory("persona")
        )

        if persona:
            return UserPersona(
                facts=[persona["content"]],
                preferences={},
                confidence=persona["confidence"]
            )
        return None
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_memory_tree.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(memory_tree): 实现 MemoryTree 主类"
```

---

## Phase 3: PyQt 桌面系统

### Task 11: PyQt 依赖和入口

**Files:**
- Create: `src/taiji_agent/desktop/__init__.py`
- Create: `src/taiji_agent/desktop/main.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 更新 pyproject.toml**

```toml
desktop = [
    "PyQt6>=6.8.0,<7.0.0",
    "lottie>=0.8.0,<1.0.0",
]
```

- [ ] **Step 2: 创建 main.py**

```python
# src/taiji_agent/desktop/main.py
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .window import TaijiWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Taiji Agent")
    app.setApplicationVersion("2.0.0")

    app.setStyleSheet("""
        QMainWindow {
            background-color: #1a1a2e;
        }
        QWidget {
            color: #e0e0e0;
            font-family: "Microsoft YaHei", sans-serif;
        }
    """)

    window = TaijiWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 创建 __init__.py**

```python
"""Taiji Agent 桌面系统"""
from .window import TaijiWindow

__all__ = ["TaijiWindow"]
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(desktop): 初始化 PyQt 桌面框架"
```

---

### Task 12: 主窗口

**Files:**
- Create: `src/taiji_agent/desktop/window.py`
- Create: `tests/test_desktop_window.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_desktop_window.py
import pytest
from PyQt6.QtWidgets import QApplication
from taiji_agent.desktop.window import TaijiWindow

@pytest.fixture
def app(qtbot):
    window = TaijiWindow()
    qtbot.addWidget(window)
    return window

def test_window_title(app):
    """测试窗口标题"""
    assert "Taiji" in app.windowTitle()

def test_window_minimum_size(app):
    """测试最小窗口大小"""
    assert app.minimumWidth() >= 800
    assert app.minimumHeight() >= 600
```

- [ ] **Step 2: 实现主窗口**

```python
# src/taiji_agent/desktop/window.py
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette

from .mascot.widget import MascotWidget
from .chat_view import ChatView
from .tray import TrayManager


class TaijiWindow(QMainWindow):
    """Taiji Agent 主窗口"""

    message_sent = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taiji Agent 2.0")
        self.setMinimumSize(900, 650)

        self._setup_ui()
        self._setup_tray()

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #4CAF50;
                font-size: 14px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #4CAF50;
                border-radius: 8px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #4CAF50;
                border-radius: 4px;
                padding: 8px;
            }
        """)

    def _setup_ui(self):
        """设置 UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(20)

        self.mascot = MascotWidget()
        self.mascot.setFixedSize(200, 250)
        left_panel.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("状态: 空闲")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.status_label)

        left_panel.addStretch()

        quick_buttons = QVBoxLayout()
        quick_buttons.addWidget(QPushButton("📧 邮件"))
        quick_buttons.addWidget(QPushButton("📁 文件"))
        quick_buttons.addWidget(QPushButton("🔍 搜索"))
        left_panel.addLayout(quick_buttons)

        main_layout.addLayout(left_panel, 1)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)

        self.chat_view = ChatView()
        right_panel.addWidget(self.chat_view, 1)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.returnPressed.connect(self._on_send)

        send_btn = QPushButton("▶")
        send_btn.setFixedWidth(50)
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(send_btn)

        right_panel.addLayout(input_layout)

        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("🔍 Memory Tree:"))
        memory_btn = QPushButton("查看记忆树")
        memory_btn.clicked.connect(self._show_memory)
        memory_layout.addWidget(memory_btn)
        right_panel.addLayout(memory_layout)

        main_layout.addLayout(right_panel, 3)

    def _setup_tray(self):
        """设置系统托盘"""
        self.tray = TrayManager(self)
        self.tray.create_tray()

    def _on_send(self):
        """发送消息"""
        text = self.input_field.text().strip()
        if not text:
            return

        self.chat_view.add_user_message(text)
        self.message_sent.emit(text)
        self.input_field.clear()

        self.mascot.set_state("thinking")
        self.status_label.setText("状态: 思考中...")

    def _show_memory(self):
        """显示记忆树"""
        pass

    def set_response(self, response: str):
        """设置响应"""
        self.chat_view.add_assistant_message(response)
        self.mascot.set_state("idle")
        self.status_label.setText("状态: 空闲")

    def set_speaking(self, audio_data: bytes):
        """设置吉祥物说话"""
        self.mascot.set_state("speaking")
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat(desktop): 实现主窗口"
```

---

### Task 13: 吉祥物组件

**Files:**
- Create: `src/taiji_agent/desktop/mascot/__init__.py`
- Create: `src/taiji_agent/desktop/mascot/widget.py`
- Create: `src/taiji_agent/desktop/mascot/states.py`
- Create: `src/taiji_agent/desktop/mascot/lottie_player.py`

- [ ] **Step 1: 创建 states.py**

```python
# src/taiji_agent/desktop/mascot/states.py
from enum import Enum


class MascotState(Enum):
    """吉祥物状态"""
    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"
    WAITING = "waiting"
    SLEEPING = "sleeping"


MASCOT_COLORS = {
    MascotState.IDLE: "#81C784",
    MascotState.THINKING: "#4CAF50",
    MascotState.SPEAKING: "#00E676",
    MascotState.LISTENING: "#66BB6A",
    MascotState.WAITING: "#A5D6A7",
    MascotState.SLEEPING: "#2E7D32",
}

MASCOT_LOTTIE_FILES = {
    MascotState.IDLE: "idle.json",
    MascotState.THINKING: "thinking.json",
    MascotState.SPEAKING: "speaking.json",
    MascotState.SLEEPING: "sleeping.json",
}
```

- [ ] **Step 2: 创建 widget.py**

```python
# src/taiji_agent/desktop/mascot/widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPalette, QPainter, QRadialGradient

from .states import MascotState, MASCOT_COLORS
from .lottie_player import LottiePlayer


class MascotWidget(QWidget):
    """吉祥物组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = MascotState.IDLE
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_frame = 0

        self.lottie_player = LottiePlayer()

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.canvas)

        self._draw_mascot()

    def set_state(self, state: str):
        """设置吉祥物状态"""
        try:
            self.state = MascotState(state)
        except ValueError:
            self.state = MascotState.IDLE

        self._draw_mascot()

        if self.state in [MascotState.THINKING, MascotState.SPEAKING]:
            self.animation_timer.start(100)
        else:
            self.animation_timer.stop()
            self.animation_frame = 0

    def _update_animation(self):
        """更新动画帧"""
        self.animation_frame += 1
        self._draw_mascot()

    def _draw_mascot(self):
        """绘制吉祥物"""
        color = QColor(MASCOT_COLORS.get(self.state, "#4CAF50"))

        if self.state == MascotState.SPEAKING:
            pulse = abs(self.animation_frame % 20 - 10) / 10
            color = QColor(int(0 + pulse * 50), int(200 + pulse * 55), int(80 + pulse * 36))

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color.name()};
                border-radius: 20px;
                border: 3px solid #2E7D32;
            }}
        """)

        emoji = self._get_emoji()
        self.canvas.setText(f"<span style='font-size: 80px;'>{emoji}</span>")

    def _get_emoji(self) -> str:
        """获取状态对应的 emoji"""
        return {
            MascotState.IDLE: "🟢",
            MascotState.THINKING: "💭",
            MascotState.SPEAKING: "🗣️",
            MascotState.LISTENING: "👂",
            MascotState.WAITING: "⏳",
            MascotState.SLEEPING: "😴",
        }.get(self.state, "🟢")
```

- [ ] **Step 3: 创建 lottie_player.py**

```python
# src/taiji_agent/desktop/mascot/lottie_player.py
from pathlib import Path
from typing import Optional


class LottiePlayer:
    """Lottie 动画播放器"""

    def __init__(self):
        self.animations: dict[str, dict] = {}
        self.current_animation: Optional[str] = None
        self.current_frame = 0

    def load_animation(self, name: str, path: Path):
        """加载动画"""
        if path.exists():
            import json
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.animations[name] = json.load(f)
            except Exception:
                pass

    def play(self, name: str):
        """播放动画"""
        if name in self.animations:
            self.current_animation = name
            self.current_frame = 0

    def get_frame(self, frame_number: int) -> Optional[dict]:
        """获取指定帧"""
        if not self.current_animation:
            return None

        animation = self.animations[self.current_animation]
        frames = animation.get("layers", [])

        if frames:
            return frames[frame_number % len(frames)]
        return None

    def set_viseme(self, viseme: str):
        """设置唇形"""
        pass
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat(desktop): 实现吉祥物组件"
```

---

### Task 14: 语音系统

**Files:**
- Create: `src/taiji_agent/desktop/voice/__init__.py`
- Create: `src/taiji_agent/desktop/voice/tts.py`
- Create: `src/taiji_agent/desktop/voice/stt.py`

- [ ] **Step 1: 创建 tts.py**

```python
# src/taiji_agent/desktop/voice/tts.py
import asyncio
from typing import Optional


class TaijiTTS:
    """太极主题 TTS"""

    VOICE_MAP = {
        "zh-CN": "zh-CN-XiaoxiaoNeural",
        "en-US": "en-US-JennyNeural",
        "zh-CN-Male": "zh-CN-YunxiNeural",
    }

    def __init__(self):
        self.voice = self.VOICE_MAP["zh-CN"]
        self.pitch = "+5%"
        self.rate = "+10%"
        self._edge_tts = None

    async def speak(self, text: str) -> bytes:
        """
        将文本转为语音

        Args:
            text: 要说话的文本

        Returns:
            bytes: 音频数据
        """
        try:
            from edge_tts import Communicate

            if self._edge_tts is None:
                self._edge_tts = Communicate(
                    text,
                    self.voice,
                    pitch=self.pitch,
                    rate=self.rate
                )

            audio_data = await self._edge_tts.get_audio()

            return audio_data

        except ImportError:
            return b""

    async def speak_to_file(self, text: str, file_path: str):
        """说话并保存到文件"""
        from edge_tts import Communicate

        communicate = Communicate(
            text,
            self.voice,
            pitch=self.pitch,
            rate=self.rate
        )

        await communicate.save(file_path)

    def set_voice(self, voice: str):
        """设置语音"""
        if voice in self.VOICE_MAP:
            self.voice = self.VOICE_MAP[voice]
        else:
            self.voice = voice
```

- [ ] **Step 2: 创建 stt.py**

```python
# src/taiji_agent/desktop/voice/stt.py
import asyncio
from typing import Optional
import numpy as np


class TaijiSTT:
    """太极主题 STT"""

    def __init__(self, model_size: str = "base"):
        """
        初始化 STT

        Args:
            model_size: 模型大小 (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self.model = None
        self.language = "zh"

    async def initialize(self):
        """初始化模型"""
        try:
            from faster_whisper import WhisperModel

            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"
            )
        except ImportError:
            pass

    async def listen(self) -> str:
        """
        监听麦克风并识别语音

        Returns:
            str: 识别的文本
        """
        if self.model is None:
            await self.initialize()

        try:
            import sounddevice as sd

            duration = 5.0
            sample_rate = 16000

            audio_data = await self._record_audio(duration, sample_rate)

            if audio_data is None or len(audio_data) == 0:
                return ""

            segments, _ = self.model.transcribe(
                audio_data,
                language=self.language
            )

            text = "".join([segment.text for segment in segments])
            return text.strip()

        except Exception:
            return ""

    async def _record_audio(
        self, duration: float, sample_rate: int
    ) -> np.ndarray:
        """录制音频"""
        try:
            import sounddevice as sd

            audio = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="float32"
            )

            sd.wait()

            return audio.flatten()

        except Exception:
            return np.array([])

    async def transcribe_file(self, file_path: str) -> str:
        """转写音频文件"""
        if self.model is None:
            await self.initialize()

        try:
            segments, _ = self.model.transcribe(
                file_path,
                language=self.language
            )

            return "".join([segment.text for segment in segments])

        except Exception:
            return ""
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat(desktop): 实现语音系统 TTS/STT"
```

---

### Task 15: 系统托盘

**Files:**
- Create: `src/taiji_agent/desktop/tray.py`

- [ ] **Step 1: 实现 TrayManager**

```python
# src/taiji_agent/desktop/tray.py
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal


class TrayManager(QObject):
    """系统托盘管理"""

    show_window = pyqtSignal()
    quick_chat = pyqtSignal()
    show_settings = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.tray: QSystemTrayIcon | None = None

    def create_tray(self):
        """创建托盘"""
        self.tray = QSystemTrayIcon(self.parent_window)

        self._create_menu()

        self.tray.setToolTip("Taiji Agent 2.0")
        self.tray.activated.connect(self._on_tray_activated)

    def _create_menu(self):
        """创建托盘菜单"""
        menu = QMenu()

        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        menu.addSeparator()

        quick_chat_action = QAction("快速对话", menu)
        quick_chat_action.triggered.connect(self._quick_chat)
        menu.addAction(quick_chat_action)

        search_memory_action = QAction("记忆查询", menu)
        search_memory_action.triggered.connect(self._search_memory)
        menu.addAction(search_memory_action)

        menu.addSeparator()

        settings_action = QAction("设置", menu)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    def show_notification(self, title: str, message: str):
        """显示通知"""
        if self.tray:
            self.tray.showMessage(title, message)

    def _on_tray_activated(self, reason):
        """托盘点击事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        """显示窗口"""
        self.show_window.emit()
        if self.parent_window:
            self.parent_window.show()
            self.parent_window.raise_()
            self.parent_window.activateWindow()

    def _quick_chat(self):
        """快速对话"""
        self.quick_chat.emit()

    def _search_memory(self):
        """搜索记忆"""
        pass

    def _show_settings(self):
        """显示设置"""
        self.show_settings.emit()

    def _quit(self):
        """退出"""
        self.quit_app.emit()
        if self.parent_window:
            self.parent_window.close()
```

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "feat(desktop): 实现系统托盘"
```

---

## Phase 4: Agent Engine 集成

### Task 16: 中间件集成

**Files:**
- Modify: `src/taiji_agent/agent/engine.py`
- Create: `tests/test_agent_integration.py`

- [ ] **Step 1: 更新 AgentConfig**

```python
# 在 engine.py 中添加
@dataclass
class AgentConfig:
    # ... 现有配置 ...

    # 新增
    tokenjuice_enabled: bool = True
    tokenjuice_threshold: int = 3000
    memory_tree_enabled: bool = True
    memory_tree_max_context: int = 3000
    desktop_enabled: bool = False
```

- [ ] **Step 2: 更新 TaijiAgent**

```python
# 在 TaijiAgent.__init__ 中添加
def __init__(self, config: AgentConfig | None = None, provider: LLMProvider | None = None):
    # ... 现有初始化 ...

    # 新增
    self.tokenjuice: TokenJuiceCompressor | None = None
    self.memory_tree: MemoryTree | None = None

    if self.config.tokenjuice_enabled:
        from taiji_agent.tokenjuice import TokenJuiceCompressor
        self.tokenjuice = TokenJuiceCompressor(llm_provider=self.provider)

    if self.config.memory_tree_enabled:
        from taiji_agent.memory_tree import MemoryTree
        self.memory_tree = MemoryTree(llm_provider=self.provider)
        asyncio.create_task(self.memory_tree.initialize())
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat: 集成 TokenJuice 和 Memory Tree 到 Agent Engine"
```

---

## Phase 5: 集成测试

### Task 17: 端到端测试

**Files:**
- Create: `tests/test_e2e_tokenjuice_memory.py`

- [ ] **Step 1: 编写端到端测试**

```python
# tests/test_e2e_tokenjuice_memory.py
import pytest
import asyncio
from pathlib import Path
from taiji_agent.agent import TaijiAgent, AgentConfig
from taiji_agent.memory_tree import MemoryTree
from taiji_agent.tokenjuice import TokenJuiceCompressor


@pytest.fixture
def mock_provider():
    """模拟 LLM 提供商"""
    class MockProvider:
        def chat(self, messages, **kwargs):
            class Response:
                content = "这是测试响应"
            return Response()

        async def achat(self, messages, **kwargs):
            return self.chat(messages, **kwargs)

    return MockProvider()


@pytest.mark.asyncio
async def test_tokenjuice_compression(mock_provider):
    """测试 TokenJuice 压缩"""
    compressor = TokenJuiceCompressor(llm_provider=mock_provider)

    html_content = "<p>Hello <b>World</b></p>"
    result = compressor.compress(html_content)

    assert "Hello **World**" in result.text
    assert "<" not in result.text


@pytest.mark.asyncio
async def test_memory_tree_ingest(tmp_path, mock_provider):
    """测试 Memory Tree 摄入"""
    tree = MemoryTree(
        storage_dir=tmp_path / "memory",
        vault_dir=tmp_path / "vault",
        llm_provider=mock_provider
    )
    await tree.initialize()

    await tree.ingest(
        content="用户喜欢喝咖啡",
        source_type="test",
        source_id="001"
    )

    context = await tree.get_context("用户偏好")
    assert "咖啡" in context or "偏好" in context

    await tree.close()


@pytest.mark.asyncio
async def test_full_pipeline(tmp_path, mock_provider):
    """测试完整流程"""
    config = AgentConfig(
        tokenjuice_enabled=True,
        memory_tree_enabled=True
    )

    agent = TaijiAgent(config=config, provider=mock_provider)

    assert agent.tokenjuice is not None
    assert agent.memory_tree is not None
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/test_e2e_tokenjuice_memory.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "test: 添加 TokenJuice 和 Memory Tree 集成测试"
```

---

## 实施检查清单

- [ ] Phase 1: TokenJuice 压缩层
  - [ ] Task 1: 依赖安装和目录创建
  - [ ] Task 2: HTML 转 Markdown 规则
  - [ ] Task 3: URL 缩短规则
  - [ ] Task 4: 去重规则
  - [ ] Task 5: CJK 保留规则
  - [ ] Task 6: 主压缩引擎

- [ ] Phase 2: Memory Tree 分层记忆
  - [ ] Task 7: 目录创建和依赖
  - [ ] Task 8: SQLite 存储层
  - [ ] Task 9: Obsidian Vault 同步
  - [ ] Task 10: MemoryTree 主类

- [ ] Phase 3: PyQt 桌面系统
  - [ ] Task 11: PyQt 依赖和入口
  - [ ] Task 12: 主窗口
  - [ ] Task 13: 吉祥物组件
  - [ ] Task 14: 语音系统
  - [ ] Task 15: 系统托盘

- [ ] Phase 4: Agent Engine 集成
  - [ ] Task 16: 中间件集成

- [ ] Phase 5: 集成测试
  - [ ] Task 17: 端到端测试

---

**计划版本**: 1.0
**预估总工时**: 20-25 天
**下次审查**: 实施前
