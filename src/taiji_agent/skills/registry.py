"""技能注册表 — 扫描和加载 SKILL.md 文件

多目录支持:
  - ~/.taiji/skills/        主技能目录
  - 外部目录 (通过 config 配置)
  - 插件技能

渐进披露架构:
  - 元数据 (name <= 64 chars, description <= 1024 chars) → skills_list
  - 完整内容 → skill_view
  - 链接文件 → skill_view(name, file_path)
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

TAIJI_HOME = Path.home() / ".taiji"
SKILLS_DIR = TAIJI_HOME / "skills"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

_PLATFORM_MAP = {"macos": "darwin", "linux": "linux", "windows": "win32"}
_EXCLUDED_DIRS = frozenset({".git", ".github", ".hub", ".archive"})

_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "you are now",
    "disregard your",
    "forget your instructions",
    "new instructions:",
    "system prompt:",
    "<system>",
    "]]>",
]

_ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SkillRegistry:
    """技能注册表"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._external_dirs: list[Path] = []
        self._cache: dict[str, dict] = {}
        self._cache_valid = False

    @property
    def all_dirs(self) -> list[Path]:
        dirs = [self.skills_dir]
        dirs.extend(self._external_dirs)
        return dirs

    def add_external_dir(self, path: Path):
        if path not in self._external_dirs and path.exists():
            self._external_dirs.append(path)
            self._cache_valid = False

    def invalidate_cache(self):
        self._cache_valid = False

    def parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """解析 YAML 前言"""
        if not content.startswith("---"):
            return {}, content
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return {}, content
        try:
            frontmatter = yaml.safe_load(content[3:end_idx]) or {}
            body = content[end_idx + 3:].strip()
            return frontmatter, body
        except yaml.YAMLError:
            return {}, content[end_idx + 3:].strip()

    def _skill_matches_platform(self, frontmatter: dict) -> bool:
        platforms = frontmatter.get("platforms")
        if not platforms:
            return True
        if isinstance(platforms, str):
            platforms = [platforms]
        current = _PLATFORM_MAP.get(os.uname().sysname.lower(), os.uname().sysname.lower())
        return any(_PLATFORM_MAP.get(p, p) == current for p in platforms)

    def _scan_injection(self, content: str) -> list[str]:
        content_lower = content.lower()
        return [p for p in _INJECTION_PATTERNS if p in content_lower]

    def find_all_skills(self, skip_disabled: bool = False) -> list[dict[str, Any]]:
        """扫描所有技能,返回带元数据的列表 (Tier 1)"""
        if self._cache_valid and not skip_disabled:
            return list(self._cache.values())

        skills = []
        seen_names: set = set()

        for scan_dir in self.all_dirs:
            if not scan_dir.exists():
                continue
            for skill_md in scan_dir.rglob("SKILL.md"):
                if any(p in _EXCLUDED_DIRS for p in skill_md.parts):
                    continue
                skill_dir = skill_md.parent
                try:
                    content = skill_md.read_text(encoding="utf-8")[:4000]
                    frontmatter, body = self.parse_frontmatter(content)

                    if not self._skill_matches_platform(frontmatter):
                        continue

                    name = str(frontmatter.get("name", skill_dir.name))[:MAX_NAME_LENGTH]
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    description = frontmatter.get("description", "")
                    if not description:
                        for line in body.strip().split("\n"):
                            line = line.strip()
                            if line and not line.startswith("#"):
                                description = line
                                break
                    if len(description) > MAX_DESCRIPTION_LENGTH:
                        description = description[:MAX_DESCRIPTION_LENGTH - 3] + "..."

                    # 提取分类
                    category = None
                    try:
                        rel = skill_dir.relative_to(scan_dir)
                        parts = rel.parts
                        if len(parts) >= 2:
                            category = parts[0]
                    except ValueError:
                        pass

                    # 提取标签
                    meta = frontmatter.get("metadata", {}) or {}
                    taiji_meta = meta.get("taiji", {}) or {}
                    tags = taiji_meta.get("tags") or frontmatter.get("tags", [])
                    if isinstance(tags, str):
                        tags = [t.strip() for t in tags.split(",")]

                    skill_entry = {
                        "name": name,
                        "description": description,
                        "category": category,
                        "tags": tags if isinstance(tags, list) else [],
                        "path": str(skill_dir),
                        "version": frontmatter.get("version", "1.0.0"),
                    }

                    skills.append(skill_entry)

                    # 缓存
                    self._cache[name] = skill_entry

                except (UnicodeDecodeError, PermissionError) as e:
                    logger.debug("Skip skill file %s: %s", skill_md, e)
                    continue

        self._cache_valid = True
        return skills

    def load_skill(self, name: str, file_path: Optional[str] = None) -> Optional[dict[str, Any]]:
        """加载技能完整内容 (Tier 2-3)"""
        for scan_dir in self.all_dirs:
            if not scan_dir.exists():
                continue
            for skill_md in scan_dir.rglob("SKILL.md"):
                if skill_md.parent.name == name or skill_md.stem == name:
                    return self._load_skill_from_path(skill_md, file_path, name)
        return None

    def _load_skill_from_path(
        self, skill_md: Path, file_path: Optional[str], name: str
    ) -> Optional[dict[str, Any]]:
        skill_dir = skill_md.parent
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            return None

        frontmatter, body = self.parse_frontmatter(content)

        # 安全检查
        injections = self._scan_injection(content)
        if injections:
            logger.warning("Skill '%s' contains potential injection patterns: %s", name, injections)

        # 按需加载特定文件
        if file_path:
            target = skill_dir / file_path
            # 路径遍历防护
            try:
                target.resolve().relative_to(skill_dir.resolve())
            except ValueError:
                return {"success": False, "error": "Path traversal detected"}
            if not target.exists():
                return {
                    "success": False,
                    "error": f"File '{file_path}' not found in skill '{name}'",
                    "available_files": self._list_support_files(skill_dir),
                }
            try:
                file_content = target.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return {
                    "success": True,
                    "name": name,
                    "file": file_path,
                    "content": f"[Binary file: {target.name}, size: {target.stat().st_size} bytes]",
                    "is_binary": True,
                }
            return {
                "success": True,
                "name": name,
                "file": file_path,
                "content": file_content,
            }

        # 解析 tags
        meta = frontmatter.get("metadata", {}) or {}
        taiji_meta = meta.get("taiji", {}) or {}
        tags = taiji_meta.get("tags") or frontmatter.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        # 链接文件
        linked_files = self._list_support_files(skill_dir)

        # 解析必需环境变量
        required_env = frontmatter.get("required_environment_variables", [])
        if isinstance(required_env, dict):
            required_env = [required_env]
        elif isinstance(required_env, str):
            required_env = [{"name": required_env}]

        return {
            "success": True,
            "name": frontmatter.get("name", name),
            "description": frontmatter.get("description", ""),
            "version": frontmatter.get("version", "1.0.0"),
            "tags": tags if isinstance(tags, list) else [],
            "content": content,
            "body": body,
            "path": str(skill_md),
            "skill_dir": str(skill_dir),
            "linked_files": linked_files if linked_files else None,
            "required_environment_variables": required_env,
        }

    def _list_support_files(self, skill_dir: Path) -> dict[str, list[str]]:
        """列出技能目录中的支持文件"""
        result = {}
        for subdir_name in ["references", "templates", "scripts", "assets"]:
            subdir = skill_dir / subdir_name
            if subdir.exists():
                files = [
                    str(f.relative_to(skill_dir))
                    for f in subdir.rglob("*")
                    if f.is_file()
                ]
                if files:
                    result[subdir_name] = files
        return result

    def find_skill_dir(self, name: str) -> Optional[Path]:
        """查找技能目录"""
        for scan_dir in self.all_dirs:
            if not scan_dir.exists():
                continue
            for skill_md in scan_dir.rglob("SKILL.md"):
                if skill_md.parent.name == name:
                    return skill_md.parent
        return None

    def get_categories(self) -> list[str]:
        skills = self.find_all_skills()
        cats = {s.get("category") for s in skills if s.get("category")}
        return sorted(cats)


# 全局注册表实例
skill_registry = SkillRegistry()
