"""
记忆系统 - 来自 Hermes Honcho
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class SessionMemory:
    """
    会话记忆系统

    来自 Hermes Honcho 的跨会话记忆系统
    支持用户画像、语义搜索、上下文存储
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        if memory_dir is None:
            self.memory_dir = Path.home() / ".taiji_agent" / "memory"
        else:
            self.memory_dir = Path(memory_dir)

        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # 记忆存储
        self.memory_file = self.memory_dir / "memory.json"
        self._memory = self._load_memory()

        # Todo 存储
        self.todos_file = self.memory_dir / "todos.json"
        self._todos = self._load_todos()

        # 用户画像
        self.profile_file = self.memory_dir / "profile.json"
        self._profile = self._load_profile()

    def _load_memory(self) -> dict[str, Any]:
        """加载记忆"""
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text())
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    def _save_memory(self):
        """保存记忆"""
        self.memory_file.write_text(json.dumps(self._memory, ensure_ascii=False, indent=2))

    def _load_todos(self) -> list[dict[str, Any]]:
        """加载 Todo"""
        if self.todos_file.exists():
            try:
                data = json.loads(self.todos_file.read_text())
                return data if isinstance(data, list) else []
            except Exception:
                return []
        return []

    def _save_todos(self):
        """保存 Todo"""
        self.todos_file.write_text(json.dumps(self._todos, ensure_ascii=False, indent=2))

    def _load_profile(self) -> dict[str, Any]:
        """加载用户画像"""
        if self.profile_file.exists():
            try:
                data = json.loads(self.profile_file.read_text())
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {"facts": [], "preferences": {}}

    def _save_profile(self):
        """保存用户画像"""
        self.profile_file.write_text(json.dumps(self._profile, ensure_ascii=False, indent=2))

    def save(self, key: str, value: str):
        """保存记忆"""
        self._memory[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_memory()

    def get(self, key: str) -> Optional[str]:
        """获取记忆"""
        entry = self._memory.get(key)
        return entry["value"] if entry else None

    def search(self, query: str) -> str:
        """搜索记忆"""
        results = []
        query_lower = query.lower()

        for key, entry in self._memory.items():
            if query_lower in key.lower() or query_lower in entry["value"].lower():
                results.append(f"[{key}] {entry['value'][:200]}")

        return "\n\n".join(results) if results else "No matching memories"

    def save_session(self, messages: list):
        """保存会话"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._memory[f"session_{session_id}"] = {
            "value": json.dumps(messages, ensure_ascii=False),
            "timestamp": datetime.now().isoformat(),
            "type": "session",
        }
        self._save_memory()

    def get_todos(self) -> list:
        """获取所有 Todo"""
        return self._todos

    def add_todo(self, task: str):
        """添加 Todo"""
        self._todos.append(
            {
                "task": task,
                "done": False,
                "created": datetime.now().isoformat(),
            }
        )
        self._save_todos()

    def done_todo(self, task: str):
        """标记 Todo 完成"""
        for todo in self._todos:
            if todo["task"] == task:
                todo["done"] = True
                todo["completed"] = datetime.now().isoformat()
                break
        self._save_todos()

    def update_peer_card(self, peer: str, facts: list[str]):
        """更新用户画像"""
        if peer not in self._profile:
            self._profile[peer] = {"facts": [], "preferences": {}}

        self._profile[peer]["facts"].extend(facts)
        self._profile[peer]["last_updated"] = datetime.now().isoformat()
        self._save_profile()

    def get_peer_card(self, peer: str = "user") -> dict[str, Any]:
        """获取用户画像"""
        result = self._profile.get(peer)
        if result is not None:
            return result  # type: ignore[no-any-return]
        return {"facts": [], "preferences": {}}

    def store_context(self, event: str, conclusion: str):
        """存储上下文"""
        key = f"context_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._memory[key] = {
            "value": f"Event: {event}\nConclusion: {conclusion}",
            "timestamp": datetime.now().isoformat(),
            "type": "context",
        }
        self._save_memory()
