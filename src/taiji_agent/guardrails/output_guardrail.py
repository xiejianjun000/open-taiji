"""
Output Guardrails - 输出质量与安全验证
"""

from __future__ import annotations
from typing import Optional

import re

from .core import Guardrail, GuardrailConfig, ValidationResult


class SensitiveDataFilter(Guardrail):
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")
    API_KEY_PATTERN = re.compile(
        r'\b(?:api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}["\']?', re.IGNORECASE
    )

    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        filter_emails: bool = True,
        filter_phones: bool = True,
        filter_ssn: bool = True,
        filter_credit_cards: bool = True,
        filter_api_keys: bool = True,
    ):
        super().__init__(config)
        self.filter_config = {
            "email": filter_emails,
            "phone": filter_phones,
            "ssn": filter_ssn,
            "credit_card": filter_credit_cards,
            "api_key": filter_api_keys,
        }
        self.patterns = {
            "email": self.EMAIL_PATTERN,
            "phone": self.PHONE_PATTERN,
            "ssn": self.SSN_PATTERN,
            "credit_card": self.CREDIT_CARD_PATTERN,
            "api_key": self.API_KEY_PATTERN,
        }

    async def validate(self, text: str) -> ValidationResult:
        flagged_types = {}
        for data_type, enabled in self.filter_config.items():
            if enabled:
                pattern = self.patterns[data_type]
                matches = pattern.findall(text)
                if matches:
                    flagged_types[data_type] = len(matches)
        if flagged_types:
            return ValidationResult.warn_result(
                message="Potential sensitive data detected",
                details={"types": flagged_types, "action": "review"},
            )
        return ValidationResult.pass_result()

    def mask_sensitive_data(self, text: str) -> str:
        result = text
        if self.filter_config.get("email"):
            result = self.EMAIL_PATTERN.sub("[EMAIL_MASKED]", result)
        if self.filter_config.get("phone"):
            result = self.PHONE_PATTERN.sub("[PHONE_MASKED]", result)
        if self.filter_config.get("ssn"):
            result = self.SSN_PATTERN.sub("[SSN_MASKED]", result)
        if self.filter_config.get("credit_card"):
            result = self.CREDIT_CARD_PATTERN.sub("[CARD_MASKED]", result)
        if self.filter_config.get("api_key"):
            result = self.API_KEY_PATTERN.sub("[API_KEY_MASKED]", result)
        return result


class QualityGate(Guardrail):
    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        min_length: int = 10,
        max_repeated_chars: int = 5,
        require_capitalized: bool = False,
    ):
        super().__init__(config)
        self.min_length = min_length
        self.max_repeated = max_repeated_chars
        self.require_capitalized = require_capitalized

    async def validate(self, text: str) -> ValidationResult:
        issues = []
        if len(text) < self.min_length:
            issues.append(f"Output too short: {len(text)} < {self.min_length}")
        repeated = re.compile(r"(.)\1{" + str(self.max_repeated) + r",}")
        if repeated.search(text):
            issues.append("Excessive repeated characters detected")
        if self.require_capitalized and not any(c.isupper() for c in text):
            issues.append("No capitalized letters found")
        empty_patterns = [
            r"\n\s*\n\s*\n",
            r" {5,}",
        ]
        for pattern in empty_patterns:
            if re.search(pattern, text):
                issues.append("Excessive whitespace detected")
                break
        if issues:
            return ValidationResult.warn_result(
                message="Quality gate warnings",
                details={"issues": issues},
            )
        return ValidationResult.pass_result(details={"length": len(text)})


class HallucinationGate(Guardrail):
    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        confidence_threshold: float = 0.7,
    ):
        super().__init__(config)
        self.confidence_threshold = confidence_threshold

    async def validate(self, text: str) -> ValidationResult:
        uncertainty_phrases = [
            r"i'm not sure",
            r"i cannot verify",
            r"may be inaccurate",
            r"cannot confirm",
            r"possibly",
            r"might be",
            r"unverified",
            r"as of my knowledge",
            r"i don't have access",
        ]
        uncertainty_count = 0
        for phrase in uncertainty_phrases:
            uncertainty_count += len(re.findall(phrase, text, re.IGNORECASE))
        if uncertainty_count > 3:
            return ValidationResult.warn_result(
                message="High uncertainty detected",
                details={"uncertainty_count": uncertainty_count},
            )
        return ValidationResult.pass_result()


class OutputGuardrail:
    @staticmethod
    def default(config: Optional[GuardrailConfig] = None) -> list[Guardrail]:
        return [
            SensitiveDataFilter(config),
            QualityGate(config),
            HallucinationGate(config),
        ]

    @staticmethod
    def strict(config: Optional[GuardrailConfig] = None) -> list[Guardrail]:
        return [
            SensitiveDataFilter(config),
            QualityGate(config, require_capitalized=True),
            HallucinationGate(config, confidence_threshold=0.8),
        ]
