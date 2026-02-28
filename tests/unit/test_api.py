"""Tests for the FastAPI routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_sites() -> None:
    resp = client.get("/api/sites")
    assert resp.status_code == 200
    data = resp.json()
    assert "sites" in data
    assert "nykaa" in data["sites"]
    assert "amazon" in data["sites"]
    assert len(data["sites"]) == 9
