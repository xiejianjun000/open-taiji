"""Obsidian Vault 同步测试"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from taiji_agent.memory_tree.storage.vault import ObsidianVault


@pytest.fixture
async def vault():
    """创建测试 Vault"""
    with tempfile.TemporaryDirectory() as tmp:
        v = ObsidianVault(Path(tmp) / "vault")
        await v.initialize()
        yield v


@pytest.mark.asyncio
async def test_write_source_file(vault):
    """测试写入源文件"""
    await vault.write_source("email", "msg123", "# 邮件主题\n\n邮件正文内容")
    file_path = vault.sources_dir / "email" / "msg123.md"
    assert file_path.exists()
    content = file_path.read_text()
    assert "邮件主题" in content


@pytest.mark.asyncio
async def test_write_topic_file(vault):
    """测试写入主题文件"""
    await vault.write_topic("项目A", "# 项目A\n\n这是一个电商项目")
    file_path = vault.topics_dir / "项目A.md"
    assert file_path.exists()


@pytest.mark.asyncio
async def test_write_global_file(vault):
    """测试写入全局文件"""
    await vault.write_global("persona", "# 用户画像\n\n用户是产品经理")
    file_path = vault.global_dir / "persona.md"
    assert file_path.exists()


@pytest.mark.asyncio
async def test_sync_all(vault):
    """测试全量同步"""
    await vault.write_source("email", "msg1", "内容1")
    await vault.write_topic("主题1", "摘要1")

    result = await vault.sync_all()

    assert result.files_written >= 2


@pytest.mark.asyncio
async def test_read_source(vault):
    """测试读取源文件"""
    await vault.write_source("email", "msg1", "# 测试邮件\n\n内容")
    
    content = await vault.read_source("email", "msg1")
    assert content is not None
    assert "测试邮件" in content
