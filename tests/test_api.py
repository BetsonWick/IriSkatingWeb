"""API tests: auth flow, bookings CRUD, static pages. No network access."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.auth import hash_password

ADMIN_USER = "iren"
ADMIN_PASSWORD = "correct-horse"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_USER)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(ADMIN_PASSWORD))
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient) -> None:
    response = client.post(
        "/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200


def create_booking(client: TestClient, name: str = "Anna") -> dict[str, Any]:
    response = client.post(
        "/api/bookings",
        json={
            "name": name,
            "contact": "anna@example.com",
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
            "program": "individual",
            "preferred_date": "not-a-date",
            "preferred_time": "evening",
        },
    )
    assert response.status_code == 422
