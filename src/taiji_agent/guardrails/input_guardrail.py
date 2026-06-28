"""
Input Guardrails - 输入安全验证
"""

from __future__ import annotations
from typing import Optional

import re

from .core import Guardrail, GuardrailConfig, ValidationResult


class ContentFilter(Guardrail):
    BLOCKED_PATTERNS: set[str] = {
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<\s*iframe",
        r"<\s*object",
        r"<\s*embed",
    }

    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        custom_patterns: Optional[list[str]] = None,
    ):
        super().__init__(config)
        self.patterns = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.BLOCKED_PATTERNS]
        if custom_patterns:
            self.patterns.extend(re.compile(p, re.IGNORECASE) for p in custom_patterns)

    async def validate(self, text: str) -> ValidationResult:
        flagged = []
        for pattern in self.patterns:
            matches = pattern.findall(text)
            if matches:
                flagged.extend(matches)
        if flagged:
            return ValidationResult.fail_result(
                message="Potentially harmful content detected",
                details={"flagged_count": len(flagged), "type": "content_filter"},
            )
        return ValidationResult.pass_result()


class ProfanityFilter(Guardrail):
    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        custom_words: Optional[list[str]] = None,
    ):
        super().__init__(config)
        self.blocked_words = set(custom_words or [])

    async def validate(self, text: str) -> ValidationResult:
        text_lower = text.lower()
        found = [w for w in self.blocked_words if w.lower() in text_lower]
        if found:
            return ValidationResult.fail_result(
                message="Blocked words detected",
                details={"words": found},
            )
        return ValidationResult.pass_result()


class RateLimitGuardrail(Guardrail):
    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        max_requests_per_minute: int = 60,
        max_tokens_per_minute: int = 100000,
    ):
        super().__init__(config)
        self.max_rpm = max_requests_per_minute
        self.max_tpm = max_tokens_per_minute
        self._request_counts: list[float] = []
        self._token_counts: list[float] = []

    async def validate(self, text: str) -> ValidationResult:
        import time

        now = time.time()
        self._request_counts = [t for t in self._request_counts if now - t < 60]
        self._token_counts = [t for t in self._token_counts if now - t < 60]
        if len(self._request_counts) >= self.max_rpm:
            return ValidationResult.fail_result(
                message="Rate limit exceeded",
                details={"limit": self.max_rpm, "window": "60s"},
            )
        self._request_counts.append(now)
        estimated_tokens = len(text.split()) * 1.3
        self._token_counts.append(estimated_tokens)
        if sum(self._token_counts) > self.max_tpm:
            return ValidationResult.fail_result(
                message="Token rate limit exceeded",
                details={"limit": self.max_tpm},
            )
        return ValidationResult.pass_result(details={"requests_in_window": len(self._request_counts)})


class LengthGuardrail(Guardrail):
    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        min_length: int = 0,
        max_length: int = 100000,
    ):
        super().__init__(config)
        self.min_length = min_length
        self.max_length = max_length

    async def validate(self, text: str) -> ValidationResult:
        length = len(text)
        if length < self.min_length:
            return ValidationResult.fail_result(
                message=f"Input too short: {length} < {self.min_length}",
                details={"length": length, "min": self.min_length},
            )
        if length > self.max_length:
            return ValidationResult.fail_result(
                message=f"Input too long: {length} > {self.max_length}",
                details={"length": length, "max": self.max_length},
            )
        return ValidationResult.pass_result(details={"length": length})


class InputGuardrail:
    @staticmethod
    def default(config: Optional[GuardrailConfig] = None) -> list[Guardrail]:
        return [
            ContentFilter(config),
            LengthGuardrail(config, max_length=50000),
            RateLimitGuardrail(config),
        ]

    @staticmethod
    def strict(config: Optional[GuardrailConfig] = None) -> list[Guardrail]:
        return [
            ContentFilter(config, custom_patterns=[r"\b(SQL|RCE|Injection)\b"]),
            LengthGuardrail(config, max_length=10000),
            RateLimitGuardrail(config, max_requests_per_minute=30),
        ]
