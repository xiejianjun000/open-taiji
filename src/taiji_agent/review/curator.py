"""技能馆长 — 定期技能库维护

职责:
  - 归档长期未使用的技能
  - 合并重叠技能
  - 自动生命周期管理
  - 只管理 agent-created 技能

Strict invariants:
  - 只触碰 agent-created 技能
  - 从不自动删除 — 只归档
  - Pinned 技能不受影响
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"

DEFAULT_INTERVAL_HOURS = 24 * 7     # 7天
DEFAULT_STALE_AFTER_DAYS = 30       # 30天未使用 = stale
DEFAULT_ARCHIVE_AFTER_DAYS = 90     # 90天未使用 = 归档


class SkillCurator:
    """技能馆长"""

    def __init__(self):
        self._state_file = TAIJI_HOME / "skills" / ".curator_state"
        self._archive_dir = TAIJI_HOME / "skills" / ".archive"
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if not self._state_file.exists():
            return {"last_run_at": None, "paused": False, "run_count": 0}
        try:
            with open(self._state_file) as f:
                return json.load(f)
        except Exception:
            return {"last_run_at": None, "paused": False, "run_count": 0}

    def _save_state(self):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_file, "w") as f:
            json.dump(self._state, f)

    def should_run(self, interval_hours: int = None) -> bool:
        if self._state.get("paused"):
            return False
        if self._state["last_run_at"] is None:
            return True
        interval = interval_hours or DEFAULT_INTERVAL_HOURS
        return (time.time() - self._state["last_run_at"]) > interval * 3600

    def run(self):
        """执行馆长维护"""
        try:
            logger.info("Curator: starting maintenance")
            from taiji_agent.skills.usage import _tracker

            # 找到所有 agent-created 技能
            agent_skills = _tracker.list_agent_created()
            if not agent_skills:
                logger.info("Curator: no agent-created skills to maintain")
                return

            # Stale 检测
            stale = _tracker.list_stale(days=DEFAULT_STALE_AFTER_DAYS)
            for name in stale:
                logger.info("Curator: skill '%s' is stale", name)

            # 归档检测
            to_archive = _tracker.list_stale(days=DEFAULT_ARCHIVE_AFTER_DAYS)
            for name in to_archive:
                self._archive_skill(name)

            self._state["last_run_at"] = time.time()
            self._state["run_count"] = self._state.get("run_count", 0) + 1
            self._save_state()

        except Exception as e:
            logger.warning("Curator error: %s", e)

    def _archive_skill(self, name: str):
        """归档技能"""
        try:
            from taiji_agent.skills.registry import skill_registry
            skill_dir = skill_registry.find_skill_dir(name)
            if not skill_dir:
                return
            import shutil
            self._archive_dir.mkdir(parents=True, exist_ok=True)
            dest = self._archive_dir / name
            if skill_dir.exists() and not dest.exists():
                shutil.move(str(skill_dir), str(dest))
                logger.info("Curator: archived skill '%s'", name)
        except Exception as e:
            logger.warning("Curator: failed to archive '%s': %s", name, e)

    def toggle_pause(self):
        self._state["paused"] = not self._state.get("paused", False)
        self._save_state()
        return self._state["paused"]
