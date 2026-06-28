"""
Agent Registry - Agent注册表
提供Agent注册、查找和管理功能
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentMetadata:
    agent_id: str
    name: str
    role: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    custom_data: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    _instance: Optional[AgentRegistry] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._agents: dict[str, Any] = {}
        self._metadata: dict[str, AgentMetadata] = {}
        self._role_index: dict[str, list[str]] = {}
        self._tag_index: dict[str, list[str]] = {}
        self._initialized = True

    def register(
        self,
        agent: Any,
        name: str,
        role: str,
        description: str = "",
        capabilities: Optional[list[str]] = None,
        languages: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        **custom_data,
    ) -> str:
        agent_id = str(uuid.uuid4())[:8]
        metadata = AgentMetadata(
            agent_id=agent_id,
            name=name,
            role=role,
            description=description,
            capabilities=capabilities or [],
            languages=languages or ["en", "zh"],
            tags=tags or [],
            custom_data=custom_data,
        )
        self._agents[agent_id] = agent
        self._metadata[agent_id] = metadata
        if role not in self._role_index:
            self._role_index[role] = []
        self._role_index[role].append(agent_id)
        for tag in metadata.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            self._tag_index[tag].append(agent_id)
        logger.info(f"Agent registered: {name} ({agent_id})")
        return agent_id

    def unregister(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        metadata = self._metadata[agent_id]
        del self._agents[agent_id]
        del self._metadata[agent_id]
        if metadata.role in self._role_index:
            self._role_index[metadata.role].remove(agent_id)
        for tag in metadata.tags:
            if tag in self._tag_index:
                self._tag_index[tag].remove(agent_id)
        logger.info(f"Agent unregistered: {agent_id}")
        return True

    def get(self, agent_id: str) -> Optional[Any]:
        return self._agents.get(agent_id)

    def get_by_name(self, name: str) -> Optional[Any]:
        for agent_id, metadata in self._metadata.items():
            if metadata.name == name:
                return self._agents.get(agent_id)
        return None

    def find_by_role(self, role: str) -> list[tuple[str, Any, AgentMetadata]]:
        agent_ids = self._role_index.get(role, [])
        return [(aid, self._agents[aid], self._metadata[aid]) for aid in agent_ids if aid in self._agents]

    def find_by_tag(self, tag: str) -> list[tuple[str, Any, AgentMetadata]]:
        agent_ids = self._tag_index.get(tag, [])
        return [(aid, self._agents[aid], self._metadata[aid]) for aid in agent_ids if aid in self._agents]

    def find_by_capability(self, capability: str) -> list[tuple[str, Any, AgentMetadata]]:
        results = []
        for agent_id, metadata in self._metadata.items():
            if capability in metadata.capabilities:
                results.append((agent_id, self._agents[agent_id], metadata))
        return results

    def find_by_language(self, language: str) -> list[tuple[str, Any, AgentMetadata]]:
        results = []
        for agent_id, metadata in self._metadata.items():
            if language in metadata.languages:
                results.append((agent_id, self._agents[agent_id], metadata))
        return results

    def search(self, query: str) -> list[tuple[str, Any, AgentMetadata]]:
        query_lower = query.lower()
        results = []
        for agent_id, agent in self._agents.items():
            metadata = self._metadata[agent_id]
            if (
                query_lower in metadata.name.lower()
                or query_lower in metadata.description.lower()
                or query_lower in metadata.role.lower()
                or any(query_lower in cap.lower() for cap in metadata.capabilities)
                or any(query_lower in tag.lower() for tag in metadata.tags)
            ):
                results.append((agent_id, agent, metadata))
        results.sort(key=lambda x: x[2].name)
        return results

    def list_all(self) -> list[tuple[str, Any, AgentMetadata]]:
        return [(aid, agent, self._metadata[aid]) for aid, agent in self._agents.items()]

    def get_statistics(self) -> dict[str, Any]:
        total = len(self._agents)
        roles: dict[str, int] = {}
        tags: dict[str, int] = {}
        capabilities: dict[str, int] = {}
        for metadata in self._metadata.values():
            roles[metadata.role] = roles.get(metadata.role, 0) + 1
            for tag in metadata.tags:
                tags[tag] = tags.get(tag, 0) + 1
            for cap in metadata.capabilities:
                capabilities[cap] = capabilities.get(cap, 0) + 1
        return {
            "total_agents": total,
            "by_role": roles,
            "top_tags": sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10],
            "top_capabilities": sorted(capabilities.items(), key=lambda x: x[1], reverse=True)[:10],
        }
