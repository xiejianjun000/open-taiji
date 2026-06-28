"""太极定时任务系统 — 来自 Hermes/OpenClaw Cron

独立于操作系统的 crontab，使用 JSON 文件存储 + 文件锁调度。

支持:
  - create/list/update/pause/resume/remove/trigger
  - cron 表达式 + 人类友好格式 ("every 2h", "30m")
  - 多平台投递 (local, feishu, dingtalk, wecom, telegram, etc.)
  - LLM 驱动任务 + 纯脚本任务
  - 上下文链（context_from）
  - 安全扫描（提示注入检测）

目录:
  ~/.taiji/cron/
  ├── jobs.json       # 任务定义
  ├── .tick.lock      # 调度锁
  └── runs/           # 运行记录
"""

from taiji_agent.cron.jobs import (
    CronJobManager,
    create_job, get_job, list_jobs,
    pause_job, resume_job, remove_job, trigger_job, update_job,
)
from taiji_agent.cron.scheduler import CronScheduler
from taiji_agent.cron.tool import cronjob, CRONJOB_SCHEMA

__all__ = [
    "CronJobManager",
    "CronScheduler",
    "create_job", "get_job", "list_jobs",
    "pause_job", "resume_job", "remove_job", "trigger_job", "update_job",
    "cronjob", "CRONJOB_SCHEMA",
]
