"""Obsidian Vault 同步"""
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

        for _, _, files in self._walk_dir(self.sources_dir):
            result.files_written += len(files)

        for _, _, files in self._walk_dir(self.topics_dir):
            result.files_written += len(files)

        for _, _, files in self._walk_dir(self.global_dir):
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
