"""
技能系统 - Skills Hub
来自 Hermes Agent
支持技能浏览、安装、创建、自改进
"""

from __future__ import annotations

import builtins
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import yaml

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """技能定义"""

    id: str
    name: str
    description: str
    instructions: str
    tools: list[str] = field(default_factory=list)
    category: str = "general"
    version: str = "1.0.0"
    author: str = "system"
    created_at: str = ""
    updated_at: str = ""
    auto_created: bool = False
    confidence: float = 0.5
    usage_count: int = 0
    success_rate: float = 1.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": self.tools,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "auto_created": self.auto_created,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Skill:
        return cls(**data)


class SkillMarket:
    """技能市场 - 预置技能库"""

    BUNDLED_SKILLS = {
        "github-auth": {
            "name": "GitHub 认证",
            "description": "配置 GitHub 认证，支持 HTTPS Token 和 SSH Key",
            "instructions": """# GitHub 认证助手

## 功能
- 验证 GitHub Token 有效性
- 配置 GitHub SSH Key
- 检查仓库访问权限

## 使用方式
```
使用 github-auth 技能进行 GitHub 认证配置
```

## 注意事项
- 确保 Token 具有 repo 权限
- SSH Key 需要添加到 GitHub 账户
""",
            "tools": ["shell"],
            "category": "开发",
        },
        "github-pr-workflow": {
            "name": "GitHub PR 工作流",
            "description": "自动化 PR 创建、审查和合并流程",
            "instructions": """# GitHub PR 工作流助手

## 功能
- 创建 Pull Request
- 检查 PR 状态
- 自动审查代码变更
- 合并 PR

## 流程
1. 检查当前分支状态
2. 创建 PR 并添加描述
3. 等待审查
4. 合并或关闭 PR

## 注意事项
- 确保分支已同步
- 添加清晰的 PR 描述
""",
            "tools": ["shell", "git_status", "git_log"],
            "category": "开发",
        },
        "code-review": {
            "name": "代码审查",
            "description": "自动化代码审查，发现潜在问题和改进点",
            "instructions": """# 代码审查助手

## 功能
- 代码质量分析
- 潜在 Bug 检测
- 性能问题识别
- 安全漏洞扫描
- 代码风格检查

## 审查维度
1. 正确性 - 逻辑是否正确
2. 性能 - 是否有性能瓶颈
3. 安全 - 是否有安全风险
4. 可维护性 - 代码是否清晰
5. 测试覆盖 - 是否有充分测试

## 输出格式
```
## 审查报告

### 问题列表
1. [严重] 问题描述
2. [中等] 问题描述

### 建议
- 优化建议
```
""",
            "tools": ["file_read", "shell", "git_log"],
            "category": "开发",
        },
        "web-research": {
            "name": "网络研究",
            "description": "深度网络搜索和信息提取",
            "instructions": """# 网络研究助手

## 功能
- 搜索网络信息
- 提取网页内容
- 总结研究发现

## 工作流程
1. 搜索相关关键词
2. 提取高质量来源
3. 综合分析信息
4. 生成研究报告

## 注意事项
- 验证信息来源可靠性
- 标注引用来源
- 避免偏见
""",
            "tools": ["web_search", "web_extract", "memory_save"],
            "category": "研究",
        },
        "document-writer": {
            "name": "文档写作",
            "description": "专业文档写作辅助",
            "instructions": """# 文档写作助手

## 功能
- 技术文档撰写
- API 文档生成
- README 优化
- 变更日志编写

## 文档结构
1. 概述
2. 快速开始
3. 详细说明
4. API 参考
5. 示例代码
6. 常见问题

## 风格指南
- 使用简洁语言
- 添加代码示例
- 保持更新
""",
            "tools": ["file_read", "file_write", "memory_save"],
            "category": "创作",
        },
        "chinese-context": {
            "name": "中文语境适配",
            "description": "优化中文理解和文化背景知识",
            "instructions": """# 中文语境适配助手

## 功能
- 中文表达优化
- 文化背景理解
- 本地化建议

## 语境要素
1. 中文表达习惯
2. 技术术语对照
3. 文化差异注意
4. 本地化最佳实践

## 应用场景
- 中文文档优化
- 中英翻译润色
- 本地化建议
""",
            "tools": ["memory_save"],
            "category": "本地化",
        },
        "planning-with-files": {
            "name": "规划与文件追踪",
            "description": "跨会话任务规划和进度追踪",
            "instructions": """# 规划与文件追踪助手

## 核心文件
- `task_plan.md` - 任务计划
- `findings.md` - 研究发现
- `progress.md` - 进度记录

## 工作流程
1. 创建/更新 task_plan.md
2. 记录研究发现到 findings.md
3. 更新进度到 progress.md

## 文件格式
```markdown
# 任务计划 (task_plan.md)
- [ ] 任务1
- [x] 任务2

# 研究发现 (findings.md)
## 发现1
内容...

# 进度记录 (progress.md)
## 2024-01-01
- 完成了XX
- 遇到YY问题
```
""",
            "tools": ["file_read", "file_write", "file_list"],
            "category": "规划",
        },
    }

    def browse(self, category: Optional[str] = None) -> list[dict]:
        """浏览技能"""
        skills = []
        for skill_id, data in self.BUNDLED_SKILLS.items():
            if category is None or data.get("category") == category:
                skills.append(
                    {
                        "id": skill_id,
                        **data,
                    }
                )
        return skills

    def get(self, skill_id: str) -> Optional[dict]:
        """获取技能"""
        return self.BUNDLED_SKILLS.get(skill_id)


class SkillManager:
    """
    技能管理器

    管理技能的安装、使用、创建、自改进
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        if skills_dir is None:
            self.skills_dir = Path.home() / ".taiji_agent" / "skills"
        else:
            self.skills_dir = Path(skills_dir)

        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self._skills: dict[str, Skill] = {}
        self._market: SkillMarket = SkillMarket()
        self._load_skills()

    def _load_skills(self):
        """加载技能"""
        for skill_file in self.skills_dir.glob("*.yaml"):
            try:
                with open(skill_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        skill = Skill.from_dict(data)
                        self._skills[skill.id] = skill
            except Exception as e:
                logger.error(f"Load skill error: {e}")

    def _save_skill(self, skill: Skill):
        """保存技能"""
        skill_file = self.skills_dir / f"{skill.id}.yaml"
        with open(skill_file, "w", encoding="utf-8") as f:
            yaml.dump(skill.to_dict(), f, allow_unicode=True, default_flow_style=False)

    def list(self, category: Optional[str] = None) -> list[Skill]:
        """列出技能"""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return sorted(skills, key=lambda s: -s.usage_count)

    def get(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(skill_id)

    def install(self, skill_id: str) -> bool:
        """安装技能"""
        market_data = self._market.get(skill_id)
        if not market_data:
            logger.error(f"Skill not found in market: {skill_id}")
            return False

        skill = Skill(
            id=skill_id,
            name=market_data["name"],
            description=market_data["description"],
            instructions=market_data["instructions"],
            tools=market_data.get("tools", []),
            category=market_data.get("category", "general"),
            author="market",
        )

        self._skills[skill_id] = skill
        self._save_skill(skill)
        logger.info(f"Installed skill: {skill_id}")
        return True

    def install_bundled(self):
        """安装所有预置技能"""
        for skill_id in self._market.BUNDLED_SKILLS.keys():
            self.install(skill_id)

    async def create(
        self,
        name: str,
        description: str,
        instructions: str,
        tools: builtins.Optional[list[str]] = None,
        category: str = "custom",
        source_task: Optional[str] = None,
    ) -> Skill:
        """从任务创建新技能"""
        skill_id = self._generate_skill_id(name)

        skill = Skill(
            id=skill_id,
            name=name,
            description=description,
            instructions=instructions,
            tools=tools or [],
            category=category,
            author="system",
            auto_created=True,
            confidence=0.7,
            created_at=datetime.now().isoformat(),
        )

        if source_task:
            skill.instructions += f"\n\n## 来源任务\n{source_task}"

        self._skills[skill_id] = skill
        self._save_skill(skill)

        logger.info(f"Created skill: {skill_id}")
        return skill

    async def improve(self, skill_id: str, new_patterns: builtins.list[str]) -> Optional[Skill]:
        """改进技能"""
        skill = self._skills.get(skill_id)
        if not skill:
            return None

        skill.instructions += "\n\n## 改进模式\n"
        for pattern in new_patterns:
            skill.instructions += f"- {pattern}\n"

        skill.confidence = min(skill.confidence + 0.05, 1.0)
        skill.updated_at = datetime.now().isoformat()

        self._save_skill(skill)
        logger.info(f"Improved skill: {skill_id}")
        return skill

    def use(self, skill_id: str) -> Optional[str]:
        """使用技能"""
        skill = self._skills.get(skill_id)
        if not skill:
            return None

        skill.usage_count += 1
        self._save_skill(skill)

        return skill.instructions

    def delete(self, skill_id: str) -> bool:
        """删除技能"""
        if skill_id not in self._skills:
            return False

        skill_file = self.skills_dir / f"{skill_id}.yaml"
        if skill_file.exists():
            skill_file.unlink()

        del self._skills[skill_id]
        logger.info(f"Deleted skill: {skill_id}")
        return True

    def _generate_skill_id(self, name: str) -> str:
        """生成技能 ID"""
        import re

        base_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        # 处理纯中文等无 ASCII 字符的名称
        if not base_id:
            base_id = "custom"
        if base_id in self._skills:
            return f"{base_id}-{len(self._skills)}"
        return base_id

    def browse_market(self, category: Optional[str] = None) -> builtins.list[dict[str, Any]]:
        """浏览技能市场"""
        return self._market.browse(category)

    def get_stats(self) -> dict:
        """获取统计信息"""
        skills = list(self._skills.values())
        return {
            "total": len(skills),
            "by_category": {cat: len([s for s in skills if s.category == cat]) for cat in {s.category for s in skills}},
            "auto_created": len([s for s in skills if s.auto_created]),
            "total_usage": sum(s.usage_count for s in skills),
            "avg_confidence": sum(s.confidence for s in skills) / len(skills) if skills else 0,
        }


class SkillCreator:
    """
    技能创建器 - 元技能

    从对话中提取技能
    """

    def __init__(self, skill_manager: SkillManager):
        self.manager = skill_manager

    async def extract_from_conversation(
        self,
        task: str,
        conversation: list[dict],
        successful_result: str,
    ) -> Optional[Skill]:
        """从对话中提取技能"""
        complexity_score = self._estimate_complexity(task, conversation)

        if complexity_score < 0.6:
            return None

        tools_used = self._extract_tools_used(conversation)

        skill_name = self._generate_skill_name(task)
        skill_description = self._summarize_task(task, successful_result)
        skill_instructions = self._generate_instructions(task, successful_result, tools_used)

        skill = await self.manager.create(
            name=skill_name,
            description=skill_description,
            instructions=skill_instructions,
            tools=tools_used,
            category=self._infer_category(task),
            source_task=task,
        )

        return skill

    def _estimate_complexity(self, task: str, conversation: list[dict]) -> float:
        """估算复杂度"""
        score = 0.0

        score += min(len(conversation) * 0.05, 0.3)

        complex_keywords = ["分析", "设计", "实现", "优化", "debug", "refactor"]
        for kw in complex_keywords:
            if kw.lower() in task.lower():
                score += 0.15

        score += min(len(task) / 500, 0.2)

        return min(score, 1.0)

    def _extract_tools_used(self, conversation: list[dict]) -> list[str]:
        """提取使用的工具"""
        tools = set()
        for msg in conversation:
            content = msg.get("content", "")
            if "file_" in content:
                tools.add("file_read")
            if "shell" in content.lower() or "command" in content.lower():
                tools.add("shell")
            if "git" in content.lower():
                tools.add("git_status")
        return list(tools)

    def _generate_skill_name(self, task: str) -> str:
        """生成技能名称"""
        import re

        words = re.findall(r"[\w]+", task)
        if len(words) > 5:
            return " ".join(words[:5])
        return task

    def _summarize_task(self, task: str, result: str) -> str:
        """总结任务"""
        return f"从任务 '{task[:50]}...' 提取的技能，用于处理类似任务"

    def _generate_instructions(
        self,
        task: str,
        result: str,
        tools: list[str],
    ) -> str:
        """生成技能说明"""
        return f"""# 技能说明

## 任务
{task}

## 成功结果
{result[:500]}

## 使用工具
{", ".join(tools) if tools else "无"}

## 执行步骤
1. 分析任务要求
2. 规划执行步骤
3. 使用适当工具
4. 验证结果
"""

    def _infer_category(self, task: str) -> str:
        """推断类别"""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["代码", "code", "debug", "refactor"]):
            return "开发"
        if any(kw in task_lower for kw in ["搜索", "search", "研究", "research"]):
            return "研究"
        if any(kw in task_lower for kw in ["文档", "document", "写", "write"]):
            return "创作"

        return "general"
