# __init__.py
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
Sync layer described in SYNC_ARCHITECTURE.md.

Pushes locally collected CSV responses to an external destination
(Google Sheets, WebDAV/Nextcloud, ...) in the background. Sync itself is
always opt-in per form: a form only pushes anywhere once its own sync.db
records a backend other than 'null'/unset (see sync_panel.py). Account-level
credentials (OAuth client, Google connection, WebDAV username/password) are
configured once, app-wide, in sync_settings_dialog.py.
"""

from typing import TYPE_CHECKING, Literal, overload

from .backend import SyncBackend, SyncConfig, SyncError
from .queue import db_path_for_csv, get_config, init_db

if TYPE_CHECKING:
    from .google_sheets import GoogleSheetsBackend
    from .webdav import WebDAVBackend

BACKEND_IDS = ("google_sheets", "webdav")

BACKEND_LABELS = {
    "google_sheets": "Google Sheets",
    "webdav": "WebDAV / Nextcloud",
}


class NullBackend(SyncBackend):
    """Log-only backend used to validate the queue/worker plumbing (milestone M1)."""

    def configure(self, config: SyncConfig) -> None:
        pass

    def test_connection(self, db_path: str) -> bool:
        return True

    def ensure_headers(self, db_path: str, headers: list) -> None:
        pass

    def push_pending(self, csv_path: str, db_path: str) -> int:
        from .queue import get_last_synced_row, log_sync_ok, read_csv_from, set_last_synced_row

        last_row = get_last_synced_row(db_path)
        rows = read_csv_from(csv_path, start=last_row + 1)
        if not rows:
            return 0
        set_last_synced_row(db_path, last_row + len(rows))
        log_sync_ok(db_path, last_row + 1, last_row + len(rows))
        return len(rows)


@overload
def get_backend(backend_id: Literal["google_sheets"], form_name: str = "") -> "GoogleSheetsBackend": ...
@overload
def get_backend(backend_id: Literal["webdav"], form_name: str = "") -> "WebDAVBackend": ...
@overload
def get_backend(backend_id: str, form_name: str = "") -> SyncBackend: ...
def get_backend(backend_id: str, form_name: str = "") -> SyncBackend:
    """Instantiate the backend registered for `backend_id`."""
    if backend_id == "null":
        return NullBackend()
    if backend_id == "google_sheets":
        from .google_sheets import GoogleSheetsBackend
        return GoogleSheetsBackend(form_name)
    if backend_id == "webdav":
        from .webdav import WebDAVBackend
        return WebDAVBackend(form_name)
    raise ValueError(f"Unknown sync backend: {backend_id}")


def backend_for_db(db_path: str, form_name: str = "") -> SyncBackend | None:
    """Return the configured backend for a sync.db, or None if sync is disabled."""
    backend_id = get_config(db_path, "backend")
    if not backend_id:
        return None
    return get_backend(backend_id, form_name)


def is_backend_configured(backend_id: str) -> bool:
    """Whether the app-wide account/credentials for `backend_id` are set up.

    Used by the per-form sync panel to decide whether to let a form push
    to a backend yet, or point the user at Sync Settings first.
    """
    if backend_id == "google_sheets":
        from .google_sheets import GoogleSheetsBackend
        return GoogleSheetsBackend.is_connected()
    if backend_id == "webdav":
        from .webdav import WebDAVBackend
        return WebDAVBackend.is_connected()
    return False
