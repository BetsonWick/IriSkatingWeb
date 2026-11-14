"""Shared fixtures: admin env + TestClient. No network access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.auth import hash_password

ADMIN_USER = "iren"
ADMIN_PASSWORD = "correct-horse"


@pytest.fixture()
def api_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Окружение API: админ-креды, SQLite в tmp, тестовые TELEGRAM_*."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_USER)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(ADMIN_PASSWORD))
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_IDS", "42,777")
    return monkeypatch


@pytest.fixture()
def client(api_env: pytest.MonkeyPatch) -> Any:
    with TestClient(app) as test_client:
        yield test_client
