# response_viewer.py
#
# Copyright 2025 Aryan Kaushik
#
# SPDX-License-Identifier: GPL-3.0-or-later

import csv
import os
import shutil

from gi.repository import Adw, Gtk, GLib


class ResponseViewerDialog(Adw.Dialog):
    """
    Shows collected responses from a CSV file as an expandable card list.
    Supports text search and per-row deletion (with a backup of the original).
    """

    def __init__(self, csv_path: str):
        super().__init__()
        self._csv_path = csv_path
        self._headers: list[str] = []
        self._rows: list[dict] = []
        self._expander_rows: list[tuple[Adw.ExpanderRow, int]] = []

        self.set_title("Responses")
        self.set_content_width(480)
        self.set_content_height(560)

        self._load_csv()
        self._build_ui()

    def _load_csv(self):
        if not os.path.exists(self._csv_path):
            return
        try:
            with open(self._csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._headers = list(reader.fieldnames or [])
                self._rows = list(reader)
        except Exception:
            pass

    def _rewrite_csv(self):
        backup = self._csv_path + ".bak"
        try:
            shutil.copy2(self._csv_path, backup)
        except Exception:
            pass
        try:
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self._headers)
                writer.writeheader()
                writer.writerows(self._rows)
        except Exception:
            pass

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Search entry in the header
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Search responses…")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self._search_entry)

        # Response count label
        self._count_label = Gtk.Label()
        self._count_label.add_css_class("dim-label")
        self._count_label.add_css_class("caption")

        # List
        self._listbox = Gtk.ListBox()
        self._listbox.add_css_class("boxed-list")
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        clamp = Adw.Clamp(maximum_size=480)
        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner_box.set_margin_top(12)
        inner_box.set_margin_bottom(12)
        inner_box.set_margin_start(12)
        inner_box.set_margin_end(12)
        inner_box.append(self._count_label)
        inner_box.append(self._listbox)
        clamp.set_child(inner_box)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(clamp)

        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

        self._populate_list()

    def _populate_list(self):
        # Clear existing rows
        while (child := self._listbox.get_first_child()):
            self._listbox.remove(child)
        self._expander_rows.clear()

        if not self._rows:
            placeholder = Adw.ActionRow(
                title="No responses yet",
                subtitle="Responses will appear here after the first submission.",
            )
            placeholder.add_prefix(
                Gtk.Image.new_from_icon_name("dialog-information-symbolic")
            )
            self._listbox.append(placeholder)
            self._count_label.set_label("")
            return

        for idx, row in enumerate(self._rows):
            expander = self._build_response_row(idx, row)
            self._listbox.append(expander)
            self._expander_rows.append((expander, idx))

        n = len(self._rows)
        self._count_label.set_label(f"{n} response{'s' if n != 1 else ''}")

    def _build_response_row(self, original_idx: int, row: dict) -> Adw.ExpanderRow:
        # Build a human-readable subtitle from the first 2 non-empty values
        preview_values = [v for v in row.values() if v][:2]
        subtitle = "  ·  ".join(preview_values) if preview_values else "empty"

        expander = Adw.ExpanderRow(
            title=f"Response #{original_idx + 1}",
            subtitle=subtitle,
        )

        # Delete button
        del_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Delete this response",
        )
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", lambda *_: self._confirm_delete(original_idx, expander))
        expander.add_suffix(del_btn)

        # Field detail rows
        for key, value in row.items():
            detail = Adw.ActionRow(title=key)
            detail.set_subtitle(str(value) if value else "—")
            detail.set_subtitle_selectable(True)
            expander.add_row(detail)

        return expander

    def _confirm_delete(self, original_idx: int, expander: Adw.ExpanderRow):
        dialog = Adw.AlertDialog(
            heading="Delete Response?",
            body=f"Response #{original_idx + 1} will be permanently removed from the CSV. "
                 "A backup (.bak) will be created first.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response, original_idx)
        dialog.present(self)

    def _on_delete_response(self, dialog, response: str, original_idx: int):
        if response != "delete":
            return
        if 0 <= original_idx < len(self._rows):
            self._rows.pop(original_idx)
            self._rewrite_csv()
            self._populate_list()

    def _on_search_changed(self, entry):
        query = entry.get_text().strip().lower()
        for expander, _idx in self._expander_rows:
            if not query:
                expander.set_visible(True)
                continue
            row_text = (expander.get_title() + " " + expander.get_subtitle()).lower()
            child = expander.get_first_child()
            while child:
                if isinstance(child, Adw.ActionRow):
                    row_text += " " + (child.get_subtitle() or "").lower()
                child = child.get_next_sibling()
            expander.set_visible(query in row_text)
