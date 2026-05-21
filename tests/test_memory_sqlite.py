"""Memory Tree SQLite 存储层测试"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from taiji_agent.memory_tree.storage.sqlite import SQLiteStorage


@pytest.fixture
async def storage():
    """创建测试存储"""
    with tempfile.TemporaryDirectory() as tmp:
        s = SQLiteStorage(Path(tmp) / "test.db")
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
    assert persona is not None
    assert "产品经理" in persona["content"]


@pytest.mark.asyncio
async def test_multiple_topics(storage):
    """测试多个主题"""
    await storage.store_topic_summary("主题1", "摘要1", 0.5)
    await storage.store_topic_summary("主题2", "摘要2", 0.8)
    await storage.store_topic_summary("主题3", "摘要3", 0.6)

    topics = await storage.get_topics()
    assert len(topics) >= 2
