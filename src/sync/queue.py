# queue.py
#
# Copyright 2025 Aryan Kaushik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""
SQLite-backed sync queue. The CSV itself is append-only and remains the
source of truth; this file only tracks how far a backend has gotten
(`last_synced_row`) plus a small history log for the settings panel's
status line.
"""

import csv
import io
import os
import sqlite3
from datetime import datetime, timezone


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT,
            row_index  INTEGER,
            status     TEXT,
            message    TEXT
        )
        """
    )
    return conn


def init_db(db_path: str) -> None:
    conn = _connect(db_path)
    conn.commit()
    conn.close()


def get_config(db_path: str, key: str) -> str | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_config(db_path: str, key: str, value: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO sync_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def clear_config(db_path: str, key: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM sync_state WHERE key = ?", (key,))
        conn.commit()
    finally:
        conn.close()


def get_last_synced_row(db_path: str) -> int:
    """0-based index of the last row confirmed synced, or -1 if nothing has synced yet."""
    value = get_config(db_path, "last_synced_row")
    return int(value) if value is not None else -1


def set_last_synced_row(db_path: str, row_index: int) -> None:
    set_config(db_path, "last_synced_row", str(row_index))


def mark_all_synced(db_path: str, csv_path: str) -> None:
    """Mark every existing row synced, so linking a new destination only
    picks up rows added after this point, not the form's whole history."""
    set_last_synced_row(db_path, count_csv_rows(csv_path) - 1)


def reset_sync_progress(db_path: str) -> None:
    """Rewind so the next push includes every row from the start - backs
    the explicit 'sync all responses' action."""
    set_last_synced_row(db_path, -1)


def log_sync_ok(db_path: str, start_row: int, end_row: int) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO sync_log (timestamp, row_index, status, message) VALUES (?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                end_row,
                "ok",
                f"synced rows {start_row}-{end_row}" if end_row >= start_row else "nothing to sync",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def log_sync_error(db_path: str, row_index: int, message: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO sync_log (timestamp, row_index, status, message) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), row_index, "error", message),
        )
        conn.commit()
    finally:
        conn.close()


def last_log_entry(db_path: str) -> dict | None:
    """Most recent sync_log row, used to render the settings panel's status line."""
    if not os.path.exists(db_path):
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT timestamp, row_index, status, message FROM sync_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {"timestamp": row[0], "row_index": row[1], "status": row[2], "message": row[3]}
    finally:
        conn.close()


def read_csv_from(csv_path: str, start: int) -> list[dict]:
    """Return CSV rows (as ordered dicts) at 0-based indices >= start."""
    start = max(start, 0)
    return _read_all_rows(csv_path)[start:]


def _read_all_rows(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def read_csv_headers(csv_path: str) -> list[str]:
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader, [])


def count_csv_rows(csv_path: str) -> int:
    """Number of data rows (header excluded)."""
    if not os.path.exists(csv_path):
        return 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(1 for _ in reader)


def read_csv_rows_from(csv_path: str, start: int) -> tuple[list[str] | None, list[list[str]]]:
    """(header_row, data_rows) at 0-based indices >= start, via csv.reader so
    embedded newlines in quoted fields don't throw off the row count."""
    if not os.path.exists(csv_path):
        return None, []
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return None, []
    header, data = rows[0], rows[1:]
    return header, data[max(start, 0):]


def rows_to_csv_text(rows: list[list[str]]) -> str:
    """Serialize rows back to CSV text (same dialect csv.writer/DictWriter use)."""
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def db_path_for_csv(csv_path: str) -> str:
    """`<form_name>.csv` -> `<form_name>.sync.db`."""
    base, _ext = os.path.splitext(csv_path)
    return f"{base}.sync.db"
