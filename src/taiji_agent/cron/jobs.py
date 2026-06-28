"""Cron 任务管理器 — JSON 文件存储"""

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"
JOBS_FILE = TAIJI_HOME / "cron" / "jobs.json"


class CronJobManager:
    """定时任务管理器"""

    def __init__(self, jobs_file: Optional[Path] = None):
        self.jobs_file = jobs_file or JOBS_FILE
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.jobs_file.exists():
            return {}
        try:
            with open(self.jobs_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        with open(self.jobs_file, "w", encoding="utf-8") as f:
            json.dump(self._jobs, f, ensure_ascii=False, indent=2)

    def create(self, prompt: str = "", schedule: str = "", name: str = None,
               repeat: int = None, deliver: str = "local", skills: list[str] = None,
               model: str = None, script: str = None, no_agent: bool = False,
               **kwargs) -> dict:
        """创建定时任务"""
        job_id = str(uuid.uuid4())[:8]
        parsed = _parse_schedule(schedule)

        job = {
            "id": job_id,
            "name": name or prompt[:50] or f"cron-{job_id}",
            "prompt": prompt or "",
            "schedule": parsed,
            "schedule_display": schedule,
            "repeat": {"times": repeat, "completed": 0} if repeat else None,
            "deliver": deliver,
            "skills": skills or [],
            "model": model,
            "script": script,
            "no_agent": no_agent,
            "enabled": True,
            "state": "scheduled",
            "created_at": time.time(),
            "next_run_at": _calculate_next_run(parsed),
            "last_run_at": None,
            "last_status": None,
            "run_count": 0,
        }
        self._jobs[job_id] = job
        self._save()
        logger.info("Cron job created: %s (%s)", job_id, job["name"])
        return job

    def get(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)

    def list_jobs(self, include_disabled: bool = False) -> list[dict]:
        jobs = list(self._jobs.values())
        if not include_disabled:
            jobs = [j for j in jobs if j.get("enabled", True)]
        return sorted(jobs, key=lambda j: j.get("created_at", 0), reverse=True)

    def update(self, job_id: str, updates: dict) -> Optional[dict]:
        if job_id not in self._jobs:
            return None
        self._jobs[job_id].update(updates)
        if "schedule" in updates:
            self._jobs[job_id]["next_run_at"] = _calculate_next_run(self._jobs[job_id]["schedule"])
        self._save()
        return self._jobs[job_id]

    def pause(self, job_id: str, reason: str = None) -> Optional[dict]:
        if job_id not in self._jobs:
            return None
        self._jobs[job_id]["enabled"] = False
        self._jobs[job_id]["state"] = "paused"
        self._jobs[job_id]["paused_at"] = time.time()
        self._jobs[job_id]["paused_reason"] = reason
        self._save()
        return self._jobs[job_id]

    def resume(self, job_id: str) -> Optional[dict]:
        if job_id not in self._jobs:
            return None
        self._jobs[job_id]["enabled"] = True
        self._jobs[job_id]["state"] = "scheduled"
        self._jobs[job_id]["paused_at"] = None
        self._jobs[job_id]["paused_reason"] = None
        self._jobs[job_id]["next_run_at"] = _calculate_next_run(self._jobs[job_id]["schedule"])
        self._save()
        return self._jobs[job_id]

    def remove(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._save()
        return True

    def get_due_jobs(self) -> list[dict]:
        """获取到期的任务"""
        now = time.time()
        due = []
        for job in self._jobs.values():
            if not job.get("enabled"):
                continue
            next_run = job.get("next_run_at")
            if next_run and next_run <= now:
                due.append(job)
        return due

    def mark_run(self, job_id: str, status: str):
        """标记任务运行"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job["last_run_at"] = time.time()
            job["last_status"] = status
            job["run_count"] = job.get("run_count", 0) + 1
            # 更新下次运行时间
            if job["schedule"]:
                job["next_run_at"] = _calculate_next_run(job["schedule"])
            # 处理 repeat
            if job.get("repeat"):
                job["repeat"]["completed"] = job["repeat"].get("completed", 0) + 1
                times = job["repeat"].get("times")
                if times and job["repeat"]["completed"] >= times:
                    job["enabled"] = False
                    job["state"] = "completed"
            self._save()


# ── 全局函数 ──────────────────────────────────────────────────────────────

_manager = CronJobManager()


def create_job(**kwargs) -> dict:
    return _manager.create(**kwargs)


def get_job(job_id: str) -> Optional[dict]:
    return _manager.get(job_id)


def list_jobs(**kwargs) -> list[dict]:
    return _manager.list_jobs(**kwargs)


def pause_job(job_id: str, reason: str = None) -> Optional[dict]:
    return _manager.pause(job_id, reason)


def resume_job(job_id: str) -> Optional[dict]:
    return _manager.resume(job_id)


def remove_job(job_id: str) -> bool:
    return _manager.remove(job_id)


def trigger_job(job_id: str) -> Optional[dict]:
    """手动触发任务"""
    job = _manager.get(job_id)
    if job:
        job["next_run_at"] = time.time() - 1  # 立即到期
        _manager._save()
    return job


def update_job(job_id: str, updates: dict) -> Optional[dict]:
    return _manager.update(job_id, updates)


# ── 调度解析 ──────────────────────────────────────────────────────────────

def _parse_schedule(schedule: str) -> dict:
    """解析调度字符串"""
    schedule = schedule.strip().lower()
    result = {"type": "unknown", "raw": schedule}

    # 人类友好格式: "30m", "every 2h", "every day at 9am"
    match = re.match(r'^(?:every\s+)?(\d+)\s*(m|min|mins|minute|minutes)$', schedule)
    if match:
        result["type"] = "interval"
        result["interval_seconds"] = int(match.group(1)) * 60
        return result

    match = re.match(r'^(?:every\s+)?(\d+)\s*(h|hr|hrs|hour|hours)$', schedule)
    if match:
        result["type"] = "interval"
        result["interval_seconds"] = int(match.group(1)) * 3600
        return result

    match = re.match(r'^(?:every\s+)?(\d+)\s*(d|day|days)$', schedule)
    if match:
        result["type"] = "interval"
        result["interval_seconds"] = int(match.group(1)) * 86400
        return result

    # Cron 表达式: "0 9 * * *"
    parts = schedule.split()
    if len(parts) == 5:
        result["type"] = "cron"
        result["cron"] = schedule
        return result

    # ISO 时间戳
    try:
        import datetime
        dt = datetime.datetime.fromisoformat(schedule)
        result["type"] = "once"
        result["run_at"] = dt.timestamp()
        return result
    except (ValueError, TypeError):
        pass

    return result


def _calculate_next_run(schedule: dict) -> Optional[float]:
    """计算下次运行时间"""
    if not schedule:
        return None
    now = time.time()

    if schedule["type"] == "interval":
        interval = schedule["interval_seconds"]
        return now + interval

    if schedule["type"] == "once":
        return schedule.get("run_at")

    if schedule["type"] == "cron":
        # 简化 cron: 默认 60s 间隔
        return now + 60

    return None
