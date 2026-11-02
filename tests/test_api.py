"""API tests: auth flow, bookings CRUD, static pages. No network access."""

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


def login(client: TestClient) -> None:
    response = client.post(
        "/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text


def create_booking(client: TestClient, name: str = "Anna") -> dict[str, Any]:
    response = client.post(
        "/api/bookings",
        json={
            "name": name,
            "contact": "anna@example.com",
            "contact_method": "telegram",
            "program": "individual",
            "preferred_date": "2026-11-20",
            "preferred_time": "evening",
            "comment": "",
        },
    )
    assert response.status_code == 200
    return response.json()


# ---------- static pages ----------


def test_index_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "IriSkating" in response.text


def test_admin_page_served(client: TestClient) -> None:
    response = client.get("/admin")
    assert response.status_code == 200
    assert "admin" in response.text.lower()


def test_static_css_served(client: TestClient) -> None:
    response = client.get("/css/styles.css")
    assert response.status_code == 200


# ---------- auth ----------


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/login", json={"username": ADMIN_USER, "password": "nope"}
    )
    assert response.status_code == 401


def test_login_sets_session_and_me(client: TestClient) -> None:
    login(client)
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json() == {"username": ADMIN_USER}


def test_logout_clears_session(client: TestClient) -> None:
    login(client)
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_bookings_require_auth(client: TestClient) -> None:
    assert client.get("/api/bookings").status_code == 401
    assert client.patch("/api/bookings/1", json={"status": "confirmed"}).status_code == 401


# ---------- bookings ----------


def test_booking_lifecycle(client: TestClient) -> None:
    created = create_booking(client, name="Test User")
    assert created["ok"] is True
    booking_id = created["id"]

    # public cannot list, admin can
    assert client.get("/api/bookings").status_code == 401
    login(client)
    bookings = client.get("/api/bookings").json()
    assert any(b["id"] == booking_id and b["name"] == "Test User" for b in bookings)

    # status update
    response = client.patch(f"/api/bookings/{booking_id}", json={"status": "confirmed"})
    assert response.status_code == 200
    bookings = client.get("/api/bookings").json()
    statuses = {b["id"]: b["status"] for b in bookings}
    assert statuses[booking_id] == "confirmed"

    # unknown id -> 404
    assert client.patch("/api/bookings/999999", json={"status": "cancelled"}).status_code == 404


def test_booking_validation(client: TestClient) -> None:
    response = client.post(
        "/api/bookings",
        json={
            "name": "X",
            "contact": "a@b.c",
            "program": "unknown-program",
            "preferred_date": "2026-11-20",
            "preferred_time": "evening",
        },
    )
    assert response.status_code == 422

    response = client.post(
        "/api/bookings",
        json={
            "name": "X",
            "contact": "a@b.c",
            "contact_method": "sms",
            "program": "individual",
            "preferred_date": "2026-11-20",
            "preferred_time": "evening",
        },
    )
    assert response.status_code == 422

    response = client.post(
        "/api/bookings",
        json={
            "name": "X",
            "contact": "a@b.c",
            "program": "individual",
            "preferred_date": "not-a-date",
            "preferred_time": "evening",
        },
    )
    assert response.status_code == 422


# ---------- contact_method migration ----------


def test_contact_method_migration(tmp_path: Path, api_env: pytest.MonkeyPatch) -> None:
    """Старая БД без contact_method должна мигрировать при старте приложения."""
    import sqlite3

    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT,"
        " name TEXT NOT NULL, contact TEXT NOT NULL, program TEXT NOT NULL,"
        " preferred_date TEXT NOT NULL, preferred_time TEXT NOT NULL,"
        " comment TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'new')"
    )
    conn.execute(
        "INSERT INTO bookings (created_at, name, contact, program, preferred_date,"
        " preferred_time) VALUES ('2026-01-01', 'Old Client', 'old@x.io', 'individual',"
        " '2026-02-01', 'evening')"
    )
    conn.commit()
    conn.close()

    api_env.setenv("DATABASE_PATH", str(db_path))
    with TestClient(app) as test_client:
        login(test_client)
        bookings = test_client.get("/api/bookings").json()
    assert len(bookings) == 1
    assert bookings[0]["contact_method"] == "telegram"


# ---------- telegram notification ----------


def test_telegram_notification_sent(client: TestClient, monkeypatch) -> None:
    import server.telegram as telegram_module

    calls: list[tuple[str, str, str]] = []

    async def fake_send_message(token: str, chat_id: str, text: str) -> bool:
        calls.append((token, chat_id, text))
        return True

    monkeypatch.setattr(telegram_module, "send_message", fake_send_message)
    created = create_booking(client, name="Notify Me")
    assert created["ok"] is True
    # уведомление уходит обоим получателям из TELEGRAM_ADMIN_CHAT_IDS
    assert [c for _, c, _ in calls] == ["42", "777"]
    assert all(text == calls[0][2] for _, _, text in calls)
    assert "Notify Me" in calls[0][2]


def test_telegram_disabled_keeps_booking(
    client: TestClient, api_env: pytest.MonkeyPatch
) -> None:
    import server.telegram as telegram_module

    async def fail_send_message(token: str, chat_id: str, text: str) -> bool:
        raise AssertionError("не должно вызываться без TELEGRAM_* в окружении")

    api_env.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    api_env.delenv("TELEGRAM_ADMIN_CHAT_IDS", raising=False)
    monkeypatch = api_env
    monkeypatch.setattr(telegram_module, "send_message", fail_send_message)

    created = create_booking(client, name="No Notify")
    assert created["ok"] is True
    login(client)
    bookings = client.get("/api/bookings").json()
    assert any(b["name"] == "No Notify" for b in bookings)
