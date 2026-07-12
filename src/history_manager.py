# history_manager.py
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

import json
import os
from datetime import datetime

from gi.repository import GLib

MAX_ENTRIES = 50


def _history_file_path() -> str:
    data_dir = os.path.join(GLib.get_user_data_dir(), "in.aryank.openforms")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "history.json")


def load_history() -> list:
    """Return history entries, most recently opened first."""
    path = _history_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save_history(entries: list) -> None:
    try:
        with open(_history_file_path(), "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def add_entry(form_name: str, config_path: str, csv_path: str | None) -> None:
    """Record that a form was opened, moving it to the top if already present."""
    if not config_path:
        return
    entries = [e for e in load_history() if e.get("config_path") != config_path]
    entries.insert(
        0,
        {
            "form_name": form_name or os.path.basename(config_path),
            "config_path": config_path,
            "csv_path": csv_path,
            "last_opened": int(datetime.now().timestamp()),
        },
    )
    _save_history(entries[:MAX_ENTRIES])


def remove_entry(config_path: str) -> None:
    _save_history([e for e in load_history() if e.get("config_path") != config_path])


def clear_history() -> None:
    _save_history([])


def format_last_opened(timestamp: int) -> str:
    """Human-friendly relative timestamp, mirroring the granularity used for CSV dates."""
    now = datetime.now()
    dt = datetime.fromtimestamp(timestamp)
    if now.date() == dt.date():
        return dt.strftime("Today %H:%M")
    if now.year == dt.year and now.isocalendar()[1] == dt.isocalendar()[1]:
        return dt.strftime("%a %H:%M")
    if now.year == dt.year:
        return dt.strftime("%d %b %H:%M")
    return dt.strftime("%d %b %Y %H:%M")
