"""技能管理工具 — Agent 自管理的技能创建/编辑/删除

操作:
  create     — 创建新技能 (SKILL.md + 目录结构)
  edit       — 完整替换 SKILL.md
  patch      — 精确查找替换 (old_string → new_string)
  delete     — 删除技能
  write_file — 添加/覆写支持文件
  remove_file — 删除支持文件

目录结构:
  ~/.taiji/skills/
  ├── my-skill/
  │   ├── SKILL.md
  │   ├── references/
  │   ├── templates/
  │   ├── scripts/
  │   └── assets/
"""
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

import yaml

from taiji_agent.skills.registry import (
    skill_registry,
    SKILLS_DIR,
    MAX_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
)

logger = logging.getLogger(__name__)

MAX_SKILL_CONTENT_CHARS = 100_000
MAX_SKILL_FILE_BYTES = 1_048_576  # 1 MiB
VALID_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
ALLOWED_SUBDIRS = frozenset({"references", "templates", "scripts", "assets"})

SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "description": "管理技能 — 创建、更新、删除。技能是程序性记忆——可复用的任务类型方法。新技能保存到 ~/.taiji/skills/。\n\n操作: create（完整 SKILL.md）, patch（old_string/new_string 精确修改）, edit（完整重写）, delete, write_file, remove_file。\n\n创建时机: 复杂任务成功（5+调用）、克服了错误、用户纠正的方法有效、发现非平凡工作流。\n更新时机: 指令过时/错误、OS特定失败、使用中发现缺失步骤或陷阱。\n完成困难/迭代任务后，主动提议保存为技能。跳过简单一次性操作。",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "patch", "edit", "delete", "write_file", "remove_file"],
                "description": "要执行的操作",
            },
            "name": {
                "type": "string",
                "description": "技能名称（小写，连字符/下划线，最大64字符）。必须匹配已有技能才能 patch/edit/delete",
            },
            "content": {
                "type": "string",
                "description": "完整 SKILL.md 内容（YAML 前言 + markdown 主体）。create/'edit' 需要",
            },
            "old_string": {
                "type": "string",
                "description": "要查找的文本（'patch' 需要）。必须唯一，除非 replace_all=true",
            },
            "new_string": {
                "type": "string",
                "description": "替换文本（'patch' 需要）。空字符串可删除匹配文本",
            },
            "replace_all": {
                "type": "boolean",
                "description": "'patch': 替换所有出现而非要求唯一匹配（默认 false）",
            },
            "category": {
                "type": "string",
                "description": "可选分类（如 'development', 'research'）。仅用于 'create'",
            },
            "file_path": {
                "type": "string",
                "description": "技能目录内支持文件的路径。'write_file'/'remove_file': 必须在 references/templates/scripts/assets/ 下。'patch': 可选，默认是 SKILL.md",
            },
            "file_content": {
                "type": "string",
                "description": "文件内容。'write_file' 需要",
            },
        },
        "required": ["action", "name"],
    },
}


# ── 验证 ──────────────────────────────────────────────────────────────────

def _validate_name(name: str) -> Optional[str]:
    if not name:
        return "技能名称不能为空"
    if len(name) > MAX_NAME_LENGTH:
        return f"名称超过 {MAX_NAME_LENGTH} 字符"
    if not VALID_NAME_RE.match(name):
        return f"无效名称 '{name}'。使用小写字母、数字、连字符、点和下划线"
    return None


def _validate_frontmatter(content: str) -> Optional[str]:
    if not content.strip():
        return "内容不能为空"
    if not content.startswith("---"):
        return "SKILL.md 必须以 YAML 前言 (---) 开头"
    end_match = re.search(r'\n---\s*\n', content[3:])
    if not end_match:
        return "未找到 YAML 前言闭合 (---)"
    yaml_content = content[3:end_match.start() + 3]
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return f"YAML 解析错误: {e}"
    if not isinstance(parsed, dict):
        return "前言必须是键值对"
    if "name" not in parsed:
        return "前言必须包含 'name' 字段"
    if "description" not in parsed:
        return "前言必须包含 'description' 字段"
    if len(str(parsed["description"])) > MAX_DESCRIPTION_LENGTH:
        return f"描述超过 {MAX_DESCRIPTION_LENGTH} 字符"
    body = content[end_match.end() + 3:].strip()
    if not body:
        return "SKILL.md 必须在前言后有内容"
    return None


def _validate_file_path(file_path: str) -> Optional[str]:
    if not file_path:
        return "file_path 不能为空"
    normalized = Path(file_path)
    if ".." in normalized.parts:
        return "路径遍历 ('..') 不允许"
    if not normalized.parts or normalized.parts[0] not in ALLOWED_SUBDIRS:
        return f"文件必须在以下目录之一: {', '.join(sorted(ALLOWED_SUBDIRS))}"
    if len(normalized.parts) < 2:
        return f"需要文件路径，如 '{normalized.parts[0]}/myfile.md'"
    return None


def _atomic_write(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        prefix=f".{file_path.name}.tmp.",
        suffix="",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, file_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _clear_prompt_cache():
    """清理技能系统提示缓存"""
    try:
        from taiji_agent.skills.registry import skill_registry
        skill_registry.invalidate_cache()
    except Exception:
        pass


# ── 核心操作 ──────────────────────────────────────────────────────────────

def _create_skill(name: str, content: str, category: str = None) -> dict:
    err = _validate_name(name)
    if err:
        return {"success": False, "error": err}
    err = _validate_frontmatter(content)
    if err:
        return {"success": False, "error": err}

    existing = skill_registry.find_skill_dir(name)
    if existing:
        return {"success": False, "error": f"技能 '{name}' 已存在"}

    skill_dir = SKILLS_DIR / category / name if category else SKILLS_DIR / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_md = skill_dir / "SKILL.md"
    _atomic_write(skill_md, content)
    _clear_prompt_cache()

    return {
        "success": True,
        "message": f"技能 '{name}' 已创建",
        "path": str(skill_dir),
        "skill_md": str(skill_md),
    }


def _edit_skill(name: str, content: str) -> dict:
    err = _validate_frontmatter(content)
    if err:
        return {"success": False, "error": err}

    skill_dir = skill_registry.find_skill_dir(name)
    if not skill_dir:
        return {"success": False, "error": f"技能 '{name}' 未找到"}

    skill_md = skill_dir / "SKILL.md"
    original = skill_md.read_text(encoding="utf-8") if skill_md.exists() else None
    _atomic_write(skill_md, content)
    _clear_prompt_cache()

    return {"success": True, "message": f"技能 '{name}' 已更新", "path": str(skill_dir)}


def _patch_skill(name: str, old_string: str, new_string: str,
                 file_path: str = None, replace_all: bool = False) -> dict:
    if not old_string:
        return {"success": False, "error": "old_string 不能为空"}
    if new_string is None:
        return {"success": False, "error": "new_string 不能为空（空字符串可删除匹配文本）"}

    skill_dir = skill_registry.find_skill_dir(name)
    if not skill_dir:
        return {"success": False, "error": f"技能 '{name}' 未找到"}

    if file_path:
        err = _validate_file_path(file_path)
        if err:
            return {"success": False, "error": err}
        target = skill_dir / file_path
    else:
        target = skill_dir / "SKILL.md"

    if not target.exists():
        return {"success": False, "error": f"文件未找到: {target.name}"}

    content = target.read_text(encoding="utf-8")

    if replace_all:
        new_content = content.replace(old_string, new_string)
        match_count = content.count(old_string)
    else:
        match_count = content.count(old_string)
        if match_count == 0:
            # 尝试模糊匹配
            import difflib
            lines = content.splitlines(True)
            old_lines = old_string.splitlines(True)
            # 简单尝试: 忽略前后空格差异
            stripped_old = old_string.strip()
            stripped_content = content.strip()
            if stripped_old not in stripped_content:
                return {
                    "success": False,
                    "error": f"未找到匹配文本。old_string 在文件中不存在。请用 skill_view('{name}') 查看准确内容后重试。",
                    "file_preview": content[:500],
                }
        if match_count > 1:
            return {
                "success": False,
                "error": f"找到 {match_count} 处匹配。请提供更多上下文使匹配唯一，或使用 replace_all=true",
            }
        new_content = content.replace(old_string, new_string, 1)

    if not file_path:
        err = _validate_frontmatter(new_content)
        if err:
            return {"success": False, "error": f"修补会破坏 SKILL.md 结构: {err}"}

    original = content
    _atomic_write(target, new_content)
    _clear_prompt_cache()

    return {
        "success": True,
        "message": f"已修补 {target.name}（{match_count} 处替换）",
    }


def _delete_skill(name: str) -> dict:
    skill_dir = skill_registry.find_skill_dir(name)
    if not skill_dir:
        return {"success": False, "error": f"技能 '{name}' 未找到"}

    # 检查 pin 保护
    try:
        from taiji_agent.skills.usage import get_record
        rec = get_record(name)
        if rec and rec.get("pinned"):
            return {
                "success": False,
                "error": f"技能 '{name}' 已锁定（pinned），不能删除。请先 unpin",
            }
    except Exception:
        pass

    shutil.rmtree(skill_dir)
    _clear_prompt_cache()

    try:
        from taiji_agent.skills.usage import _tracker
        _tracker.forget(name)
    except Exception:
        pass

    return {"success": True, "message": f"技能 '{name}' 已删除"}


def _write_file(name: str, file_path: str, file_content: str) -> dict:
    err = _validate_file_path(file_path)
    if err:
        return {"success": False, "error": err}
    if not file_content and file_content != "":
        return {"success": False, "error": "file_content 不能为空"}

    content_bytes = len(file_content.encode("utf-8"))
    if content_bytes > MAX_SKILL_FILE_BYTES:
        return {"success": False, "error": f"文件内容 {content_bytes} 字节（限制 1 MiB）"}

    skill_dir = skill_registry.find_skill_dir(name)
    if not skill_dir:
        return {"success": False, "error": f"技能 '{name}' 未找到。先用 action='create' 创建"}

    target = skill_dir / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, file_content)

    return {"success": True, "message": f"文件 '{file_path}' 已写入技能 '{name}'", "path": str(target)}


def _remove_file(name: str, file_path: str) -> dict:
    err = _validate_file_path(file_path)
    if err:
        return {"success": False, "error": err}

    skill_dir = skill_registry.find_skill_dir(name)
    if not skill_dir:
        return {"success": False, "error": f"技能 '{name}' 未找到"}

    target = skill_dir / file_path
    if not target.exists():
        return {"success": False, "error": f"文件 '{file_path}' 在技能 '{name}' 中未找到"}

    target.unlink()

    # 清理空目录
    parent = target.parent
    if parent != skill_dir and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()

    return {"success": True, "message": f"文件 '{file_path}' 已从技能 '{name}' 中移除"}


# ── 主入口 ────────────────────────────────────────────────────────────────

def skill_manage(
    action: str,
    name: str,
    content: str = None,
    category: str = None,
    file_path: str = None,
    file_content: str = None,
    old_string: str = None,
    new_string: str = None,
    replace_all: bool = False,
    **kwargs,
) -> str:
    """管理技能的统一入口"""
    try:
        if action == "create":
            if not content:
                return json.dumps({"success": False, "error": "create 需要 content"}, ensure_ascii=False)
            result = _create_skill(name, content, category)
        elif action == "edit":
            if not content:
                return json.dumps({"success": False, "error": "edit 需要 content"}, ensure_ascii=False)
            result = _edit_skill(name, content)
        elif action == "patch":
            result = _patch_skill(name, old_string, new_string, file_path, replace_all)
        elif action == "delete":
            result = _delete_skill(name)
        elif action == "write_file":
            if not file_path:
                return json.dumps({"success": False, "error": "write_file 需要 file_path"}, ensure_ascii=False)
            if file_content is None:
                return json.dumps({"success": False, "error": "write_file 需要 file_content"}, ensure_ascii=False)
            result = _write_file(name, file_path, file_content)
        elif action == "remove_file":
            if not file_path:
                return json.dumps({"success": False, "error": "remove_file 需要 file_path"}, ensure_ascii=False)
            result = _remove_file(name, file_path)
        else:
            result = {"success": False, "error": f"未知操作 '{action}'。可用: create, edit, patch, delete, write_file, remove_file"}

        # 成功后记录来源
        if result.get("success"):
            try:
                from taiji_agent.skills.provenance import is_background_review
                from taiji_agent.skills.usage import bump_patch, mark_agent_created, _tracker
                if action == "create" and is_background_review():
                    mark_agent_created(name)
                elif action in {"patch", "edit", "write_file", "remove_file"}:
                    bump_patch(name)
                elif action == "delete":
                    _tracker.forget(name)
            except Exception:
                pass

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
