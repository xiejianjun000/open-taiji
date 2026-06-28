"""
Taiji Agent Guardrails Module
安全护栏系统 - 参考OpenAI Agents SDK设计
"""

from .core import CompositeGuardrail, Guardrail, GuardrailConfig, GuardrailManager, ValidationResult
from .input_guardrail import ContentFilter, InputGuardrail, LengthGuardrail, ProfanityFilter, RateLimitGuardrail
from .output_guardrail import HallucinationGate, OutputGuardrail, QualityGate, SensitiveDataFilter

__all__ = [
    "Guardrail",
    "ValidationResult",
    "GuardrailConfig",
    "GuardrailManager",
    "CompositeGuardrail",
    "InputGuardrail",
    "ContentFilter",
    "RateLimitGuardrail",
    "ProfanityFilter",
    "LengthGuardrail",
    "OutputGuardrail",
    "SensitiveDataFilter",
    "QualityGate",
    "HallucinationGate",
]
