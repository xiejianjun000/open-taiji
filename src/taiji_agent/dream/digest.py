"""记忆消化器 — 梦境系统的核心处理器"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"


class MemoryDigester:
    """记忆消化器"""

    def __init__(self):
        self._memory_dir = TAIJI_HOME / "memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    async def digest_deep(self):
        try:
            conversations = self._load_recent_conversations(limit=50)
            if not conversations:
                return None
            memories = []
            skills_candidates = []
            for conv in conversations:
                if self._is_skill_worthy(conv):
                    skills_candidates.append(conv)
                memories.append(self._extract_key_info(conv))
            if memories:
                self._save_memories(memories)
            skills_created = 0
            if skills_candidates:
                skills_created = await self._create_skills_from_candidates(skills_candidates)
            return {"memories": len(memories), "skills": skills_created}
        except Exception as e:
            logger.warning("Deep digest error: %s", e)
            return None

    async def digest_light(self):
        try:
            conversations = self._load_recent_conversations(limit=20)
            if conversations:
                profile = self._update_user_profile(conversations)
                self._save_profile(profile)
        except Exception as e:
            logger.warning("Light digest error: %s", e)

    async def digest_rem(self):
        try:
            self._link_related_memories()
        except Exception as e:
            logger.warning("REM digest error: %s", e)

    def _load_recent_conversations(self, limit=50):
        # 1) 优先从 JSONL 读取（兼容 OpenClaw memory-core 格式）
        conv_file = TAIJI_HOME / "conversations.jsonl"
        conversations = []
        if conv_file.exists():
            try:
                with open(conv_file, encoding="utf-8") as f:
                    for line in f:
                        try:
                            conversations.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

        if conversations:
            return conversations[-limit:]

        # 2) 回退到 Taiji SQLite 会话存储
        try:
            import sqlite3
            db_path = Path.home() / ".taiji_agent" / "sessions.db"
            if not db_path.exists():
                return []

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # 获取最近活跃的会话
            sessions_rows = conn.execute(
                "SELECT id, name FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

            for s_row in sessions_rows:
                sid = s_row["id"]
                msgs = conn.execute(
                    "SELECT role, content, created_at FROM messages "
                    "WHERE session_id=? ORDER BY id ASC",
                    (sid,)
                ).fetchall()

                if msgs:
                    # 转换成 digest 期望的格式: {messages: [{role,content},...], timestamp, ...}
                    conversations.append({
                        "session_id": sid,
                        "name": s_row["name"] or sid,
                        "timestamp": msgs[-1]["created_at"] or time.time(),
                        "messages": [
                            {"role": m["role"], "content": m["content"]}
                            for m in msgs
                        ],
                    })

            conn.close()
        except Exception as e:
            logger.debug("SQLite fallback error: %s", e)

        return conversations[-limit:]

    def _is_skill_worthy(self, conv):
        messages = conv.get("messages", [])
        tool_calls = sum(1 for m in messages if m.get("role") == "tool")
        user_turns = sum(1 for m in messages if m.get("role") == "user")
        return tool_calls >= 3 and user_turns >= 3

    def _extract_key_info(self, conv):
        return {
            "timestamp": conv.get("timestamp", time.time()),
            "summary": conv.get("messages", [{}])[0].get("content", "")[:200] if conv.get("messages") else "",
            "tags": self._extract_tags(conv),
        }

    def _extract_tags(self, conv):
        messages = conv.get("messages", [])
        full_text = " ".join(m.get("content", "") for m in messages).lower()
        tag_keywords = ["python", "code", "debug", "git", "test", "api", "docker", "deploy",
                       "飞书", "feishu", "数据库", "database", "redis", "linux", "shell"]
        return [kw for kw in tag_keywords if kw in full_text][:5]

    async def _create_skills_from_candidates(self, candidates):
        created = 0
        try:
            from taiji_agent.skills.provenance import set_write_origin, reset_write_origin
            token = set_write_origin("background_review")
            try:
                for candidate in candidates[:3]:
                    name = self._generate_skill_name(candidate)
                    content = self._generate_skill_content(candidate)
                    if name and content:
                        from taiji_agent.skills.manager_tool import _create_skill
                        result = _create_skill(name, content)
                        if result.get("success"):
                            created += 1
                            try:
                                from taiji_agent.skills.usage import mark_agent_created
                                mark_agent_created(name)
                            except Exception:
                                pass
            finally:
                reset_write_origin(token)
        except Exception as e:
            logger.debug("Auto skill creation error: %s", e)
        return created

    def _generate_skill_name(self, conv):
        messages = conv.get("messages", [])
        first_msg = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        if not first_msg:
            return None
        import re
        words = re.findall(r'[a-z0-9一-鿿]+', first_msg.lower())
        return "-".join(words[:4])[:60] if words else None

    def _generate_skill_content(self, conv):
        name = self._generate_skill_name(conv)
        if not name:
            return None
        messages = conv.get("messages", [])
        first_msg = next((m.get("content", "")[:100] for m in messages if m.get("role") == "user"), "")
        return "---\nname: %s\ndescription: Auto-extracted skill\nversion: 1.0.0\n---\n\n# %s\n\nFrom: %s..." % (name, name, first_msg)

    def _save_memories(self, memories):
        mem_file = self._memory_dir / "dream_memories.jsonl"
        with open(mem_file, "a", encoding="utf-8") as f:
            for mem in memories:
                f.write(json.dumps(mem, ensure_ascii=False) + "\n")

    def _update_user_profile(self, conversations):
        profile = {}
        profile_file = TAIJI_HOME / "user_profile.json"
        if profile_file.exists():
            try:
                with open(profile_file) as f:
                    profile = json.load(f)
            except Exception:
                pass
        profile["last_active"] = time.time()
        profile["total_conversations"] = profile.get("total_conversations", 0) + len(conversations)
        return profile

    def _save_profile(self, profile):
        profile_file = TAIJI_HOME / "user_profile.json"
        with open(profile_file, "w") as f:
            json.dump(profile, f, ensure_ascii=False)

    def _link_related_memories(self):
        pass
