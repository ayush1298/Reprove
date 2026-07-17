"""Redaction at persistence boundaries. Logs are useful only if they never leak credentials."""

from __future__ import annotations

import re
from typing import Any


PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(token\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
)


def redact(text: str) -> str:
    value = text
    for pattern in PATTERNS:
        value = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", value)
    return value


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    return value
