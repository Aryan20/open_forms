# keyring.py
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
Credential storage via the GNOME Keyring (libsecret), per SYNC_ARCHITECTURE.md §3.4.
OAuth tokens and WebDAV passwords are never written to sync.db or the form
JSON — only here. Requires the `org.freedesktop.secrets` Flatpak permission.
"""

import json
from typing import Any

Secret: Any

try:
    import gi
    gi.require_version("Secret", "1")
    from gi.repository import Secret
    _HAS_SECRET = True
except (ImportError, ValueError):
    Secret = None
    _HAS_SECRET = False

_SCHEMA = None
if _HAS_SECRET:
    _SCHEMA = Secret.Schema.new(
        "in.aryank.openforms",
        Secret.SchemaFlags.NONE,
        {
            "backend": Secret.SchemaAttributeType.STRING,
            "form": Secret.SchemaAttributeType.STRING,
        },
    )


class KeyringUnavailable(Exception):
    """Raised when libsecret / a running Secret Service is not available."""


def _require_secret() -> None:
    if not _HAS_SECRET:
        raise KeyringUnavailable("libsecret (gi.repository.Secret) is not available")


def store_token(form_name: str, backend: str, token: dict) -> None:
    """Persist a credential dict (OAuth tokens, WebDAV username/password, ...)."""
    _require_secret()
    Secret.password_store_sync(
        _SCHEMA,
        {"backend": backend, "form": form_name},
        Secret.COLLECTION_DEFAULT,
        f"Open Forms – {backend} credentials for {form_name}",
        json.dumps(token),
        None,
    )


def load_token(form_name: str, backend: str) -> dict | None:
    _require_secret()
    raw = Secret.password_lookup_sync(_SCHEMA, {"backend": backend, "form": form_name}, None)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def clear_token(form_name: str, backend: str) -> None:
    _require_secret()
    Secret.password_clear_sync(_SCHEMA, {"backend": backend, "form": form_name}, None)


def is_available() -> bool:
    return _HAS_SECRET
