"""
Handoffs Core - 智能体交接核心
参考OpenAI Agents SDK Handoffs设计
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class HandoffDecision(StrEnum):
    STAY = "stay"
    TRANSFER = "transfer"
    COLLABORATE = "collaborate"


@dataclass
class HandoffConfig:
    transfer_threshold: float = 0.7
    auto_transfer: bool = True
    preserve_context: bool = True
    include_agent_state: bool = True
    max_handoffs_per_session: int = 10


@dataclass
class HandoffResult:
    source_agent: str
    target_agent: str
    decision: HandoffDecision
    transferred_at: datetime
    context_summary: str
    success: bool
    error: Optional[str] = None


@dataclass
class HandoffContext:
    user_intent: str
    current_task: str
    completed_steps: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    relevant_history: list[dict[str, Any]] = field(default_factory=list)
    session_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class Handoff(ABC):
    def __init__(
        self,
        name: str,
        description: str,
        agent: Any,
        config: Optional[HandoffConfig] = None,
    ):
        self.name = name
        self.description = description
        self.agent = agent
        self.config = config or HandoffConfig()
        self._handoff_count = 0

    @abstractmethod
    async def should_handoff(
        self,
        context: HandoffContext,
    ) -> tuple[bool, float]:
        pass

    @abstractmethod
    async def prepare_handoff(
        self,
        context: HandoffContext,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def on_handoff_received(
        self,
        context: HandoffContext,
    ) -> str:
        pass

    def can_accept_handoff(self) -> bool:
        return self._handoff_count < self.config.max_handoffs_per_session

    def increment_handoff_count(self) -> None:
        self._handoff_count += 1


class HandoffManager:
    def __init__(self, config: Optional[HandoffConfig] = None):
        self.config = config or HandoffConfig()
        self._handoffs: dict[str, Handoff] = {}
        self._handoff_history: list[HandoffResult] = []
        self._current_agent: Optional[str] = None

    def register(self, handoff: Handoff) -> None:
        self._handoffs[handoff.name] = handoff
        logger.info(f"Handoff registered: {handoff.name}")

    def unregister(self, name: str) -> None:
        if name in self._handoffs:
            del self._handoffs[name]
            logger.info(f"Handoff unregistered: {name}")

    def get(self, name: str) -> Optional[Handoff]:
        return self._handoffs.get(name)

    def list_handoffs(self) -> list[Handoff]:
        return list(self._handoffs.values())

    async def evaluate_handoffs(
        self,
        context: HandoffContext,
        current_agent: str,
    ) -> list[tuple[Handoff, float, bool]]:
        candidates = []
        for name, handoff in self._handoffs.items():
            if name == current_agent:
                continue
            if not handoff.can_accept_handoff():
                continue
            should, confidence = await handoff.should_handoff(context)
            candidates.append((handoff, confidence, should))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [(h, c, s) for h, c, s in candidates if s]

    async def transfer(
        self,
        from_agent: str,
        to_agent: str,
        context: HandoffContext,
    ) -> HandoffResult:
        source = self._handoffs.get(from_agent)
        target = self._handoffs.get(to_agent)
        if not source or not target:
            error = "Handoff failed: agent not found"
            logger.error(error)
            return HandoffResult(
                source_agent=from_agent,
                target_agent=to_agent,
                decision=HandoffDecision.STAY,
                transferred_at=datetime.now(),
                context_summary="",
                success=False,
                error=error,
            )
        try:
            transfer_data = await source.prepare_handoff(context)
            target.increment_handoff_count()
            await target.on_handoff_received(context)
            result = HandoffResult(
                source_agent=from_agent,
                target_agent=to_agent,
                decision=HandoffDecision.TRANSFER,
                transferred_at=datetime.now(),
                context_summary=transfer_data.get("summary", ""),
                success=True,
            )
            self._handoff_history.append(result)
            self._current_agent = to_agent
            logger.info(f"Handoff completed: {from_agent} -> {to_agent}")
            return result
        except Exception as e:
            error = f"Handoff error: {str(e)}"
            logger.error(error)
            return HandoffResult(
                source_agent=from_agent,
                target_agent=to_agent,
                decision=HandoffDecision.TRANSFER,
                transferred_at=datetime.now(),
                context_summary="",
                success=False,
                error=error,
            )

    def get_history(self, limit: int = 100) -> list[HandoffResult]:
        return self._handoff_history[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        total = len(self._handoff_history)
        successful = sum(1 for r in self._handoff_history if r.success)
        by_agent: dict[str, int] = {}
        for result in self._handoff_history:
            by_agent[result.target_agent] = by_agent.get(result.target_agent, 0) + 1
        return {
            "total_handoffs": total,
            "successful_handoffs": successful,
            "success_rate": successful / total if total > 0 else 0,
            "handoffs_by_agent": by_agent,
        }
