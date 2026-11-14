"""Visit stats for the /admin dashboard: instant queries to Prometheus.

Админка (/admin) показывает визиты и заявки по странам за 24ч / 7д —
источник тот же, что и у Grafana (счётчики iriskating_site_* из
server/metrics.py), но без iframe и публичного доступа: эндпоинт
/api/stats закрыт сессионной авторизацией админа.

Prometheus живёт в той же docker-сети (PROMETHEUS_URL, по умолчанию
http://prometheus:9090). Если он недоступен — возвращается ответ с
prometheus_ok=false, админка показывает «недоступно», ничего не падает.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Final

import httpx

_TIMEOUT: Final = 2.0

# (ключ окна, подпись в админке, PromQL-окно)
_WINDOWS: Final[tuple[tuple[str, str], ...]] = (
    ("24h", "24 часа"),
    ("7d", "7 дней"),
)

_QUERIES: Final[dict[str, str]] = {
    "visits": "sum by (country) (increase(iriskating_site_visits_total[{window}]))",
    "bookings": "sum by (country) (increase(iriskating_booking_requests_total[{window}]))",
}


def parse_instant_vector(payload: dict[str, Any]) -> dict[str, float]:
    """Ответ /api/v1/query → {страна: значение}.

    Нечисловые и не-конечные значения (NaN/+Inf у пустых окон) пропускаются.
    """
    result: dict[str, float] = {}
    for series in payload.get("data", {}).get("result", []):
        metric = series.get("metric", {})
        country = str(metric.get("country", "XX")) if isinstance(metric, dict) else "XX"
        try:
            value = float(series["value"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if math.isfinite(value):
            result[country] = result.get(country, 0.0) + value
    return result


def _query(client: httpx.Client, query: str) -> dict[str, Any]:
    response = client.get("/api/v1/query", params={"query": query})
    response.raise_for_status()
    payload: Any = response.json()
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ValueError(f"unexpected prometheus response: {payload!r:.200}")
    return payload


def _window_row(client: httpx.Client, key: str, label: str) -> dict[str, Any]:
    visits = parse_instant_vector(_query(client, _QUERIES["visits"].format(window=key)))
    bookings = parse_instant_vector(_query(client, _QUERIES["bookings"].format(window=key)))

    merged: dict[str, dict[str, Any]] = {}
    for country, value in visits.items():
        merged[country] = {"country": country, "visits": value, "bookings": 0.0}
    for country, value in bookings.items():
        row = merged.setdefault(country, {"country": country, "visits": 0.0, "bookings": 0.0})
        row["bookings"] = value

    countries = sorted(
        merged.values(), key=lambda row: (-row["visits"], -row["bookings"], row["country"])
    )
    return {
        "key": key,
        "label": label,
        "visits": sum(row["visits"] for row in countries),
        "bookings": sum(row["bookings"] for row in countries),
        "countries": countries,
    }


def fetch_stats(
    prometheus_url: str, transport: httpx.BaseTransport | None = None
) -> dict[str, Any]:
    """Собрать статистику по всем окнам; при недоступности Prometheus — ok=False.

    transport — точка расширения для тестов (httpx.MockTransport).
    """
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        with httpx.Client(base_url=prometheus_url, timeout=_TIMEOUT, transport=transport) as client:
            windows = [_window_row(client, key, label) for key, label in _WINDOWS]
    except (httpx.HTTPError, ValueError, KeyError):
        return {"prometheus_ok": False, "generated_at": generated_at, "windows": []}

    return {
        "prometheus_ok": True,
        "generated_at": generated_at,
        "windows": windows,
    }
