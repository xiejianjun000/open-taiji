"""
Taiji Agent Handoffs Module
Agent智能体交接系统 - 参考OpenAI Agents SDK Handoffs设计
"""

from .core import (
    Handoff,
    HandoffConfig,
    HandoffContext,
    HandoffDecision,
    HandoffManager,
    HandoffResult,
)
from .registry import AgentRegistry

__all__ = [
    "Handoff",
    "HandoffConfig",
    "HandoffManager",
    "HandoffResult",
    "HandoffContext",
    "HandoffDecision",
    "AgentRegistry",
]
