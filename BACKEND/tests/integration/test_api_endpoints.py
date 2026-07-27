"""Integration tests for API endpoints - smoke tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_readyz(client: TestClient) -> None:
    assert client.get("/readyz").status_code == 200
