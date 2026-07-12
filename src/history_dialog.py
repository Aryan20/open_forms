# history_dialog.py
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

import os

from gi.repository import Adw, Gtk

from .history_manager import clear_history, format_last_opened, load_history, remove_entry


class HistoryDialog(Adw.Dialog):
    """
    Shows previously opened forms so the user can quickly reopen one
    without re-picking its JSON config and CSV file.
    Supports text search, per-row removal, and clearing all history.
    """

    def __init__(self, on_open):
        super().__init__()
        self._on_open = on_open
        self._rows: list[tuple[Adw.ActionRow, dict]] = []

        self.set_title("History")
        self.set_content_width(480)
        self.set_content_height(560)

        self._build_ui()
        self._reload()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Search history…")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self._search_entry)

        clear_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Clear All")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", self._confirm_clear_all)
        header.pack_start(clear_btn)

        toolbar_view.add_top_bar(header)

        self._listbox = Gtk.ListBox()
        self._listbox.add_css_class("boxed-list")
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.set_activate_on_single_click(True)
        self._listbox.connect("row-activated", self._on_row_activated)

        clamp = Adw.Clamp(maximum_size=480)
        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner_box.set_margin_top(12)
        inner_box.set_margin_bottom(12)
        inner_box.set_margin_start(12)
        inner_box.set_margin_end(12)
        inner_box.append(self._listbox)
        clamp.set_child(inner_box)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(clamp)

        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

    def _reload(self):
        self._entries = load_history()
        self._populate_list()

    def _populate_list(self):
        while (child := self._listbox.get_first_child()):
            self._listbox.remove(child)
        self._rows.clear()

        if not self._entries:
            placeholder = Adw.ActionRow(
                title="No history yet",
                subtitle="Forms you open will be listed here.",
            )
            placeholder.add_prefix(Gtk.Image.new_from_icon_name("dialog-information-symbolic"))
            self._listbox.append(placeholder)
            return

        for entry in self._entries:
            row = self._build_row(entry)
            self._listbox.append(row)
            self._rows.append((row, entry))

    def _build_row(self, entry: dict) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=entry.get("form_name") or os.path.basename(entry.get("config_path", "")),
            subtitle=entry.get("config_path", ""),
            activatable=True,
        )
        row.set_subtitle_lines(1)

        time_label = Gtk.Label(label=format_last_opened(entry.get("last_opened", 0)))
        time_label.add_css_class("dim-label")
        time_label.add_css_class("caption")
        row.add_suffix(time_label)

        del_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Remove from history",
        )
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", lambda *_: self._remove_entry(entry))
        row.add_suffix(del_btn)

        return row

    def _remove_entry(self, entry: dict):
        remove_entry(entry.get("config_path", ""))
        self._reload()

    def _confirm_clear_all(self, *_):
        dialog = Adw.AlertDialog(
            heading="Clear History?",
            body="All entries will be permanently removed. Your form files themselves are not affected.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_clear_response)
        dialog.present(self)

    def _on_clear_response(self, _dialog, response):
        if response == "clear":
            clear_history()
            self._reload()

    def _on_row_activated(self, _listbox, row):
        for r, entry in self._rows:
            if r is row:
                self.close()
                self._on_open(entry)
                return

    def _on_search_changed(self, entry):
        query = entry.get_text().strip().lower()
        for row, e in self._rows:
            text = (e.get("form_name", "") + " " + e.get("config_path", "")).lower()
            row.set_visible(not query or query in text)
