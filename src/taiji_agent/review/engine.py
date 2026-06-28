"""后台审查引擎 — 对话后自动审查和技能提取"""

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"

COMBINED_REVIEW_PROMPT = """You are a background review agent. Review the conversation and extract:
1. Important user preferences and context → save to memory
2. Reusable methods → create/update skills
If nothing worth saving, say 'Nothing to save.'"""

MEMORY_REVIEW_PROMPT = """Review conversation for memory-worthy info:
1. User preferences (style, format, workflow)
2. Important context (projects, tools, environment)
3. Key decisions
If nothing new, say 'Nothing to save.'"""

SKILL_REVIEW_PROMPT = """Review conversation for skill creation:
1. Reusable methods/processes?
2. Existing skills need patching?
3. User corrected your behavior?
Skill criteria: 3+ tool calls, reusable method, user corrected approach.
If nothing, say 'Nothing to save.'"""


class BackgroundReviewEngine:
    """后台审查引擎"""

    def __init__(self, max_iterations=16):
        self.max_iterations = max_iterations
        self._review_store = TAIJI_HOME / "review_state.json"

    def spawn_review(self, messages, review_memory=True, review_skills=True, model=None):
        if not messages:
            return
        thread = threading.Thread(
            target=self._run_review,
            args=(messages, review_memory, review_skills, model),
            daemon=True,
        )
        thread.start()

    def _run_review(self, messages, review_memory, review_skills, model=None):
        import contextlib
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._process_review(messages, review_memory, review_skills, model)
                )
                loop.close()
                if result and result.get("actions"):
                    actions = result["actions"]
                    summary = " · ".join(dict.fromkeys(actions))
                    print("\n  💾 自我改进审查: %s" % summary)
            except Exception as e:
                logger.warning("Background review failed: %s", e)

    async def _process_review(self, messages, review_memory, review_skills, model=None):
        actions = []
        try:
            from taiji_agent.skills.provenance import set_write_origin, reset_write_origin
            token = set_write_origin("background_review")
            try:
                if review_memory:
                    mem_result = await self._review_memory(messages)
                    if mem_result:
                        actions.extend(mem_result)
                if review_skills:
                    skill_result = await self._review_skills(messages)
                    if skill_result:
                        actions.extend(skill_result)
            finally:
                reset_write_origin(token)
            return {"actions": actions} if actions else None
        except Exception as e:
            logger.debug("Review processing error: %s", e)
            return None

    async def _review_memory(self, messages):
        actions = []
        try:
            from taiji_agent.memory import SessionMemory
            mem = SessionMemory()
            user_messages = [_msg_content(m) for m in messages if _msg_role(m) == "user"]
            for msg in user_messages[-5:]:
                if len(msg) > 50 and self._has_memory_value(msg):
                    key = "user_info_%d" % (hash(msg) % 10000)
                    mem.save(key, msg[:500])
                    actions.append("Memory updated")
        except Exception as e:
            logger.debug("Memory review error: %s", e)
        return actions

    async def _review_skills(self, messages):
        actions = []
        try:
            tool_calls = sum(1 for m in messages if _msg_role(m) == "tool")
            user_turns = sum(1 for m in messages if _msg_role(m) == "user")
            if tool_calls >= 3 and user_turns >= 3:
                self._save_review_state({
                    "timestamp": time.time(),
                    "tool_calls": tool_calls,
                    "user_turns": user_turns,
                })
                actions.append("Skills review queued")
        except Exception as e:
            logger.debug("Skills review error: %s", e)
        return actions

    def _has_memory_value(self, text):
        keywords = ["偏好", "喜欢", "重要", "记住", "每次", "总是", "从不",
                   "prefer", "important", "remember", "always", "never"]
        return any(kw in text.lower() for kw in keywords)

    def _save_review_state(self, state):
        try:
            existing = {}
            if self._review_store.exists():
                with open(self._review_store) as f:
                    existing = json.load(f)
            existing.update(state)
            with open(self._review_store, "w") as f:
                json.dump(existing, f)
        except Exception:
            pass

    def should_review(self, messages):
        user_turns = sum(1 for m in messages if _msg_role(m) == "user")
        tool_calls = sum(1 for m in messages if _msg_role(m) == "tool")
        return (user_turns >= 2, tool_calls >= 3)


def _msg_role(msg) -> str:
    """获取消息角色，兼容 dict 和 Pydantic 对象"""
    if isinstance(msg, dict):
        return msg.get("role", "")
    return getattr(msg, "role", "")


def _msg_content(msg) -> str:
    """获取消息内容，兼容 dict 和 Pydantic 对象"""
    if isinstance(msg, dict):
        return msg.get("content", "")
    return getattr(msg, "content", "")
