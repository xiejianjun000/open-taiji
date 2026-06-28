"""技能工具 — skills_list 和 skill_view

渐进披露架构:
  skills_list → Tier 1: 名称 + 描述 (token 高效)
  skill_view  → Tier 2: 完整 SKILL.md 内容
  skill_view(name, file_path) → Tier 3: 按需加载引用文件
"""
import json
import logging

from taiji_agent.skills.registry import skill_registry, MAX_DESCRIPTION_LENGTH

logger = logging.getLogger(__name__)


# ── Schema 定义 ──────────────────────────────────────────────────────────

SKILLS_LIST_SCHEMA = {
    "name": "skills_list",
    "description": "列出所有可用技能（仅名称+描述，token节省）。使用 skill_view(name) 加载完整内容。",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "可选分类过滤（如 'development', 'research'）",
            }
        },
        "required": [],
    },
}

SKILL_VIEW_SCHEMA = {
    "name": "skill_view",
    "description": "加载技能的完整内容或访问其引用文件（references, templates, scripts, assets）。首次调用返回 SKILL.md 内容及 linked_files 字典。要访问引用文件，使用 file_path 参数再次调用。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "技能名称（使用 skills_list 查看可用技能）",
            },
            "file_path": {
                "type": "string",
                "description": "可选：技能内文件的相对路径（如 'references/api.md', 'scripts/validate.py'）。省略则返回主 SKILL.md 内容。",
            },
        },
        "required": ["name"],
    },
}


# ── Tool handlers ─────────────────────────────────────────────────────────

def skills_list(category: str = None, **kwargs) -> str:
    """列出所有技能（Tier 1: 最小元数据）

    Args:
        category: 可选分类过滤

    Returns:
        JSON 字符串，包含 skills 和 categories
    """
    try:
        all_skills = skill_registry.find_all_skills()

        if category:
            all_skills = [s for s in all_skills if s.get("category") == category]

        # 按分类排序
        all_skills = sorted(
            all_skills,
            key=lambda s: (s.get("category") or "", s["name"]),
        )

        categories = skill_registry.get_categories()

        return json.dumps(
            {
                "success": True,
                "skills": all_skills,
                "categories": categories,
                "count": len(all_skills),
                "hint": "使用 skill_view(name) 查看完整内容、标签和引用文件",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


def skill_view(name: str, file_path: str = None, **kwargs) -> str:
    """加载技能内容（Tier 2-3）

    Args:
        name: 技能名称
        file_path: 可选引用文件路径

    Returns:
        JSON 字符串
    """
    try:
        result = skill_registry.load_skill(name, file_path)

        if result is None:
            available = [s["name"] for s in skill_registry.find_all_skills()[:20]]
            return json.dumps(
                {
                    "success": False,
                    "error": f"技能 '{name}' 未找到",
                    "available_skills": available,
                    "hint": "使用 skills_list 查看所有可用技能",
                },
                ensure_ascii=False,
            )

        if result.get("success") is False:
            return json.dumps(result, ensure_ascii=False)

        # Track usage
        try:
            from taiji_agent.skills.usage import bump_view, bump_use
            bump_view(str(name))
            bump_use(str(name))
        except Exception:
            pass

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
