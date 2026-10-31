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
    program TEXT NOT NULL,
    preferred_date TEXT NOT NULL,
    preferred_time TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'confirmed', 'cancelled'))
);
"""

_ALLOWED_STATUS: Final = frozenset({"new", "confirmed", "cancelled"})


class BookingsDB:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def add(
        self,
        *,
        name: str,
        contact: str,
        program: str,
        preferred_date: str,
        preferred_time: str,
        comment: str,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO bookings (name, contact, program, preferred_date,"
                " preferred_time, comment) VALUES (?, ?, ?, ?, ?, ?)",
                (name, contact, program, preferred_date, preferred_time, comment),
            )
            self._conn.commit()
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("INSERT into bookings did not return lastrowid")
            return row_id

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, name, contact, program, preferred_date,"
                " preferred_time, comment, status FROM bookings ORDER BY id DESC"
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
