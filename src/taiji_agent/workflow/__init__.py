"""
Taiji Agent Workflow Module
状态工作流引擎 - 参考LangGraph设计
"""

from .engine import (
    NodeResult,
    WorkflowConfig,
    WorkflowEngine,
    WorkflowState,
)
from .graph import (
    ConditionalEdge,
    Edge,
    Node,
    StateReducer,
    WorkflowGraph,
)

__all__ = [
    "WorkflowEngine",
    "WorkflowState",
    "WorkflowConfig",
    "NodeResult",
    "WorkflowGraph",
    "Node",
    "Edge",
    "ConditionalEdge",
    "StateReducer",
]
