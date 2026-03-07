# field_editor_row.py
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

from .form_model import FormField


_FIELD_ICONS = {
    "entry":    "text-x-generic-symbolic",
    "text":     "insert-text-symbolic",
    "radio":    "checkbox-symbolic",
    "check":    "checkbox-checked-symbolic",
    "spin":     "list-add-symbolic",
    "calendar": "x-office-calendar-symbolic",
    "label":    "font-select-symbolic",
    "picture":  "image-x-generic-symbolic",
}

_REQUIRES_REQUIRED = ("entry", "text", "check", "radio", "calendar")


class FieldEditorRow(Adw.ExpanderRow):
    """
    One card in the builder list. Wraps a single FormField and keeps
    the dataclass in sync as the user edits properties.
    All changes are written directly into self.form_field — the builder
    page reads model.fields to serialise.
    """

    def __init__(self, form_field: FormField, on_delete, on_move_up, on_move_down):
        super().__init__()
        self.form_field = form_field
        self._build(on_delete, on_move_up, on_move_down)

    def _build(self, on_delete, on_move_up, on_move_down):
        self._refresh_title()
        self.set_subtitle(self.form_field.type)

        icon = Gtk.Image.new_from_icon_name(
            _FIELD_ICONS.get(self.form_field.type, "dialog-question-symbolic")
        )
        self.add_prefix(icon)

        for icon_name, callback in (
            ("go-up-symbolic",      lambda *_: on_move_up(self)),
            ("go-down-symbolic",    lambda *_: on_move_down(self)),
            ("user-trash-symbolic", lambda *_: on_delete(self)),
        ):
            btn = Gtk.Button(icon_name=icon_name, valign=Gtk.Align.CENTER)
            btn.add_css_class("flat")
            if icon_name == "user-trash-symbolic":
                btn.add_css_class("destructive-action")
            btn.connect("clicked", callback)
            self.add_suffix(btn)

        label_row = Adw.EntryRow(title="Label")
        label_row.set_text(self.form_field.label)
        label_row.connect("changed", self._on_label_changed)
        self.add_row(label_row)

        ftype = self.form_field.type

        if ftype in _REQUIRES_REQUIRED:
            req_row = Adw.SwitchRow(title="Required")
            req_row.set_active(self.form_field.required)
            req_row.connect("notify::active", self._on_required_changed)
            self.add_row(req_row)

        if ftype == "radio":
            self._build_options_editor()

        elif ftype == "spin":
            for attr, title, lo, hi in (
                ("min",  "Minimum", -999999, 999999),
                ("max",  "Maximum", -999999, 999999),
                ("step", "Step",    0.001,   999999),
            ):
                spin_row = Adw.SpinRow.new_with_range(lo, hi, 1)
                spin_row.set_title(title)
                spin_row.set_value(float(getattr(self.form_field, attr)))
                spin_row.connect(
                    "notify::value",
                    lambda r, _, a=attr: setattr(self.form_field, a, r.get_value()),
                )
                self.add_row(spin_row)

        elif ftype == "label":
            style_row = Adw.EntryRow(title="Style classes (comma-separated, e.g. title-1)")
            style_row.set_text(", ".join(self.form_field.style))
            style_row.connect("changed", self._on_style_changed)
            self.add_row(style_row)

        elif ftype == "picture":
            uri_row = Adw.EntryRow(title="Image URI (file:///…)")
            uri_row.set_text(self.form_field.uri)
            uri_row.connect(
                "changed",
                lambda r, *_: setattr(self.form_field, "uri", r.get_text()),
            )
            self.add_row(uri_row)

            for attr, title in (("width", "Width (px)"), ("height", "Height (px)")):
                s = Adw.SpinRow.new_with_range(20, 4096, 10)
                s.set_title(title)
                s.set_value(float(getattr(self.form_field, attr)))
                s.connect(
                    "notify::value",
                    lambda r, _, a=attr: setattr(self.form_field, a, int(r.get_value())),
                )
                self.add_row(s)

    def _on_label_changed(self, row):
        self.form_field.label = row.get_text()
        self._refresh_title()

    def _on_required_changed(self, row, _):
        self.form_field.required = row.get_active()

    def _on_style_changed(self, row):
        raw = row.get_text()
        self.form_field.style = [s.strip() for s in raw.split(",") if s.strip()]

    def _refresh_title(self):
        self.set_title(self.form_field.label or f"[{self.form_field.type}]")

    def _build_options_editor(self):
        self._options_expander = Adw.ExpanderRow(title="Options")
        self._options_expander.set_expanded(True)

        add_btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER)
        add_btn.add_css_class("flat")
        add_btn.set_tooltip_text("Add option")
        add_btn.connect("clicked", lambda *_: self._add_option_row(""))
        self._options_expander.add_suffix(add_btn)

        self._option_rows: list = []

        for opt in self.form_field.options:
            self._add_option_row(opt)

        self.add_row(self._options_expander)

    def _add_option_row(self, text: str):
        row = Adw.EntryRow(title="Option")
        row.set_text(text)

        del_btn = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.set_tooltip_text("Remove option")
        del_btn.connect("clicked", lambda *_: self._remove_option_row(row))
        row.add_suffix(del_btn)

        row.connect("changed", lambda *_: self._sync_options())
        self._option_rows.append(row)
        self._options_expander.add_row(row)
        self._sync_options()

    def _remove_option_row(self, row):
        self._options_expander.remove(row)
        self._option_rows.remove(row)
        self._sync_options()

    def _sync_options(self):
        self.form_field.options = [r.get_text() for r in self._option_rows]