"""SQLite 存储层"""
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

    async def get_global_memory(self, memory_type: str) -> Optional[dict]:
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
