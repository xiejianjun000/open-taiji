"""
太极技能系统 — 融合 Hermes Agent + OpenClaw Skill 架构

三层渐进披露：
  Tier 1: skills_list — 元数据（名称+描述）
  Tier 2: skill_view  — 完整 SKILL.md 内容
  Tier 3: 按需加载引用文件（references/ templates/ scripts/ assets/）

SKILL.md 格式 (agentskills.io 兼容):
---
name: skill-name
description: 简短描述
version: 1.0.0
metadata:
  taiji:
    tags: [tag1, tag2]
    category: development
---
# Skill Title
Full instructions...
"""

from taiji_agent.skills.registry import SkillRegistry
from taiji_agent.skills.tools import (
    skills_list,
    skill_view,
    SKILLS_LIST_SCHEMA,
    SKILL_VIEW_SCHEMA,
)
from taiji_agent.skills.manager_tool import (
    skill_manage,
    SKILL_MANAGE_SCHEMA,
)
from taiji_agent.skills.provenance import (
    set_write_origin,
    reset_write_origin,
    get_write_origin,
    is_background_review,
    BACKGROUND_REVIEW,
)
from taiji_agent.skills.usage import (
    SkillUsageTracker,
    bump_use,
    bump_view,
    bump_patch,
    mark_agent_created,
    is_agent_created,
    get_record,
)

__all__ = [
    "SkillRegistry",
    "skills_list",
    "skill_view",
    "skill_manage",
    "SKILLS_LIST_SCHEMA",
    "SKILL_VIEW_SCHEMA",
    "SKILL_MANAGE_SCHEMA",
    "set_write_origin",
    "reset_write_origin",
    "get_write_origin",
    "is_background_review",
    "BACKGROUND_REVIEW",
    "SkillUsageTracker",
    "bump_use",
    "bump_view",
    "bump_patch",
    "mark_agent_created",
    "is_agent_created",
    "get_record",
]
