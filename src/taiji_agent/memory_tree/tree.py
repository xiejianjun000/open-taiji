"""MemoryTree 主类"""
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

        await self._update_topic_layer(content, source_type, source_id)

        await self._update_global_layer(content)

        return chunk_id

    async def _update_topic_layer(self, content: str, source_type: str, source_id: str):
        """更新主题层"""
        topic = f"{source_type}:{source_id}"

        if self.llm_provider:
            try:
                topic_prompt = f"""从以下内容中提取主题（1-2个词）:

{content}

主题:"""

                response = self.llm_provider.chat([{"role": "user", "content": topic_prompt}])
                topic = response.content.strip() if response.content else topic

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
                await self.storage.store_topic_summary(
                    topic=topic,
                    summary=content[:200],
                    importance=0.5
                )
        else:
            await self.storage.store_topic_summary(
                topic=topic,
                summary=content[:200],
                importance=0.5
            )

    async def _update_global_layer(self, content: str):
        """更新全局层"""
        if not self.llm_provider:
            return

        try:
            if any(keyword in content for keyword in ["我喜欢", "我爱好", "我的喜好", "我是"]):
                await self.storage.store_global_memory(
                    memory_type="persona",
                    content=content,
                    confidence=0.7
                )

                await self.vault.write_global("persona", f"# 用户画像\n\n{content}")
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
