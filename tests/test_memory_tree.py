"""MemoryTree 主类测试"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from taiji_agent.memory_tree import MemoryTree, Layer


class MockLLMProvider:
    """模拟 LLM 提供商 - 直接返回摘要请求的内容"""
    def chat(self, messages, **kwargs):
        class Response:
            content = ""
        return Response()


@pytest.fixture
async def tree():
    """创建测试 MemoryTree"""
    with tempfile.TemporaryDirectory() as tmp:
        t = MemoryTree(
            storage_dir=Path(tmp) / "memory",
            vault_dir=Path(tmp) / "vault",
            llm_provider=MockLLMProvider()
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
    assert result != ""


@pytest.mark.asyncio
async def test_get_context(tree):
    """测试获取上下文"""
    await tree.ingest(
        content="项目A是一个电商平台，使用Python开发",
        source_type="notion",
        source_id="doc001"
    )

    context = await tree.get_context("分析项目A")
    assert context != ""


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


@pytest.mark.asyncio
async def test_ingest_stores_content(tree):
    """测试摄入后存储了内容"""
    await tree.ingest(
        content="这是一段重要内容",
        source_type="test",
        source_id="test1"
    )

    chunks = await tree.storage.get_source_chunks("test", "test1")
    assert len(chunks) > 0
    assert "重要内容" in chunks[0]["content"]
