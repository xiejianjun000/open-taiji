"""
Guardrails Core - 护栏核心定义
参考OpenAI Agents SDK Guardrails设计
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class ValidationResult:
    is_valid: bool
    level: ValidationLevel
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    flagged_content: Optional[list[str]] = None

    @classmethod
    def pass_result(cls, message: str = "Validation passed", details: Optional[dict] = None) -> ValidationResult:
        return cls(is_valid=True, level=ValidationLevel.PASS, message=message, details=details or {})

    @classmethod
    def fail_result(cls, message: str, details: Optional[dict] = None) -> ValidationResult:
        return cls(is_valid=False, level=ValidationLevel.FAIL, message=message, details=details or {})

    @classmethod
    def warn_result(cls, message: str, details: Optional[dict] = None) -> ValidationResult:
        return cls(is_valid=True, level=ValidationLevel.WARN, message=message, details=details or {})


@dataclass
class GuardrailConfig:
    enabled: bool = True
    strict_mode: bool = False
    fail_fast: bool = True
    custom_rules: dict[str, Any] = field(default_factory=dict)


class Guardrail(ABC):
    def __init__(self, config: Optional[GuardrailConfig] = None):
        self.config = config or GuardrailConfig()
        self.name = self.__class__.__name__

    @abstractmethod
    async def validate(self, text: str) -> ValidationResult:
        pass

    async def __call__(self, text: str) -> ValidationResult:
        if not self.config.enabled:
            return ValidationResult.pass_result(f"{self.name} is disabled")
        return await self.validate(text)


class CompositeGuardrail(Guardrail):
    def __init__(
        self,
        guardrails: list[Guardrail],
        config: Optional[GuardrailConfig] = None,
        mode: str = "all",
    ):
        super().__init__(config)
        self.guardrails = guardrails
        self.mode = mode

    async def validate(self, text: str) -> ValidationResult:
        results: list[ValidationResult] = []
        for guardrail in self.guardrails:
            result = await guardrail(text)
            results.append(result)
            if self.config.fail_fast and not result.is_valid:
                if self.mode == "all":
                    return result
                elif self.mode == "any" and result.level == ValidationLevel.FAIL:
                    return result
        if self.mode == "all":
            failures = [r for r in results if not r.is_valid]
            if failures:
                return failures[0]
        warnings = [r for r in results if r.level == ValidationLevel.WARN]
        if warnings:
            return warnings[0]
        return ValidationResult.pass_result("All guardrails passed")


class GuardrailManager:
    def __init__(self):
        self.input_guardrails: list[Guardrail] = []
        self.output_guardrails: list[Guardrail] = []
        self.tool_guardrails: list[Guardrail] = []
        self._results_history: list[dict[str, Any]] = []

    def add_input_guardrail(self, guardrail: Guardrail) -> None:
        self.input_guardrails.append(guardrail)

    def add_output_guardrail(self, guardrail: Guardrail) -> None:
        self.output_guardrails.append(guardrail)

    def add_tool_guardrail(self, guardrail: Guardrail) -> None:
        self.tool_guardrails.append(guardrail)

    async def validate_input(self, text: str) -> ValidationResult:
        if not self.input_guardrails:
            return ValidationResult.pass_result("No input guardrails configured")
        composite = CompositeGuardrail(self.input_guardrails)
        result = await composite(text)
        self._log_result("input", text, result)
        return result

    async def validate_output(self, text: str) -> ValidationResult:
        if not self.output_guardrails:
            return ValidationResult.pass_result("No output guardrails configured")
        composite = CompositeGuardrail(self.output_guardrails)
        result = await composite(text)
        self._log_result("output", text, result)
        return result

    async def validate_tool_input(self, tool_name: str, arguments: dict[str, Any]) -> ValidationResult:
        if not self.tool_guardrails:
            return ValidationResult.pass_result("No tool guardrails configured")
        composite = CompositeGuardrail(self.tool_guardrails)
        text = f"Tool: {tool_name}\nArgs: {arguments}"
        result = await composite(text)
        self._log_result("tool", text, result)
        return result

    def _log_result(self, guardrail_type: str, text: str, result: ValidationResult) -> None:
        entry = {
            "type": guardrail_type,
            "guardrail": result.message,
            "is_valid": result.is_valid,
            "level": result.level.value,
            "details": result.details,
        }
        self._results_history.append(entry)
        if not result.is_valid:
            logger.warning(f"Guardrail failed: {result.message}")

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._results_history[-limit:]

    def clear_history(self) -> None:
        self._results_history.clear()
