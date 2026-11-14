"""Prometheus-метрики посещений сайта по регионам.

Регион (страна) посетителя берётся из заголовка ``CF-IPCountry``, который
Cloudflare добавляет к каждому запросу к origin (основной домен
iriskating.com проксирован через CF — см. docs/cloudflare.md в репозитории
бота). Если заголовка нет (прямой заход на sslip.io, локальный запуск) —
метрика пишется с кодом ``XX`` (unknown).

Метрики:
- ``iriskating_site_visits_total{country, page}`` — посещения лендинга;
- ``iriskating_booking_requests_total{country, program}`` — отправленные
  заявки (конверсия по регионам).

Счётчики живут в процессе uvicorn (CMD без ``--workers``). Если когда-нибудь
появится несколько воркеров — понадобится multiprocess-режим prometheus_client
(https://prometheus.github.io/client_python/multiprocess/).
"""

from __future__ import annotations

import re

from prometheus_client import Counter
from starlette.datastructures import Headers

COUNTRY_UNKNOWN = "XX"

# Пути, считающиеся «визитом» на сайт. /admin не считаем: это рабочий
# инструмент владельца, а не посещение посетителя.
VISIT_PATHS = frozenset({"/", "/index.html"})

# Код страны из CF-IPCountry: ISO 3166-1 alpha-2 + спец-коды CF (T1 — Tor,
# XX — unknown). Ограничиваем длину/алфавит на случай левого значения.
_COUNTRY_RE = re.compile(r"^[A-Z0-9]{1,8}$")

site_visits = Counter(
    "iriskating_site_visits_total",
    "Landing page visits by visitor country and page",
    ("country", "page"),
)

booking_requests = Counter(
    "iriskating_booking_requests_total",
    "Booking requests accepted by visitor country and program",
    ("country", "program"),
)


def visitor_country(headers: Headers) -> str:
    """Код страны посетителя из CF-IPCountry (Cloudflare) или 'XX'."""
    raw = headers.get("cf-ipcountry", "").strip().upper()
    if raw and _COUNTRY_RE.fullmatch(raw):
        return raw
    return COUNTRY_UNKNOWN
