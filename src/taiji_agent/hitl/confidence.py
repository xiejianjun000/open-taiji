"""
Confidence Gate - 置信度门控
智能判断是否需要人工审批
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ConfidenceResult:
    confidence: float
    level: ConfidenceLevel
    should_auto_approve: bool
    reason: str
    metadata: dict[str, Any]


class ConfidenceGate:
    def __init__(
        self,
        high_threshold: float = 0.85,
        medium_threshold: float = 0.70,
        auto_approve_high: bool = True,
        auto_approve_medium: bool = False,
    ):
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.auto_approve_high = auto_approve_high
        self.auto_approve_medium = auto_approve_medium

    def evaluate(
        self,
        action_type: str,
        action_description: str,
        risk_level: str,
        parameters: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> ConfidenceResult:
        confidence = self._calculate_confidence(action_type, action_description, risk_level, parameters, context)
        level = self._get_level(confidence)
        should_auto = self._should_auto_approve(level, risk_level)
        reason = self._get_reason(confidence, level, risk_level)
        return ConfidenceResult(
            confidence=confidence,
            level=level,
            should_auto_approve=should_auto,
            reason=reason,
            metadata={
                "thresholds": {
                    "high": self.high_threshold,
                    "medium": self.medium_threshold,
                },
                "risk_level": risk_level,
                "action_type": action_type,
            },
        )

    def _calculate_confidence(
        self,
        action_type: str,
        action_description: str,
        risk_level: str,
        parameters: dict[str, Any],
        context: Optional[dict[str, Any]],
    ) -> float:
        base_confidence = 0.8
        if risk_level == "low":
            base_confidence += 0.1
        elif risk_level == "high":
            base_confidence -= 0.2
        if context:
            historical_success = context.get("historical_success_rate", 0.5)
            base_confidence *= 0.5 + historical_success
            user_trust_score = context.get("user_trust_score", 0.5)
            base_confidence *= 0.5 + user_trust_score
        safe_action_types = {"query", "search", "read", "get", "list", "view"}
        if action_type.lower() in safe_action_types:
            base_confidence += 0.05
        destructive_keywords = {"delete", "remove", "destroy", "drop", "truncate"}
        if any(kw in action_type.lower() for kw in destructive_keywords):
            base_confidence -= 0.3
        parameter_count = len(parameters)
        if parameter_count > 10:
            base_confidence -= 0.1
        return max(0.0, min(1.0, base_confidence))

    def _get_level(self, confidence: float) -> ConfidenceLevel:
        if confidence >= self.high_threshold:
            return ConfidenceLevel.HIGH
        elif confidence >= self.medium_threshold:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _should_auto_approve(self, level: ConfidenceLevel, risk_level: str) -> bool:
        if risk_level == "critical":
            return False
        if level == ConfidenceLevel.HIGH and self.auto_approve_high:
            return True
        if level == ConfidenceLevel.MEDIUM and self.auto_approve_medium:
            return True
        return False

    def _get_reason(self, confidence: float, level: ConfidenceLevel, risk_level: str) -> str:
        reasons = []
        reasons.append(f"Confidence: {confidence:.2%}")
        reasons.append(f"Level: {level.value}")
        if risk_level != "medium":
            reasons.append(f"Risk: {risk_level}")
        if confidence >= self.high_threshold:
            reasons.append("Above auto-approve threshold")
        elif confidence >= self.medium_threshold:
            reasons.append("Near auto-approve threshold")
        else:
            reasons.append("Below threshold, manual review recommended")
        return "; ".join(reasons)

    async def should_request_approval(
        self,
        action_type: str,
        action_description: str,
        risk_level: str,
        parameters: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[bool, ConfidenceResult]:
        result = self.evaluate(action_type, action_description, risk_level, parameters, context)
        should_request = not result.should_auto_approve
        return should_request, result
