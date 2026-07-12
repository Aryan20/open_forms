# field_type_dialog.py
#
# Copyright 2025 Aryan Kaushik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk


_FIELD_TYPES = [
    ("entry",    "Short Text",      "text-x-generic-symbolic",       "Single-line text input"),
    ("text",     "Long Text",       "insert-text-symbolic",          "Multi-line text area"),
    ("dropdown", "Dropdown",        "pan-down-symbolic",             "Single-select from a list"),
    ("radio",    "Multiple Choice", "checkbox-symbolic",             "Pick one from a list"),
    ("check",    "Checkbox",        "checkbox-checked-symbolic",     "Boolean yes/no toggle"),
    ("spin",     "Number",          "list-add-symbolic",             "Numeric spinner with range"),
    ("calendar", "Date",            "x-office-calendar-symbolic",    "Date picker"),
    ("label",    "Label / Title",   "font-select-symbolic",          "Static display text"),
    ("picture",  "Image",           "image-x-generic-symbolic",      "Embed a picture"),
]


class FieldTypeDialog(Adw.Dialog):
    """
    Bottom-sheet / dialog that lets the user pick a field type to add.
    On narrow screens Adw.Dialog already behaves as a bottom sheet.
    Calls on_type_chosen(ftype: str) and closes itself.
    """

    def __init__(self, on_type_chosen):
        super().__init__()
        self._on_type_chosen = on_type_chosen

        self.set_title("Add Field")
        self.set_content_width(360)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        listbox = Gtk.ListBox()
        listbox.add_css_class("boxed-list")
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for ftype, name, icon_name, subtitle in _FIELD_TYPES:
            row = Adw.ActionRow(title=name, subtitle=subtitle)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))
            row.set_activatable(True)
            row.connect("activated", self._make_handler(ftype))
            listbox.append(row)

        clamp = Adw.Clamp(maximum_size=400)
        clamp.set_child(listbox)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_propagate_natural_height(True)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(scroll)

        toolbar_view.set_content(box)
        self.set_child(toolbar_view)

    def _make_handler(self, ftype: str):
        def handler(_row):
            self._on_type_chosen(ftype)
            self.close()
        return handler
