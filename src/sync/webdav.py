# webdav.py
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
WebDAV / Nextcloud sync backend (SYNC_ARCHITECTURE.md §5). No OAuth - basic
auth with a username + app password stored in the GNOME Keyring under a
fixed app-wide scope, shared by every form (configured once in
sync_settings_dialog.py). Each form only picks its own destination URL -
see link() and sync_panel.py.

The remote file is a shared log other devices (or a linked Google Form)
may also write to, so push_pending() never overwrites it - it fetches,
merges in this device's new rows, and PUTs back conditionally (ETag
If-Match, or If-None-Match: * on create), retrying on conflict.
"""

import base64
import csv
import io
import urllib.error
import urllib.request

from . import keyring
from .backend import SyncBackend, SyncConfig, SyncError
from .queue import (
    get_config,
    get_last_synced_row,
    log_sync_ok,
    read_csv_rows_from,
    rows_to_csv_text,
    set_config,
    set_last_synced_row,
)

# Keyring "form" attribute used for the app-wide (not per-form) credentials.
_APP_SCOPE = "app"
_CRED_KEY = "webdav"

# Fetch/merge/PUT rounds to try before giving up and letting the worker retry later.
_MAX_CONFLICT_RETRIES = 5


class WebDAVBackend(SyncBackend):
    """Appends this device's new rows to a shared remote CSV file over WebDAV."""

    def __init__(self, form_name: str = ""):
        self.form_name = form_name

    def configure(self, config: SyncConfig) -> None:
        pass  # credentials live in the Keyring; URL lives in sync.db (set via link())

    @staticmethod
    def set_credentials(username: str, password: str) -> None:
        keyring.store_token(_APP_SCOPE, _CRED_KEY, {"username": username, "password": password})

    @staticmethod
    def get_username() -> str | None:
        creds = keyring.load_token(_APP_SCOPE, _CRED_KEY)
        return creds.get("username") if creds else None

    @staticmethod
    def is_connected() -> bool:
        return keyring.load_token(_APP_SCOPE, _CRED_KEY) is not None

    @staticmethod
    def disconnect() -> None:
        keyring.clear_token(_APP_SCOPE, _CRED_KEY)

    def link(self, db_path: str, url: str) -> None:
        """Set this form's destination URL. Credentials are app-wide - see set_credentials()."""
        set_config(db_path, "webdav_url", url)

    def _credentials(self) -> str:
        token = keyring.load_token(_APP_SCOPE, _CRED_KEY)
        if not token:
            raise SyncError("No WebDAV credentials configured. Set them up in Sync Settings first.")
        userpass = f"{token['username']}:{token['password']}".encode("utf-8")
        return base64.b64encode(userpass).decode("ascii")

    def test_connection(self, db_path: str) -> bool:
        url = get_config(db_path, "webdav_url")
        if not url:
            return False
        try:
            creds = self._credentials()
        except SyncError:
            return False

        req = urllib.request.Request(url, method="PROPFIND")
        req.add_header("Authorization", f"Basic {creds}")
        req.add_header("Depth", "0")
        try:
            urllib.request.urlopen(req, timeout=10)
            return True
        except urllib.error.HTTPError as e:
            # 404 is fine - the file doesn't exist yet but the server/auth are reachable.
            return e.code not in (401, 403)
        except urllib.error.URLError:
            return False

    def ensure_headers(self, db_path: str, headers: list[str]) -> None:
        pass  # header check happens inline in push_pending, which fetches remote content anyway

    def _fetch_remote(self, url: str, creds: str) -> tuple[str | None, str | None]:
        """(content, etag); content is None if the remote file doesn't exist yet."""
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Basic {creds}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8"), resp.headers.get("ETag")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, None
            raise SyncError(f"Could not read remote CSV ({e.code}): {e.read().decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            raise SyncError(f"WebDAV server unreachable: {e.reason}") from e

    def _put(self, url: str, creds: str, content: str, *, if_match: str | None, if_none_match: str | None) -> bool:
        """Conditional PUT. Returns False on a 412/409 so the caller can retry instead of raising."""
        req = urllib.request.Request(url, data=content.encode("utf-8"), method="PUT")
        req.add_header("Authorization", f"Basic {creds}")
        req.add_header("Content-Type", "text/csv; charset=utf-8")
        if if_match:
            req.add_header("If-Match", if_match)
        if if_none_match:
            req.add_header("If-None-Match", if_none_match)
        try:
            urllib.request.urlopen(req, timeout=30)
            return True
        except urllib.error.HTTPError as e:
            if e.code in (412, 409):
                return False
            raise SyncError(f"WebDAV upload failed ({e.code}): {e.read().decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            raise SyncError(f"WebDAV server unreachable: {e.reason}") from e

    def push_pending(self, csv_path: str, db_path: str) -> int:
        previous_last = get_last_synced_row(db_path)
        header, new_rows = read_csv_rows_from(csv_path, previous_last + 1)
        if not new_rows:
            return 0  # nothing new since the last push

        url = get_config(db_path, "webdav_url")
        if not url:
            raise SyncError("No WebDAV URL configured. Open sync settings to set one.")
        creds = self._credentials()
        new_text = rows_to_csv_text(new_rows)

        succeeded = False
        for _attempt in range(_MAX_CONFLICT_RETRIES):
            remote_content, etag = self._fetch_remote(url, creds)
            exists = remote_content is not None and bool(remote_content.strip())

            if not exists:
                merged = (rows_to_csv_text([header]) if header else "") + new_text
            else:
                assert remote_content is not None
                remote_header = next(csv.reader(io.StringIO(remote_content)), [])
                if remote_header and header is not None and remote_header != header:
                    raise SyncError(
                        "The shared WebDAV file's columns no longer match this form "
                        "(it may have been edited elsewhere). Point this form at a "
                        "new URL, or fix the shared file's header row."
                    )
                merged = remote_content
                if not merged.endswith(("\r\n", "\n", "\r")):
                    merged += "\r\n"
                merged += new_text

            if remote_content is None:
                ok = self._put(url, creds, merged, if_match=None, if_none_match="*")
            else:
                ok = self._put(url, creds, merged, if_match=etag, if_none_match=None)
            if ok:
                succeeded = True
                break

        if not succeeded:
            raise SyncError(
                "Could not append to the shared WebDAV file after several attempts - "
                "another device kept winning the race. Will retry on the next sync."
            )

        new_last = previous_last + len(new_rows)
        set_last_synced_row(db_path, new_last)
        log_sync_ok(db_path, previous_last + 1, new_last)
        return len(new_rows)
