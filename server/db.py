"""SQLite storage for booking requests.

A single connection guarded by a lock is plenty for a landing-site workload.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Final

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    name TEXT NOT NULL,
    contact TEXT NOT NULL,
    contact_method TEXT NOT NULL DEFAULT 'telegram'
        CHECK (contact_method IN ('telegram', 'instagram', 'whatsapp', 'email')),
    program TEXT NOT NULL,
    preferred_date TEXT NOT NULL,
    preferred_time TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'confirmed', 'cancelled'))
);
"""

_ALLOWED_STATUS: Final = frozenset({"new", "confirmed", "cancelled"})
_ALLOWED_METHODS: Final = frozenset({"telegram", "instagram", "whatsapp", "email"})


class BookingsDB:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Лёгкие миграции для уже существующих баз.

        1. БД без колонки contact_method — добавляем с default 'telegram'.
        2. Если CHECK-констрейнт колонки не знает 'email' (старая схема) —
           пересобираем таблицу (SQLite не умеет менять CHECK через ALTER).
        """
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(bookings)")}
        if "contact_method" not in columns:
            self._conn.execute(
                "ALTER TABLE bookings ADD COLUMN contact_method TEXT NOT NULL DEFAULT 'telegram'"
            )

        table_sql_row = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'bookings'"
        ).fetchone()
        if table_sql_row and "email" not in (table_sql_row[0] or ""):
            self._conn.executescript(
                """
                BEGIN;
                CREATE TABLE bookings_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    name TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    contact_method TEXT NOT NULL DEFAULT 'telegram'
                        CHECK (contact_method IN ('telegram', 'instagram', 'whatsapp', 'email')),
                    program TEXT NOT NULL,
                    preferred_date TEXT NOT NULL,
                    preferred_time TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new', 'confirmed', 'cancelled'))
                );
                INSERT INTO bookings_new (
                    id, created_at, name, contact, contact_method, program,
                    preferred_date, preferred_time, comment, status
                )
                SELECT id, created_at, name, contact, contact_method, program,
                       preferred_date, preferred_time, comment, status
                FROM bookings;
                DROP TABLE bookings;
                ALTER TABLE bookings_new RENAME TO bookings;
                COMMIT;
                """
            )

    def add(
        self,
        *,
        name: str,
        contact: str,
        contact_method: str,
        program: str,
        preferred_date: str,
        preferred_time: str,
        comment: str,
    ) -> int:
        if contact_method not in _ALLOWED_METHODS:
            raise ValueError(f"unsupported contact method: {contact_method}")
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO bookings (name, contact, contact_method, program,"
                " preferred_date, preferred_time, comment) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    contact,
                    contact_method,
                    program,
                    preferred_date,
                    preferred_time,
                    comment,
                ),
            )
            self._conn.commit()
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("INSERT into bookings did not return lastrowid")
            return row_id

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, name, contact, contact_method, program,"
                " preferred_date, preferred_time, comment, status FROM bookings"
                " ORDER BY id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def set_status(self, booking_id: int, status: str) -> bool:
        if status not in _ALLOWED_STATUS:
            raise ValueError(f"unsupported status: {status}")
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id)
            )
            self._conn.commit()
        return cursor.rowcount > 0
