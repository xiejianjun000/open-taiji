"""后台审查系统 — 来自 Hermes Agent 的自我改进机制

每次对话后自动运行:
  1. 审查对话内容
  2. 提取关键记忆
  3. 创建/更新技能
  4. 馆长定期维护

三层自我改进:
  Layer 1: Background Review — 每次对话后审查
  Layer 2: Skill Manager   — 代理自主管理技能
  Layer 3: Curator         — 定期技能库维护
"""

from taiji_agent.review.engine import BackgroundReviewEngine
from taiji_agent.review.curator import SkillCurator

__all__ = ["BackgroundReviewEngine", "SkillCurator"]
