# google_sheets.py
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
Google Sheets sync backend. Implements the OAuth2 PKCE + local-redirect flow
and the append API described in SYNC_ARCHITECTURE.md §4. Uses only the
standard library for HTTP (urllib, http.server, json) - no google-auth or
gspread dependency - to keep the Flatpak bundle small.

The OAuth client id/secret are NOT bundled with the app (there is no server
component to keep them in). The user brings their own OAuth client from the
Google Cloud Console, entered once app-wide in sync_settings_dialog.py - not
per form. The connected account and client credentials are stored in the
GNOME Keyring under a fixed app-wide scope (see _APP_SCOPE below), so every
form shares the same Google connection; each form only picks which sheet it
pushes to (see sync_panel.py). This mirrors how other credential-less
open-source desktop apps integrate with Google APIs.
"""

import base64
import hashlib
import http.server
import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import cast

from . import keyring
from .backend import SyncBackend, SyncConfig, SyncError
from .queue import (
    get_config,
    get_last_synced_row,
    log_sync_ok,
    read_csv_from,
    read_csv_headers,
    set_config,
    set_last_synced_row,
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"

# Access tokens are refreshed this long before their real expiry to absorb
# clock skew and in-flight request time.
_TOKEN_REFRESH_SKEW = 60

# Applied to every urlopen() call below - otherwise a stalled connection
# blocks the worker thread forever with no error surfaced.
_REQUEST_TIMEOUT = 30

# Keyring "form" attribute used for app-wide (not per-form) credentials -
# the OAuth client and the connected Google account are shared by every form.
_APP_SCOPE = "app"
_CLIENT_KEY = "google_oauth_client"
_TOKEN_KEY = "google_sheets"

# Serializes token refreshes across forms/threads sharing this account.
_token_lock = threading.Lock()

_SHEET_URL_ID_RE = re.compile(r"/spreadsheets/(?:u/\d+/)?d/([a-zA-Z0-9_-]+)")


def extract_spreadsheet_id(text: str) -> str:
    """Pull the spreadsheet ID out of a pasted Sheets URL, or pass through a bare ID.

    Raises ValueError if it looks like a URL but doesn't match a known Sheets
    URL shape, rather than storing the whole URL as the "id".
    """
    text = text.strip()
    match = _SHEET_URL_ID_RE.search(text)
    if match:
        return match.group(1)
    if "://" in text or text.startswith("www."):
        raise ValueError("Couldn't find a spreadsheet ID in that link.")
    return text


_GID_RE = re.compile(r"[#&?]gid=(\d+)")


def extract_gid(text: str) -> int | None:
    """Tab id from a pasted URL's #gid=... / &gid=... fragment, if present."""
    match = _GID_RE.search(text)
    return int(match.group(1)) if match else None


def _a1_quote(sheet_name: str) -> str:
    """Quote a sheet title for A1-notation ranges, e.g. `'My Form'!1:1`."""
    return "'" + sheet_name.replace("'", "''") + "'"


class _OAuthCallbackServer(http.server.HTTPServer):
    """HTTPServer with a typed slot for the single callback's query params."""

    oauth_result: dict[str, list[str]] | None = None


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Receives the single `/oauth2callback?code=...` redirect from Google."""

    def do_GET(self):
        server = cast(_OAuthCallbackServer, self.server)
        parsed = urllib.parse.urlparse(self.path)
        server.oauth_result = urllib.parse.parse_qs(parsed.query)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if "code" in server.oauth_result:
            body = "<html><body><h3>Open Forms connected. You can close this tab.</h3></body></html>"
        else:
            body = "<html><body><h3>Authorization failed. You can close this tab.</h3></body></html>"
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *_args):
        pass


def _make_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


class GoogleSheetsBackend(SyncBackend):
    """Appends new CSV rows to a Google Sheet via the Sheets API v4.

    Credentials (OAuth client + connected account) are app-wide - every
    instance reads/writes the same Keyring entries regardless of `form_name`,
    which is only used as a default spreadsheet title.
    """

    def __init__(self, form_name: str = ""):
        self.form_name = form_name or "Form"
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._load_client_credentials()

    def configure(self, config: SyncConfig) -> None:
        self._load_client_credentials()

    def _load_client_credentials(self) -> None:
        creds = keyring.load_token(_APP_SCOPE, _CLIENT_KEY)
        if creds:
            self._client_id = creds.get("client_id")
            self._client_secret = creds.get("client_secret")

    # -- App-wide client/account management -------------------------------

    @staticmethod
    def set_client_credentials(client_id: str, client_secret: str) -> None:
        keyring.store_token(_APP_SCOPE, _CLIENT_KEY, {"client_id": client_id, "client_secret": client_secret})

    @staticmethod
    def get_client_id() -> str | None:
        creds = keyring.load_token(_APP_SCOPE, _CLIENT_KEY)
        return creds.get("client_id") if creds else None

    @staticmethod
    def get_client_secret() -> str | None:
        creds = keyring.load_token(_APP_SCOPE, _CLIENT_KEY)
        return creds.get("client_secret") if creds else None

    @staticmethod
    def has_client_credentials() -> bool:
        return keyring.load_token(_APP_SCOPE, _CLIENT_KEY) is not None

    @staticmethod
    def is_connected() -> bool:
        return keyring.load_token(_APP_SCOPE, _TOKEN_KEY) is not None

    @staticmethod
    def disconnect() -> None:
        keyring.clear_token(_APP_SCOPE, _TOKEN_KEY)

    # -- OAuth -----------------------------------------------------------

    def start_oauth_flow(self, on_complete) -> None:
        """
        Run the PKCE + local-redirect OAuth flow (SYNC_ARCHITECTURE.md §4.1)
        using the app-wide OAuth client saved via set_client_credentials().

        Opens the system browser and, in a background thread, blocks until
        Google redirects back to a temporary localhost server. Calls
        `on_complete(error)` when done (error is None on success). Callers
        driving GTK must marshal on_complete through GLib.idle_add.
        """
        if not self._client_id or not self._client_secret:
            on_complete(SyncError("No Google OAuth Client ID/Secret configured. Set them up in Sync Settings first."))
            return

        client_id, client_secret = self._client_id, self._client_secret
        verifier, challenge = _make_pkce_pair()
        state = secrets.token_urlsafe(24)

        server = _OAuthCallbackServer(("127.0.0.1", 0), _OAuthCallbackHandler)
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/oauth2callback"

        query = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
            }
        )
        auth_url = f"{AUTH_URL}?{query}"

        def _serve():
            try:
                import webbrowser
                webbrowser.open(auth_url)
                server.timeout = 180
                server.handle_request()
                result = server.oauth_result
                if result is None:
                    on_complete(SyncError("Authorization timed out or was cancelled."))
                    return
                returned_state = result.get("state", [None])[0]
                if returned_state != state:
                    on_complete(SyncError("Authorization response did not match this request. Please try again."))
                    return
                code = result.get("code", [None])[0]
                if not code:
                    on_complete(SyncError("Authorization was cancelled or denied."))
                    return
                try:
                    self._exchange_code(code, client_id, client_secret, redirect_uri, verifier)
                except SyncError as e:
                    on_complete(e)
                    return
                on_complete(None)
            finally:
                server.server_close()

        threading.Thread(target=_serve, daemon=True).start()

    def _exchange_code(self, code, client_id, client_secret, redirect_uri, verifier) -> None:
        data = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            }
        ).encode("ascii")
        try:
            with urllib.request.urlopen(
                urllib.request.Request(TOKEN_URL, data=data, method="POST"), timeout=_REQUEST_TIMEOUT
            ) as resp:
                token = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise SyncError(f"Token exchange failed: {e.read().decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            raise SyncError(f"Network unreachable: {e.reason}") from e

        token["obtained_at"] = time.time()
        keyring.store_token(_APP_SCOPE, _TOKEN_KEY, token)

    def _fresh_token(self) -> str:
        token = keyring.load_token(_APP_SCOPE, _TOKEN_KEY)
        if not token:
            raise SyncError("Not connected to Google Sheets. Please reconnect your account.")

        expires_at = token.get("obtained_at", 0) + token.get("expires_in", 0)
        if time.time() < expires_at - _TOKEN_REFRESH_SKEW:
            return token["access_token"]

        with _token_lock:
            # re-check in case another thread refreshed while we waited
            token = keyring.load_token(_APP_SCOPE, _TOKEN_KEY)
            if not token:
                raise SyncError("Not connected to Google Sheets. Please reconnect your account.")
            expires_at = token.get("obtained_at", 0) + token.get("expires_in", 0)
            if time.time() < expires_at - _TOKEN_REFRESH_SKEW:
                return token["access_token"]

            refresh_token = token.get("refresh_token")
            if not refresh_token:
                raise SyncError("Google session expired. Please reconnect your account.")
            if not self._client_id or not self._client_secret:
                raise SyncError("Missing Google OAuth client credentials. Reconnect your account.")

            data = urllib.parse.urlencode(
                {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
            ).encode("ascii")
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(TOKEN_URL, data=data, method="POST"), timeout=_REQUEST_TIMEOUT
                ) as resp:
                    refreshed = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    keyring.clear_token(_APP_SCOPE, _TOKEN_KEY)
                raise SyncError(f"Token refresh failed: {e.read().decode('utf-8', 'replace')}") from e
            except urllib.error.URLError as e:
                raise SyncError(f"Network unreachable: {e.reason}") from e

            refreshed.setdefault("refresh_token", refresh_token)
            refreshed["obtained_at"] = time.time()
            keyring.store_token(_APP_SCOPE, _TOKEN_KEY, refreshed)
            return refreshed["access_token"]

    # -- Sheets API --------------------------------------------------------

    def _request(self, url: str, body: dict, token: str, method: str = "POST") -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as e:
            message = e.read().decode("utf-8", "replace")
            if e.code == 429:
                retry_after = e.headers.get("Retry-After", "?")
                raise SyncError(f"Rate limited by Google Sheets (retry after {retry_after}s)") from e
            if e.code == 401:
                raise SyncError(f"Google authorization rejected: {message}") from e
            if e.code >= 500:
                raise SyncError(f"Google Sheets is unavailable ({e.code}): {message}") from e
            raise SyncError(f"Google Sheets API error {e.code}: {message}") from e
        except urllib.error.URLError as e:
            raise SyncError(f"Network unreachable: {e.reason}") from e

    def create_spreadsheet(self, title: str) -> str:
        """Create a new spreadsheet and return its id. Used by 'Create New Sheet' in the UI."""
        token = self._fresh_token()
        body = {"properties": {"title": title}, "sheets": [{"properties": {"title": title}}]}
        result = self._request(SHEETS_BASE_URL, body, token, method="POST")
        return result["spreadsheetId"]

    def get_sheet_title(self, sheet_id: str, gid: int | None = None) -> str:
        """Title of the tab matching `gid`, or the first tab if not given."""
        token = self._fresh_token()
        url = f"{SHEETS_BASE_URL}/{sheet_id}?fields=sheets.properties"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise SyncError(
                    "Spreadsheet not found - check the ID/link and that your Google account has access."
                ) from e
            raise SyncError(f"Could not read spreadsheet info: {e.read().decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            raise SyncError(f"Network unreachable: {e.reason}") from e

        sheets = data.get("sheets") or []
        if not sheets:
            raise SyncError("That spreadsheet has no sheets/tabs.")
        if gid is not None:
            for sheet in sheets:
                if sheet.get("properties", {}).get("sheetId") == gid:
                    return sheet["properties"]["title"]
            raise SyncError(f"Could not find a tab with gid={gid} in that spreadsheet.")
        return sheets[0]["properties"]["title"]

    def link_sheet(self, db_path: str, sheet_id: str, sheet_name: str) -> None:
        set_config(db_path, "sheet_id", sheet_id)
        set_config(db_path, "sheet_name", sheet_name or self.form_name)

    def test_connection(self, db_path: str) -> bool:
        try:
            self._fresh_token()
            return True
        except SyncError:
            return False

    def ensure_headers(self, db_path: str, headers: list[str]) -> None:
        """Write the header row only if the sheet is empty; leave an existing one alone."""
        sheet_id = get_config(db_path, "sheet_id")
        if not sheet_id:
            return  # push_pending() will raise its own "no sheet linked" error
        sheet_name = get_config(db_path, "sheet_name") or self.form_name
        token = self._fresh_token()

        range_url = f"{SHEETS_BASE_URL}/{sheet_id}/values/{urllib.parse.quote(_a1_quote(sheet_name))}!1:1"
        req = urllib.request.Request(f"{range_url}?majorDimension=ROWS", method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise SyncError("Linked spreadsheet was not found. Re-link a sheet in sync settings.") from e
            raise SyncError(f"Could not read sheet headers: {e.read().decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            raise SyncError(f"Network unreachable: {e.reason}") from e

        existing = (data.get("values") or [[]])[0]
        if not existing:
            body = {"values": [headers], "majorDimension": "ROWS"}
            self._request(f"{range_url}?valueInputOption=RAW", body, token, method="PUT")

    def push_pending(self, csv_path: str, db_path: str) -> int:
        last_row = get_last_synced_row(db_path)
        rows = read_csv_from(csv_path, start=last_row + 1)
        if not rows:
            return 0

        self.ensure_headers(db_path, read_csv_headers(csv_path))

        sheet_id = get_config(db_path, "sheet_id")
        if not sheet_id:
            raise SyncError("No Google Sheet linked. Open sync settings and connect one.")
        sheet_name = get_config(db_path, "sheet_name") or self.form_name

        token = self._fresh_token()
        body = {"values": [list(row.values()) for row in rows], "majorDimension": "ROWS"}
        url = f"{SHEETS_BASE_URL}/{sheet_id}/values/{urllib.parse.quote(_a1_quote(sheet_name))}!A1:append"
        params = "valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        self._request(f"{url}?{params}", body, token, method="POST")

        set_last_synced_row(db_path, last_row + len(rows))
        log_sync_ok(db_path, last_row + 1, last_row + len(rows))
        return len(rows)
