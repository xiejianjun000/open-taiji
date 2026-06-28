"""
Checkpoint Manager - 断点恢复系统
支持工作流暂停和恢复
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
class StrEnum(str, Enum):
    pass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CheckpointStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Checkpoint:
    checkpoint_id: str
    workflow_id: str
    step_name: str
    state: dict[str, Any]
    created_at: datetime
    status: CheckpointStatus = CheckpointStatus.ACTIVE
    parent_checkpoint_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "step_name": self.step_name,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "metadata": self.metadata,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            checkpoint_id=data["checkpoint_id"],
            workflow_id=data["workflow_id"],
            step_name=data["step_name"],
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=CheckpointStatus(data.get("status", "active")),
            parent_checkpoint_id=data.get("parent_checkpoint_id"),
            metadata=data.get("metadata", {}),
            version=data.get("version", 1),
        )


class CheckpointManager:
    def __init__(
        self,
        storage_path: Optional[str] = None,
        auto_save: bool = True,
        max_checkpoints: int = 100,
    ):
        self.storage_path = Path(storage_path) if storage_path else Path("./checkpoints")
        self.auto_save = auto_save
        self.max_checkpoints = max_checkpoints
        self._checkpoints: dict[str, Checkpoint] = {}
        self._workflow_checkpoints: dict[str, list[str]] = {}
        if self.auto_save:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        workflow_id: str,
        step_name: str,
        state: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
        parent_checkpoint_id: Optional[str] = None,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            step_name=step_name,
            state=state.copy(),
            created_at=datetime.now(),
            parent_checkpoint_id=parent_checkpoint_id,
            metadata=metadata or {},
        )
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        if workflow_id not in self._workflow_checkpoints:
            self._workflow_checkpoints[workflow_id] = []
        self._workflow_checkpoints[workflow_id].append(checkpoint.checkpoint_id)
        if len(self._workflow_checkpoints[workflow_id]) > self.max_checkpoints:
            oldest = self._workflow_checkpoints[workflow_id].pop(0)
            self._cleanup_checkpoint(oldest)
        if self.auto_save:
            self._save_checkpoint(checkpoint)
        logger.info(f"Checkpoint created: {checkpoint.checkpoint_id} at {step_name}")
        return checkpoint

    def pause(self, checkpoint_id: str) -> Checkpoint:
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        checkpoint = self._checkpoints[checkpoint_id]
        checkpoint.status = CheckpointStatus.PAUSED
        if self.auto_save:
            self._save_checkpoint(checkpoint)
        logger.info(f"Checkpoint paused: {checkpoint_id}")
        return checkpoint

    def resume(self, checkpoint_id: str) -> Checkpoint:
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        checkpoint = self._checkpoints[checkpoint_id]
        checkpoint.status = CheckpointStatus.ACTIVE
        if self.auto_save:
            self._save_checkpoint(checkpoint)
        logger.info(f"Checkpoint resumed: {checkpoint_id}")
        return checkpoint

    def complete(self, checkpoint_id: str) -> Checkpoint:
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        checkpoint = self._checkpoints[checkpoint_id]
        checkpoint.status = CheckpointStatus.COMPLETED
        if self.auto_save:
            self._save_checkpoint(checkpoint)
        logger.info(f"Checkpoint completed: {checkpoint_id}")
        return checkpoint

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._checkpoints.get(checkpoint_id)

    def get_latest(self, workflow_id: str) -> Optional[Checkpoint]:
        if workflow_id not in self._workflow_checkpoints:
            return None
        checkpoint_ids = self._workflow_checkpoints[workflow_id]
        if not checkpoint_ids:
            return None
        return self._checkpoints.get(checkpoint_ids[-1])

    def get_history(self, workflow_id: str) -> list[Checkpoint]:
        if workflow_id not in self._workflow_checkpoints:
            return []
        return [self._checkpoints[cid] for cid in self._workflow_checkpoints[workflow_id] if cid in self._checkpoints]

    def restore(self, checkpoint_id: str) -> dict[str, Any]:
        checkpoint = self.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        logger.info(f"State restored from: {checkpoint_id}")
        return checkpoint.state.copy()

    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        file_path = self.storage_path / f"{checkpoint.workflow_id}_{checkpoint.checkpoint_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)

    def _cleanup_checkpoint(self, checkpoint_id: str) -> None:
        if checkpoint_id in self._checkpoints:
            checkpoint = self._checkpoints[checkpoint_id]
            file_path = self.storage_path / f"{checkpoint.workflow_id}_{checkpoint_id}.json"
            if file_path.exists():
                file_path.unlink()
            del self._checkpoints[checkpoint_id]
            for _workflow_id, ids in self._workflow_checkpoints.items():
                if checkpoint_id in ids:
                    ids.remove(checkpoint_id)

    def load_from_disk(self, workflow_id: str) -> list[Checkpoint]:
        checkpoints = []
        for file_path in self.storage_path.glob(f"{workflow_id}_*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    checkpoint = Checkpoint.from_dict(data)
                    checkpoints.append(checkpoint)
                    self._checkpoints[checkpoint.checkpoint_id] = checkpoint
                    if workflow_id not in self._workflow_checkpoints:
                        self._workflow_checkpoints[workflow_id] = []
                    if checkpoint.checkpoint_id not in self._workflow_checkpoints[workflow_id]:
                        self._workflow_checkpoints[workflow_id].append(checkpoint.checkpoint_id)
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
        return sorted(checkpoints, key=lambda c: c.created_at)
