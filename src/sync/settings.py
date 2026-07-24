# settings.py
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
App-wide (not per-form) non-secret sync settings — currently just the
default sync interval. Credentials never live here; see sync/keyring.py.
"""

import json
import os

from gi.repository import GLib

DEFAULT_INTERVAL = 30


def _settings_path() -> str:
    config_dir = os.path.join(GLib.get_user_config_dir(), "in.aryank.openforms")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "sync-settings.json")


def load_settings() -> dict:
    path = _settings_path()
    if not os.path.exists(path):
        return {"interval": DEFAULT_INTERVAL}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"interval": DEFAULT_INTERVAL}
    if not isinstance(data, dict):
        return {"interval": DEFAULT_INTERVAL}
    data.setdefault("interval", DEFAULT_INTERVAL)
    return data


def save_settings(settings: dict) -> None:
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


def get_interval() -> int:
    return int(load_settings().get("interval", DEFAULT_INTERVAL))


def set_interval(seconds: int) -> None:
    settings = load_settings()
    settings["interval"] = int(seconds)
    save_settings(settings)
