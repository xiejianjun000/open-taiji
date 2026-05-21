"""端到端集成测试"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from taiji_agent.tokenjuice import TokenJuiceCompressor
from taiji_agent.memory_tree import MemoryTree


class MockLLMProvider:
    """模拟 LLM 提供商"""
    def chat(self, messages, **kwargs):
        class Response:
            content = "摘要内容"
        return Response()


@pytest.mark.asyncio
async def test_tokenjuice_compression():
    """测试 TokenJuice 压缩"""
    compressor = TokenJuiceCompressor(llm_provider=MockLLMProvider())

    html_content = "<p>Hello <b>World</b></p>"
    result = compressor.compress(html_content)

    assert "Hello **World**" in result.text
    assert "<" not in result.text


@pytest.mark.asyncio
async def test_memory_tree_ingest():
    """测试 Memory Tree 摄入"""
    with tempfile.TemporaryDirectory() as tmp:
        tree = MemoryTree(
            storage_dir=Path(tmp) / "memory",
            vault_dir=Path(tmp) / "vault",
            llm_provider=MockLLMProvider()
        )
        await tree.initialize()

        await tree.ingest(
            content="用户喜欢喝咖啡",
            source_type="test",
            source_id="001"
        )

        context = await tree.get_context("用户偏好")
        assert context != ""

        await tree.close()


@pytest.mark.asyncio
async def test_full_pipeline():
    """测试完整流程"""
    with tempfile.TemporaryDirectory() as tmp:
        tree = MemoryTree(
            storage_dir=Path(tmp) / "memory",
            vault_dir=Path(tmp) / "vault",
            llm_provider=MockLLMProvider()
        )
        await tree.initialize()

        await tree.ingest(
            content="<p>测试 <b>HTML</b> 内容</p>",
            source_type="email",
            source_id="test001"
        )

        compressor = TokenJuiceCompressor(llm_provider=MockLLMProvider())
        compressed = compressor.compress("测试 HTML 内容")

        assert compressed.tokens < 100
        assert "HTML" in compressed.text

        await tree.close()
