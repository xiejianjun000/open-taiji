"""
Approval Queue - 审批队列系统
参考Dify v1.13.0 Human Input节点设计
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    SKIP = "skip"


@dataclass
class ApprovalConfig:
    timeout_seconds: int = 3600
    auto_reject_on_timeout: bool = False
    escalation_email: Optional[str] = None
    require_reason: bool = True
    allow_modification: bool = True
    max_retries: int = 3


@dataclass
class ApprovalRequest:
    request_id: str
    agent_name: str
    action_type: str
    action_description: str
    justification: str
    risk_level: str
    parameters: dict[str, Any]
    requested_at: datetime
    timeout_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    responded_at: Optional[datetime] = None
    responded_by: Optional[str] = None
    decision: Optional[ApprovalDecision] = None
    decision_notes: Optional[str] = None
    modified_parameters: Optional[dict[str, Any]] = None
    retry_count: int = 0
    agent_state: Optional[dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        agent_name: str,
        action_type: str,
        action_description: str,
        justification: str,
        risk_level: str = "medium",
        parameters: Optional[dict[str, Any]] = None,
        config: Optional[ApprovalConfig] = None,
        agent_state: Optional[dict[str, Any]] = None,
    ) -> ApprovalRequest:
        cfg = config or ApprovalConfig()
        now = datetime.now()
        return cls(
            request_id=str(uuid.uuid4()),
            agent_name=agent_name,
            action_type=action_type,
            action_description=action_description,
            justification=justification,
            risk_level=risk_level,
            parameters=parameters or {},
            requested_at=now,
            timeout_at=now + timedelta(seconds=cfg.timeout_seconds),
            agent_state=agent_state,
        )


class ApprovalQueue:
    def __init__(self, config: Optional[ApprovalConfig] = None):
        self.config = config or ApprovalConfig()
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []
        self._waiting: dict[str, asyncio.Event] = {}
        self._listeners: list[Callable] = []

    def add_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify_listeners(self, request: ApprovalRequest) -> None:
        for listener in self._listeners:
            try:
                listener(request)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    async def request_approval(
        self,
        agent_name: str,
        action_type: str,
        action_description: str,
        justification: str,
        risk_level: str = "medium",
        parameters: Optional[dict[str, Any]] = None,
        agent_state: Optional[dict[str, Any]] = None,
    ) -> str:
        request = ApprovalRequest.create(
            agent_name=agent_name,
            action_type=action_type,
            action_description=action_description,
            justification=justification,
            risk_level=risk_level,
            parameters=parameters,
            config=self.config,
            agent_state=agent_state,
        )
        self._pending[request.request_id] = request
        self._waiting[request.request_id] = asyncio.Event()
        self._notify_listeners(request)
        logger.info(f"Approval requested: {request.request_id} - {action_type}")
        return request.request_id

    async def wait_for_decision(
        self,
        request_id: str,
        timeout: Optional[int] = None,
    ) -> ApprovalRequest:
        if request_id not in self._pending:
            raise ValueError(f"Request not found: {request_id}")
        request = self._pending[request_id]
        timeout_seconds = timeout or self.config.timeout_seconds
        try:
            await asyncio.wait_for(
                self._waiting[request_id].wait(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            if self.config.auto_reject_on_timeout:
                await self.reject(
                    request_id,
                    "TIMEOUT",
                    f"Auto-rejected due to timeout ({timeout_seconds}s)",
                )
            else:
                request.status = ApprovalStatus.TIMEOUT
        return self._pending[request_id]

    async def approve(
        self,
        request_id: str,
        user_id: str,
        notes: Optional[str] = None,
    ) -> ApprovalRequest:
        if request_id not in self._pending:
            raise ValueError(f"Request not found: {request_id}")
        request = self._pending[request_id]
        request.status = ApprovalStatus.APPROVED
        request.decision = ApprovalDecision.APPROVE
        request.responded_at = datetime.now()
        request.responded_by = user_id
        request.decision_notes = notes
        self._waiting[request_id].set()
        self._history.append(request)
        del self._pending[request_id]
        logger.info(f"Approval granted: {request_id}")
        return request

    async def reject(
        self,
        request_id: str,
        user_id: str,
        notes: Optional[str] = None,
    ) -> ApprovalRequest:
        if request_id not in self._pending:
            raise ValueError(f"Request not found: {request_id}")
        request = self._pending[request_id]
        request.status = ApprovalStatus.REJECTED
        request.decision = ApprovalDecision.REJECT
        request.responded_at = datetime.now()
        request.responded_by = user_id
        request.decision_notes = notes
        self._waiting[request_id].set()
        self._history.append(request)
        del self._pending[request_id]
        logger.info(f"Approval rejected: {request_id}")
        return request

    async def modify_and_approve(
        self,
        request_id: str,
        user_id: str,
        modified_parameters: dict[str, Any],
        notes: Optional[str] = None,
    ) -> ApprovalRequest:
        if not self.config.allow_modification:
            raise ValueError("Modification not allowed")
        if request_id not in self._pending:
            raise ValueError(f"Request not found: {request_id}")
        request = self._pending[request_id]
        request.status = ApprovalStatus.APPROVED
        request.decision = ApprovalDecision.MODIFY
        request.responded_at = datetime.now()
        request.responded_by = user_id
        request.modified_parameters = modified_parameters
        request.decision_notes = notes
        self._waiting[request_id].set()
        self._history.append(request)
        del self._pending[request_id]
        logger.info(f"Approval modified and granted: {request_id}")
        return request

    def get_pending(self) -> list[ApprovalRequest]:
        return list(self._pending.values())

    def get_pending_by_risk(self, risk_level: str) -> list[ApprovalRequest]:
        return [r for r in self._pending.values() if r.risk_level == risk_level]

    def get_history(self, limit: int = 100) -> list[ApprovalRequest]:
        return self._history[-limit:]

    def cancel(self, request_id: str) -> ApprovalRequest:
        if request_id not in self._pending:
            raise ValueError(f"Request not found: {request_id}")
        request = self._pending[request_id]
        request.status = ApprovalStatus.CANCELLED
        request.responded_at = datetime.now()
        self._waiting[request_id].set()
        self._history.append(request)
        del self._pending[request_id]
        return request
