"""Unit tests for services."""

from __future__ import annotations

from app.services.redaction_service import redact_dict, redact_string


class TestRedactionService:
    def test_redact_bearer_token(self) -> None:
        text = "Authorization: Bearer sk-1234567890abcdef"
        result = redact_string(text)
        assert "sk-1234567890abcdef" not in result
        assert "REDACTED" in result

    def test_redact_api_key(self) -> None:
        text = "api_key=secret123456"
        result = redact_string(text)
        assert "secret123456" not in result
        assert "REDACTED" in result

    def test_redact_password(self) -> None:
        text = "password: mysecretpassword"
        result = redact_string(text)
        assert "mysecretpassword" not in result
        assert "REDACTED" in result

    def test_redact_postgresql_url(self) -> None:
        text = "postgresql://user:pass@host:5432/db"
        result = redact_string(text)
        assert "pass@host" not in result
        assert "REDACTED" in result

    def test_redact_redis_url(self) -> None:
        text = "redis://localhost:6379/0"
        result = redact_string(text)
        assert "REDACTED" in result

    def test_redact_dict(self) -> None:
        data = {
            "api_key": "secret123",
            "normal_field": "visible",
            "nested": {"password": "hidden"},
        }
        result = redact_dict(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["normal_field"] == "visible"
        assert result["nested"]["password"] == "[REDACTED]"

    def test_redact_preserves_structure(self) -> None:
        data = {"key": "value", "number": 42}
        result = redact_dict(data)
        assert result["number"] == 42
