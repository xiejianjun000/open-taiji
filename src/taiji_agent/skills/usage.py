"""技能使用追踪 — 记录技能的查看、使用、修补次数

支持馆长（Curator）生命周期管理:
  - pinned: 受保护，不允许删除
  - agent_created: 后台审查创建
  - last_used_at: 最近使用时间（用于 stale 检测）
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"
USAGE_FILE = TAIJI_HOME / "skills" / ".skill_usage.json"


class SkillUsageTracker:
    """技能使用追踪器"""

    def __init__(self):
        self._usage_file = USAGE_FILE
        self._usage_file.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self._usage_file.exists():
            return {}
        try:
            with open(self._usage_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        try:
            with open(self._usage_file, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save skill usage: %s", e)

    def _ensure_record(self, name: str) -> dict:
        if name not in self._records:
            self._records[name] = {
                "name": name,
                "view_count": 0,
                "use_count": 0,
                "patch_count": 0,
                "agent_created": False,
                "pinned": False,
                "last_used_at": None,
                "last_viewed_at": None,
                "last_patched_at": None,
                "created_at": time.time(),
            }
        return self._records[name]

    def bump_view(self, name: str):
        rec = self._ensure_record(name)
        rec["view_count"] += 1
        rec["last_viewed_at"] = time.time()
        self._save()

    def bump_use(self, name: str):
        rec = self._ensure_record(name)
        rec["use_count"] += 1
        rec["last_used_at"] = time.time()
        self._save()

    def bump_patch(self, name: str):
        rec = self._ensure_record(name)
        rec["patch_count"] += 1
        rec["last_patched_at"] = time.time()
        self._save()

    def mark_agent_created(self, name: str):
        rec = self._ensure_record(name)
        rec["agent_created"] = True
        self._save()

    def is_agent_created(self, name: str) -> bool:
        return self._records.get(name, {}).get("agent_created", False)

    def get_record(self, name: str) -> Optional[dict]:
        return self._records.get(name)

    def pin(self, name: str):
        rec = self._ensure_record(name)
        rec["pinned"] = True
        self._save()

    def unpin(self, name: str):
        rec = self._ensure_record(name)
        rec["pinned"] = False
        self._save()

    def forget(self, name: str):
        self._records.pop(name, None)
        self._save()

    def list_agent_created(self) -> list[str]:
        return [n for n, r in self._records.items() if r.get("agent_created")]

    def list_stale(self, days: int = 30) -> list[str]:
        threshold = time.time() - days * 86400
        return [
            n for n, r in self._records.items()
            if r.get("last_used_at") and r["last_used_at"] < threshold
            and not r.get("pinned")
        ]


# 全局实例
_tracker = SkillUsageTracker()


def bump_view(name: str):
    _tracker.bump_view(name)


def bump_use(name: str):
    _tracker.bump_use(name)


def bump_patch(name: str):
    _tracker.bump_patch(name)


def mark_agent_created(name: str):
    _tracker.mark_agent_created(name)


def is_agent_created(name: str) -> bool:
    return _tracker.is_agent_created(name)


def get_record(name: str) -> Optional[dict]:
    return _tracker.get_record(name)
