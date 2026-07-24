# backend.py
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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class SyncError(Exception):
    """Raised by a SyncBackend when push_pending / test_connection / ensure_headers fails.

    Caught by SyncWorker to trigger exponential back-off instead of crashing
    the background thread.
    """


@dataclass
class SyncConfig:
    """Non-sensitive, per-backend configuration (sheet id, WebDAV URL, ...).

    Credentials (OAuth tokens, passwords) never live here — see sync/keyring.py.
    """

    backend_id: str
    params: dict[str, Any] = field(default_factory=dict)


class SyncBackend(ABC):
    """Interface implemented by every sync destination (Google Sheets, WebDAV, ...)."""

    @abstractmethod
    def configure(self, config: SyncConfig) -> None:
        """Apply non-sensitive configuration ahead of a push."""

    @abstractmethod
    def test_connection(self, db_path: str) -> bool:
        """Return True if credentials/config in db_path currently allow a push."""

    @abstractmethod
    def push_pending(self, csv_path: str, db_path: str) -> int:
        """Read unsynced rows from csv_path, push to the backend, update
        last_synced_row in db_path on success. Returns rows pushed (0 if none)."""

    @abstractmethod
    def ensure_headers(self, db_path: str, headers: list[str]) -> None:
        """Create or verify that the destination has the correct column headers."""
