import re

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{82}"),
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"ANTHROPIC_API_KEY[=:]\s*[A-Za-z0-9_\-]+"),
    re.compile(r"(?:password|secret|token|api[_-]?key)[=:]\s*\S+", re.IGNORECASE),
]

REDACTED = "[REDACTED]"


def redact_text(text: str) -> str:
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def redact_dict(data: dict) -> dict:
    redacted = {}
    for key, value in data.items():
        if isinstance(value, str):
            redacted[key] = redact_text(value)
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_text(str(v)) if isinstance(v, str) else v for v in value
            ]
        else:
            redacted[key] = value
    return redacted


def scan_for_secrets(content: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        matches = pattern.findall(content)
        for match in matches:
            findings.append(f"Found pattern: {match[:10]}...")
    return findings
