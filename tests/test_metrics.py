"""Metrics tests: visits counted by region (CF-IPCountry), /metrics endpoint.

Counters are global (module-level in server.metrics), so assertions compare
deltas before/after each request rather than absolute values. No network.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


def sample_value(name: str, labels: dict[str, str]) -> float:
    """Текущее значение счётчика; 0 для ещё не существующей серии."""
    value = REGISTRY.get_sample_value(name, labels)
    return 0.0 if value is None else value


def create_booking(client: TestClient, headers: dict[str, str] | None = None) -> Any:
    return client.post(
        "/api/bookings",
        json={
            "name": "Anna",
            "contact": "anna@example.com",
            "contact_method": "telegram",
            "program": "individual",
            "preferred_date": "2026-11-20",
            "preferred_time": "evening",
            "comment": "",
        },
        headers=headers or {},
    )


# ---------- /metrics endpoint ----------


def test_metrics_endpoint_exposed(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "iriskating_site_visits_total" in response.text
    assert "iriskating_booking_requests_total" in response.text


# ---------- site visits ----------


def test_visit_counted_by_cf_country(client: TestClient) -> None:
    labels = {"country": "DE", "page": "landing"}
    before = sample_value("iriskating_site_visits_total", labels)
    response = client.get("/", headers={"CF-IPCountry": "DE"})
    assert response.status_code == 200
    assert sample_value("iriskating_site_visits_total", labels) == before + 1


def test_visit_lowercase_country_normalized(client: TestClient) -> None:
    labels = {"country": "GB", "page": "landing"}
    before = sample_value("iriskating_site_visits_total", labels)
    client.get("/", headers={"CF-IPCountry": "gb"})
    assert sample_value("iriskating_site_visits_total", labels) == before + 1


def test_visit_without_header_counts_unknown(client: TestClient) -> None:
    labels = {"country": "XX", "page": "landing"}
    before = sample_value("iriskating_site_visits_total", labels)
    client.get("/")
    assert sample_value("iriskating_site_visits_total", labels) == before + 1


def test_visit_with_garbage_header_counts_unknown(client: TestClient) -> None:
    labels = {"country": "XX", "page": "landing"}
    before = sample_value("iriskating_site_visits_total", labels)
    client.get("/", headers={"CF-IPCountry": "<script>"})
    assert sample_value("iriskating_site_visits_total", labels) == before + 1


def test_index_html_path_counts_as_landing(client: TestClient) -> None:
    labels = {"country": "FR", "page": "landing"}
    before = sample_value("iriskating_site_visits_total", labels)
    client.get("/index.html", headers={"CF-IPCountry": "FR"})
    assert sample_value("iriskating_site_visits_total", labels) == before + 1


def test_static_assets_not_counted_as_visits(client: TestClient) -> None:
    def all_visits() -> float:
        # имя серии Counter — *_total; семейство в collect() зовётся без суффикса,
        # поэтому фильтруем именно по имени серии
        return sum(
            s.value
            for metric in REGISTRY.collect()
            for s in metric.samples
            if s.name == "iriskating_site_visits_total"
        )

    before = all_visits()
    client.get("/css/styles.css")
    client.get("/js/main.js")
    client.get("/admin")
    assert all_visits() == before


# ---------- bookings by region ----------


def test_booking_counted_by_country_and_program(client: TestClient) -> None:
    labels = {"country": "US", "program": "individual"}
    before = sample_value("iriskating_booking_requests_total", labels)
    response = create_booking(client, headers={"CF-IPCountry": "US"})
    assert response.status_code == 200
    assert sample_value("iriskating_booking_requests_total", labels) == before + 1


def test_booking_without_header_counts_unknown(client: TestClient) -> None:
    labels = {"country": "XX", "program": "individual"}
    before = sample_value("iriskating_booking_requests_total", labels)
    response = create_booking(client)
    assert response.status_code == 200
    assert sample_value("iriskating_booking_requests_total", labels) == before + 1


def test_failed_booking_not_counted(client: TestClient) -> None:
    labels = {"country": "US", "program": "individual"}
    before = sample_value("iriskating_booking_requests_total", labels)
    response = client.post(
        "/api/bookings",
        json={
            "name": "X",
            "contact": "a@b.c",
            "program": "unknown-program",
            "preferred_date": "2026-11-20",
            "preferred_time": "evening",
        },
        headers={"CF-IPCountry": "US"},
    )
    assert response.status_code == 422
    assert sample_value("iriskating_booking_requests_total", labels) == before
