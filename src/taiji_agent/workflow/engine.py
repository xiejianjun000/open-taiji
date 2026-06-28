"""
Workflow Engine - 状态工作流引擎
参考LangGraph状态图设计
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=dict[str, Any])


class NodeResult:
    def __init__(
        self,
        node_name: str,
        output: Any,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self.node_name = node_name
        self.output = output
        self.success = success
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.now()


@dataclass
class WorkflowState:
    current_node: str
    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    checkpoint_id: Optional[str] = None

    def add_history(self, node: str, action: str, data: Any) -> None:
        self.history.append(
            {
                "node": node,
                "action": action,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def add_error(self, error: str) -> None:
        self.errors.append(error)


@dataclass
class WorkflowConfig:
    name: str = "workflow"
    max_iterations: int = 100
    max_retry: int = 3
    timeout_seconds: int = 3600
    enable_cycles: bool = True
    checkpoint_enabled: bool = True
    interrupt_on_nodes: list[str] = field(default_factory=list)


class WorkflowEngine:
    def __init__(self, config: Optional[WorkflowConfig] = None):
        self.config = config or WorkflowConfig()
        self._nodes: dict[str, Callable[..., Any]] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, Callable[[WorkflowState], str]] = {}
        self._interrupt_nodes: set[str] = set()
        self._interrupted: dict[str, asyncio.Event] = {}
        self._state: Optional[WorkflowState] = None

    def add_node(
        self,
        name: str,
        func: Callable[..., Any],
    ) -> None:
        self._nodes[name] = func
        logger.info(f"Node added: {name}")

    def add_edge(
        self,
        source: str,
        target: str,
    ) -> None:
        if source not in self._nodes:
            raise ValueError(f"Source node not found: {source}")
        if target not in self._nodes:
            raise ValueError(f"Target node not found: {target}")
        self._edges[source] = target
        logger.info(f"Edge added: {source} -> {target}")

    def add_conditional_edges(
        self,
        source: str,
        conditions: dict[str, str],
        default: str,
    ) -> None:
        if source not in self._nodes:
            raise ValueError(f"Source node not found: {source}")

        def router(state: WorkflowState) -> str:
            for condition_name, target in conditions.items():
                if f"_check_{condition_name}" in dir(self):
                    check_func = getattr(self, f"_check_{condition_name}")
                    if check_func(state):
                        return target
            return default

        self._conditional_edges[source] = router
        for target in conditions.values():
            if target not in self._nodes:
                raise ValueError(f"Target node not found: {target}")
        logger.info(f"Conditional edges added from {source}")

    def interrupt_at(self, node_names: list[str]) -> None:
        self._interrupt_nodes.update(node_names)
        if self.config.checkpoint_enabled:
            self.config.interrupt_on_nodes.extend(node_names)

    async def _execute_node(
        self,
        node_name: str,
        state: WorkflowState,
    ) -> NodeResult:
        if node_name not in self._nodes:
            return NodeResult(
                node_name=node_name,
                output=None,
                success=False,
                error=f"Node not found: {node_name}",
            )
        node_func = self._nodes[node_name]
        try:
            if asyncio.iscoroutinefunction(node_func):
                result = await node_func(state)
            else:
                result = node_func(state)
            state.add_history(node_name, "executed", result)
            return NodeResult(node_name=node_name, output=result, success=True)
        except Exception as e:
            error_msg = f"Node {node_name} error: {str(e)}"
            state.add_error(error_msg)
            logger.error(error_msg)
            return NodeResult(node_name=node_name, output=None, success=False, error=str(e))

    def _get_next_node(self, current_node: str, state: WorkflowState) -> Optional[str]:
        if current_node in self._conditional_edges:
            return self._conditional_edges[current_node](state)
        return self._edges.get(current_node)

    async def run(
        self,
        initial_state: Optional[dict[str, Any]] = None,
        start_node: Optional[str] = None,
    ) -> WorkflowState:
        state = WorkflowState(
            current_node=start_node or self._get_start_node(),
            metadata=initial_state or {},
        )
        self._state = state
        iterations = 0
        while iterations < self.config.max_iterations:
            iterations += 1
            current = state.current_node
            if current not in self._nodes:
                logger.warning("No more nodes, workflow complete")
                break
            if current in self._interrupt_nodes:
                self._interrupted[current] = asyncio.Event()
                logger.info(f"Workflow interrupted at: {current}")
                return state
            result = await self._execute_node(current, state)
            if not result.success and iterations >= self.config.max_retry:
                state.add_error(f"Max retries exceeded at {current}")
                break
            next_node = self._get_next_node(current, state)
            if next_node is None:
                logger.info("Workflow complete, no more edges")
                break
            state.current_node = next_node
        return state

    def _get_start_node(self) -> str:
        if not self._nodes:
            raise ValueError("No nodes defined")
        target_nodes = set()
        for source in self._edges:
            target_nodes.add(self._edges[source])
        for node in self._nodes:
            if node not in self._edges and node in target_nodes:
                continue
            if node not in self._edges:
                return node
        return list(self._nodes.keys())[0]

    def resume(self, state: Optional[dict[str, Any]] = None) -> WorkflowState:
        if not self._state:
            raise ValueError("No interrupted workflow to resume")
        if state:
            self._state.metadata.update(state)
        current = self._state.current_node
        if current in self._interrupted:
            self._interrupted[current].set()
            del self._interrupted[current]
        logger.info(f"Workflow resumed at: {current}")
        return self._state

    def get_state(self) -> Optional[WorkflowState]:
        return self._state

    def get_nodes(self) -> list[str]:
        return list(self._nodes.keys())

    def get_edges(self) -> dict[str, str]:
        return self._edges.copy()

    def visualize_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self._nodes:
            lines.append(f"    {node}[({node})]")
        for source, target in self._edges.items():
            lines.append(f"    {source} --> {target}")
        for source, _router in self._conditional_edges.items():
            lines.append(f"    {source} -.-> {source}_router")
            lines.append(f"    {source}_router{{Router}}")
        return "\n".join(lines)
