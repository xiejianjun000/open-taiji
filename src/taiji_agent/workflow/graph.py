"""
Workflow Graph - 工作流图结构
支持节点、边、条件边的声明式定义
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import Any, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar("T")


class NodeType(StrEnum):
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    CONDITION = "condition"
    MERGE = "merge"
    END = "end"


@dataclass
class Node:
    name: str
    node_type: NodeType
    handler: Optional[Callable] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Edge:
    source: str
    target: str
    condition: Callable[[Any], bool] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConditionalEdge:
    source: str
    routes: dict[str, str]
    default: str
    router_func: Callable[[Any], str]


@dataclass
class StateReducer:
    field_name: str
    reducer_func: Callable[[list[Any]], Any]

    def reduce(self, values: list[Any]) -> Any:
        return self.reducer_func(values)


class WorkflowGraph:
    def __init__(self, name: str = "workflow"):
        self.name = name
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._conditional_edges: dict[str, ConditionalEdge] = {}
        self._reducers: dict[str, StateReducer] = {}
        self._entry_point: Optional[str] = None
        self._end_nodes: list[str] = []

    def add_node(
        self,
        name: str,
        node_type: NodeType = NodeType.AGENT,
        handler: Optional[Callable] = None,
        **metadata,
    ) -> WorkflowGraph:
        node = Node(
            name=name,
            node_type=node_type,
            handler=handler,
            metadata=metadata,
        )
        self._nodes[name] = node
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Callable[[Any], bool] | None = None,
    ) -> WorkflowGraph:
        if source not in self._nodes:
            raise ValueError(f"Node not found: {source}")
        if target not in self._nodes:
            raise ValueError(f"Node not found: {target}")
        edge = Edge(source=source, target=target, condition=condition)
        self._edges.append(edge)
        return self

    def add_conditional_edge(
        self,
        source: str,
        routes: dict[str, str],
        default: Optional[str] = None,
    ) -> WorkflowGraph:
        if source not in self._nodes:
            raise ValueError(f"Node not found: {source}")
        for target in routes.values():
            if target not in self._nodes:
                raise ValueError(f"Target node not found: {target}")

        def router(state: Any) -> str:
            for route_name, target in routes.items():
                check_key = f"_check_{route_name}"
                if hasattr(self, check_key):
                    check_func = getattr(self, check_key)
                    if check_func(state):
                        return target
            return default or list(routes.values())[0]

        self._conditional_edges[source] = ConditionalEdge(
            source=source,
            routes=routes,
            default=default or list(routes.values())[0],
            router_func=router,
        )
        return self

    def set_entry_point(self, node_name: str) -> WorkflowGraph:
        if node_name not in self._nodes:
            raise ValueError(f"Node not found: {node_name}")
        self._entry_point = node_name
        return self

    def set_end_nodes(self, *node_names: str) -> WorkflowGraph:
        for name in node_names:
            if name not in self._nodes:
                raise ValueError(f"Node not found: {name}")
        self._end_nodes = list(node_names)
        return self

    def add_reducer(self, field_name: str, reducer_func: Callable) -> WorkflowGraph:
        self._reducers[field_name] = StateReducer(field_name, reducer_func)
        return self

    def compile(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nodes": {name: node.node_type.value for name, node in self._nodes.items()},
            "edges": [{"source": e.source, "target": e.target} for e in self._edges],
            "conditional_edges": {source: ce.routes for source, ce in self._conditional_edges.items()},
            "entry_point": self._entry_point,
            "end_nodes": self._end_nodes,
            "reducers": list(self._reducers.keys()),
        }

    def visualize_mermaid(self) -> str:
        lines = [f"%% {self.name}"]
        lines.append("graph TD")
        for name, node in self._nodes.items():
            if node.node_type == NodeType.END:
                lines.append(f"    {name}(({name}))")
            elif node.node_type == NodeType.CONDITION:
                lines.append(f"    {name}{{{name}}}")
            elif node.node_type == NodeType.MERGE:
                lines.append(f"    {name}>{{name}}]")
            else:
                lines.append(f"    {name}[{name}]")
        for edge in self._edges:
            lines.append(f"    {edge.source} --> {edge.target}")
        for source, ce in self._conditional_edges.items():
            lines.append(f"    {source} -.-> {source}_cond")
            lines.append(f"    {source}_cond{{?}}")
            for route, target in ce.routes.items():
                lines.append(f"    {source}_cond -->|'{route}'| {target}")
            lines.append(f"    {source}_cond -.->|default| {ce.default}")
        if self._entry_point:
            lines.append(f"    START([Start]) --> {self._entry_point}")
        for end in self._end_nodes:
            lines.append(f"    {end} --> END([End])")
        return "\n".join(lines)

    def visualize_ascii(self) -> str:
        lines = [f"Workflow: {self.name}", "=" * 40]
        lines.append(f"\nNodes ({len(self._nodes)}):")
        for name, node in self._nodes.items():
            marker = ""
            if name == self._entry_point:
                marker = " [ENTRY]"
            if name in self._end_nodes:
                marker = " [END]"
            lines.append(f"  • {name} ({node.node_type.value}){marker}")
        lines.append(f"\nEdges ({len(self._edges)}):")
        for edge in self._edges:
            lines.append(f"  {edge.source} → {edge.target}")
        if self._conditional_edges:
            lines.append(f"\nConditional Edges ({len(self._conditional_edges)}):")
            for source, ce in self._conditional_edges.items():
                routes_str = ", ".join(f"{k}→{v}" for k, v in ce.routes.items())
                lines.append(f"  {source} ? [{routes_str}] (default: {ce.default})")
        return "\n".join(lines)
