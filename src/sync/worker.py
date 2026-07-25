# worker.py
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

import threading
from datetime import datetime, timezone

from .backend import SyncBackend, SyncError
from .queue import log_sync_error


class SyncWorker(threading.Thread):
    """
    Background thread (daemon, so it never blocks app exit) that periodically
    pushes pending CSV rows to a SyncBackend. See SYNC_ARCHITECTURE.md §3.2.

    This class never touches GTK. `on_status(status, message)` is invoked from
    the worker thread itself — callers that update widgets must marshal it
    through GLib.idle_add.
    """

    def __init__(
        self,
        backend: SyncBackend,
        csv_path: str,
        db_path: str,
        interval: int = 30,
        on_status=None,
    ):
        super().__init__(daemon=True)
        self.backend = backend
        self.csv_path = csv_path
        self.db_path = db_path
        self.interval = interval
        self.on_status = on_status
        self._trigger = threading.Event()
        self._stop = threading.Event()

    def trigger(self) -> None:
        """Wake the worker immediately (e.g. after a new row is appended, or 'Sync Now')."""
        self._trigger.set()

    def stop(self) -> None:
        self._stop.set()
        self._trigger.set()

    def _report(self, status: str, message: str = "") -> None:
        if self.on_status:
            self.on_status(status, message)

    def run(self) -> None:
        backoff = self.interval
        while not self._stop.is_set():
            self._trigger.wait(timeout=backoff)
            self._trigger.clear()
            if self._stop.is_set():
                break
            try:
                pushed = self.backend.push_pending(self.csv_path, self.db_path)
                backoff = self.interval
                now = datetime.now(timezone.utc).strftime("%H:%M:%S")
                if pushed:
                    self._report("ok", f"Synced {pushed} row(s) at {now}")
                else:
                    self._report("ok", f"Nothing new to sync (checked {now})")
            except SyncError as e:
                backoff = min(backoff * 2, 600)
                log_sync_error(self.db_path, -1, str(e))
                self._report("error", str(e))
            except Exception as e:
                # don't let an unhandled backend error kill the thread silently
                backoff = min(backoff * 2, 600)
                log_sync_error(self.db_path, -1, f"Unexpected error: {e}")
                self._report("error", f"Unexpected error: {e}")
