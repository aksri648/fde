"""Redaction service for sensitive data in logs, events, and planner context."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)api[_-]?key\s*[=:]\s*\S+"),
    re.compile(r"(?i)authorization\s*[=:]\s*\S+"),
    re.compile(r"(?i)password\s*[=:]\s*\S+"),
    re.compile(r"(?i)secret\s*[=:]\s*\S+"),
    re.compile(r"(?i)token\s*[=:]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"postgresql://\S+"),
    re.compile(r"redis://\S+"),
]

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"(?i)api[_-]?key"),
    re.compile(r"(?i)password"),
    re.compile(r"(?i)secret"),
    re.compile(r"(?i)token"),
    re.compile(r"(?i)credential"),
    re.compile(r"(?i)auth"),
]

REDACTED = "[REDACTED]"


def redact_string(text: str) -> str:
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        is_sensitive_key = any(p.search(key) for p in SENSITIVE_KEY_PATTERNS)

        if is_sensitive_key:
            redacted[key] = REDACTED
        elif isinstance(value, str):
            redacted[key] = redact_string(value)
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_dict(item)
                if isinstance(item, dict)
                else redact_string(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def redact_for_planner(text: str) -> str:
    return redact_string(text)
