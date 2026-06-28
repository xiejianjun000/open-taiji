"""梦境系统 — 来自 OpenClaw memory-core 的后台记忆消化

当 Agent 处于空闲状态时，梦境系统自动运行：
  - deep:  深度梦境 — 对近期对话进行深度记忆提取和技能提炼
  - light: 轻度梦境 — 快速回顾最近对话，更新用户画像
  - rem:   快速眼动 — 关联记忆片段，发现模式

配置:
  memory_core:
    dreaming:
      enabled: true
      interval_hours: 4
      deep_enabled: true
"""

from taiji_agent.dream.engine import DreamEngine, DreamConfig, DreamType
from taiji_agent.dream.digest import MemoryDigester

__all__ = ["DreamEngine", "DreamConfig", "DreamType", "MemoryDigester"]
