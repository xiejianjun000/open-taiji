"""cronjob 工具 — 供 Agent 调用"""

import json
import logging
from typing import Any, Optional

from taiji_agent.cron.jobs import (
    create_job, get_job, list_jobs,
    pause_job, resume_job, remove_job, trigger_job, update_job,
    _manager,
)

logger = logging.getLogger(__name__)

CRONJOB_SCHEMA = {
    "name": "cronjob",
    "description": "管理定时任务。创建、列出、更新、暂停、恢复、删除或手动触法定时任务。\n\n使用 action='create' 创建新任务，action='list' 查看所有任务，action='update'/'pause'/'resume'/'remove'/'run' 管理现有任务。",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "update", "pause", "resume", "remove", "run", "trigger"],
                "description": "操作类型"
            },
            "job_id": {"type": "string", "description": "任务 ID（update/pause/resume/remove/run 需要）"},
            "prompt": {"type": "string", "description": "任务提示词（create 需要）"},
            "schedule": {"type": "string", "description": "调度: '30m', 'every 2h', '0 9 * * *', ISO 时间戳"},
            "name": {"type": "string", "description": "可选的任务名称"},
            "repeat": {"type": "integer", "description": "可选重复次数"},
            "deliver": {"type": "string", "description": "投递目标: 'local', 'feishu', 'dingtalk', 'all'"},
            "skills": {"type": "array", "items": {"type": "string"}, "description": "可选技能列表"},
            "script": {"type": "string", "description": "可选脚本路径（相对于 ~/.taiji/scripts/）"},
            "no_agent": {"type": "boolean", "description": "设 true 跳过 LLM，直接用脚本"},
        },
        "required": ["action"],
    },
}


def cronjob(
    action: str,
    job_id: str = None,
    prompt: str = None,
    schedule: str = None,
    name: str = None,
    repeat: int = None,
    deliver: str = None,
    skills: list[str] = None,
    script: str = None,
    no_agent: bool = None,
    **kwargs,
) -> str:
    try:
        action = (action or "").strip().lower()

        if action == "create":
            if not schedule:
                return json.dumps({"success": False, "error": "schedule 是必需的"}, ensure_ascii=False)
            if not prompt and not skills:
                return json.dumps({"success": False, "error": "create 需要 prompt 或 skills"}, ensure_ascii=False)
            job = create_job(prompt=prompt or "", schedule=schedule, name=name, repeat=repeat,
                           deliver=deliver or "local", skills=skills, script=script, no_agent=bool(no_agent))
            return json.dumps({"success": True, "job_id": job["id"], "name": job["name"],
                             "schedule": job["schedule_display"], "next_run_at": job["next_run_at"],
                             "message": f"定时任务 '{job['name']}' 已创建"}, ensure_ascii=False, indent=2)

        if action == "list":
            jobs = list_jobs()
            return json.dumps({"success": True, "count": len(jobs), "jobs": [_format_job(j) for j in jobs]},
                            ensure_ascii=False, indent=2)

        if not job_id:
            return json.dumps({"success": False, "error": f"操作 '{action}' 需要 job_id"}, ensure_ascii=False)

        job = get_job(job_id)
        if not job:
            return json.dumps({"success": False, "error": f"任务 '{job_id}' 未找到"}, ensure_ascii=False)

        if action == "update":
            updates = {}
            for key in ["prompt", "name", "deliver", "skills", "script"]:
                if locals().get(key) is not None:
                    updates[key] = locals()[key]
            if not updates:
                return json.dumps({"success": False, "error": "没有提供更新内容"}, ensure_ascii=False)
            updated = update_job(job_id, updates)
            return json.dumps({"success": True, "job": _format_job(updated)}, ensure_ascii=False, indent=2)

        if action == "remove":
            removed = remove_job(job_id)
            return json.dumps({"success": True, "message": f"任务 '{job['name']}' 已删除"} if removed else
                            {"success": False, "error": f"删除失败"}, ensure_ascii=False)

        if action == "pause":
            updated = pause_job(job_id)
            return json.dumps({"success": True, "job": _format_job(updated)}, ensure_ascii=False, indent=2)

        if action == "resume":
            updated = resume_job(job_id)
            return json.dumps({"success": True, "job": _format_job(updated)}, ensure_ascii=False, indent=2)

        if action in {"run", "trigger"}:
            updated = trigger_job(job_id)
            return json.dumps({"success": True, "job": _format_job(updated)}, ensure_ascii=False, indent=2)

        return json.dumps({"success": False, "error": f"未知操作: {action}"}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


def _format_job(job: dict) -> dict:
    prompt = str(job.get("prompt", ""))
    return {
        "job_id": job["id"],
        "name": job.get("name", ""),
        "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "schedule": job.get("schedule_display", "?"),
        "deliver": job.get("deliver", "local"),
        "next_run_at": job.get("next_run_at"),
        "last_run_at": job.get("last_run_at"),
        "last_status": job.get("last_status"),
        "enabled": job.get("enabled", True),
        "state": job.get("state", "scheduled"),
        "run_count": job.get("run_count", 0),
    }
