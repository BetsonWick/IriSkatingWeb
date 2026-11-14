"""Stats API tests: auth, graceful degradation, PromQL response parsing.

No network: PROMETHEUS_URL points at a refused port (conftest), and the
fetch/parse logic is unit-tested through httpx.MockTransport.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi.testclient import TestClient

from server import stats


def mock_prometheus(visits: dict[str, float], bookings: dict[str, float]) -> httpx.MockTransport:
    """Canned /api/v1/query: различает запросы по имени метрики в PromQL."""

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        if "site_visits" in query:
            series = visits
        elif "booking_requests" in query:
            series = bookings
        else:
            series = {}
        result = [
            {"metric": {"country": country}, "value": [0, str(value)]}
            for country, value in series.items()
        ]
        payload = {"status": "success", "data": {"resultType": "vector", "result": result}}
        return httpx.Response(200, content=json.dumps(payload).encode())

    return httpx.MockTransport(handler)


# ---------- auth ----------


def test_stats_requires_auth(client: TestClient) -> None:
    assert client.get("/api/stats").status_code == 401


def test_stats_ok_for_admin(client: TestClient) -> None:
    client.post("/api/login", json={"username": "iren", "password": "correct-horse"})
    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["prometheus_ok"] is False  # Prometheus недоступен в тестах
    assert body["windows"] == []
    assert "generated_at" in body


# ---------- parsing / merging ----------


def test_parse_instant_vector() -> None:
    payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"country": "DE"}, "value": [0, "2"]},
                {"metric": {"country": "XX"}, "value": [0, "1.5"]},
                # NaN / мусор пропускаются
                {"metric": {"country": "US"}, "value": [0, "NaN"]},
                {"metric": {"country": "FR"}, "value": [0, "oops"]},
                {"metric": {}, "value": [0, "3"]},  # нет страны → XX
            ],
        },
    }
    assert stats.parse_instant_vector(payload) == {"DE": 2.0, "XX": 4.5}


def test_fetch_stats_merges_and_sorts() -> None:
    transport = mock_prometheus(
        visits={"DE": 5.0, "XX": 2.0, "US": 1.0},
        bookings={"DE": 1.0, "US": 1.0},
    )
    result = stats.fetch_stats("http://prometheus:9090", transport=transport)
    assert result["prometheus_ok"] is True
    assert len(result["windows"]) == 2
    window = result["windows"][0]
    assert window["key"] == "24h"
    assert window["visits"] == 8.0
    assert window["bookings"] == 2.0
    # сортировка по визитам по убыванию
    assert [c["country"] for c in window["countries"]] == ["DE", "XX", "US"]
    by_country = {c["country"]: c for c in window["countries"]}
    assert by_country["DE"] == {"country": "DE", "visits": 5.0, "bookings": 1.0}
    assert by_country["US"]["bookings"] == 1.0
    assert by_country["XX"]["bookings"] == 0.0


def test_fetch_stats_prometheus_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(fail)
    result = stats.fetch_stats("http://prometheus:9090", transport=transport)
    assert result["prometheus_ok"] is False
    assert result["windows"] == []


def test_fetch_stats_bad_payload() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"not-json"))
    result = stats.fetch_stats("http://prometheus:9090", transport=transport)
    assert result["prometheus_ok"] is False


def test_window_labels() -> None:
    transport = mock_prometheus({}, {})
    result: dict[str, Any] = stats.fetch_stats("http://prometheus:9090", transport=transport)
    assert [w["key"] for w in result["windows"]] == ["24h", "7d"]
    assert [w["label"] for w in result["windows"]] == ["24 часа", "7 дней"]
