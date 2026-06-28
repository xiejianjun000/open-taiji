"""Cron 调度器 — 后台线程 + 文件锁"""

import logging
import os
import time
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"


class CronScheduler:
    """定时任务调度器"""

    def __init__(self):
        self._lock_file = TAIJI_HOME / "cron" / ".tick.lock"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 60  # 秒

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()
        logger.info("Cron scheduler started (tick: %ds)", self._tick_interval)

    def stop(self):
        self._running = False

    def _tick_loop(self):
        while self._running:
            try:
                if self._acquire_lock():
                    self._tick()
            except Exception as e:
                logger.warning("Cron tick error: %s", e)
            finally:
                self._release_lock()
            time.sleep(self._tick_interval)

    def _tick(self):
        """执行一次调度"""
        try:
            from taiji_agent.cron.jobs import _manager
            due = _manager.get_due_jobs()
            if due:
                logger.info("Cron tick: %d job(s) due", len(due))
                for job in due:
                    self._run_job(job)
        except Exception as e:
            logger.warning("Cron tick execution error: %s", e)

    def _run_job(self, job: dict):
        """执行单个任务"""
        import json
        job_id = job["id"]
        try:
            # 安全扫描
            prompt = job.get("prompt", "")
            if prompt and self._scan_prompt(prompt):
                logger.warning("Cron job %s blocked by security scan", job_id)
                self._mark_run(job_id, "blocked")
                return

            if job.get("no_agent") and job.get("script"):
                self._run_script_job(job)
            else:
                self._run_agent_job(job)

            self._mark_run(job_id, "success")
        except Exception as e:
            logger.error("Cron job %s failed: %s", job_id, e)
            self._mark_run(job_id, "error")

    def _run_agent_job(self, job: dict):
        """LLM 驱动的任务执行"""
        # 预留: 通过 Agent 执行
        logger.info("Agent job %s: %s", job["id"], job.get("prompt", "")[:100])
        pass

    def _run_script_job(self, job: dict):
        """纯脚本执行"""
        import subprocess
        script = job["script"]
        scripts_dir = TAIJI_HOME / "scripts"
        script_path = scripts_dir / script
        if not script_path.exists():
            logger.error("Script not found: %s", script_path)
            return
        try:
            result = subprocess.run(
                ["bash", str(script_path)] if script.endswith(".sh") else ["python3", str(script_path)],
                capture_output=True, text=True, timeout=300
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            # 投递结果
            if output.strip():
                self._deliver(job, output)
        except subprocess.TimeoutExpired:
            logger.warning("Script job %s timed out", job["id"])

    def _deliver(self, job: dict, content: str):
        """投递任务结果"""
        deliver = job.get("deliver", "local")
        if deliver == "local":
            runs_dir = TAIJI_HOME / "cron" / "runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            output_file = runs_dir / f"{job['id']}.txt"
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{content}\n\n")
        # 投递到 IM 平台
        elif deliver.startswith("feishu"):
            logger.info("Deliver to feishu: %s...", content[:50])
        elif deliver.startswith("dingtalk"):
            logger.info("Deliver to dingtalk: %s...", content[:50])

    def _mark_run(self, job_id: str, status: str):
        try:
            from taiji_agent.cron.jobs import _manager
            _manager.mark_run(job_id, status)
        except Exception:
            pass

    def _scan_prompt(self, prompt: str) -> bool:
        """扫描提示注入"""
        threats = [
            "ignore previous instructions",
            "disregard your instructions",
            "system prompt override",
        ]
        prompt_lower = prompt.lower()
        return any(t in prompt_lower for t in threats)

    def _acquire_lock(self) -> bool:
        try:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            if self._lock_file.exists():
                # 检查锁是否过期
                mtime = self._lock_file.stat().st_mtime
                if time.time() - mtime > 300:  # 5分钟过期
                    self._lock_file.unlink()
                else:
                    return False
            self._lock_file.touch()
            return True
        except Exception:
            return False

    def _release_lock(self):
        try:
            if self._lock_file.exists():
                self._lock_file.unlink()
        except Exception:
            pass
