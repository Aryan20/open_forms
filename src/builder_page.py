# builder_page.py
#
# Copyright 2025 Aryan Kaushik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from gi.repository import Adw, Gtk, Gio

from .form_model import FormField, FormModel
from .field_editor_row import FieldEditorRow
from .field_type_dialog import FieldTypeDialog


@Gtk.Template(resource_path="/in/aryank/openforms/builder_page.ui")
class BuilderPage(Gtk.Box):
    """
    The GUI Form Builder page.
    Users can create or edit a form visually; the result is serialised
    to JSON (same schema as hand-written configs) when they hit Save.

    The page is opened as a new tab from FormConfig, just like FormPage.
    After saving, the produced JSON path is passed back so the tab title
    updates and the file can be immediately used.
    """

    __gtype_name__ = "BuilderPage"

    # Template children (defined in builder_page.ui)
    builder_toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    form_name_row: Adw.EntryRow = Gtk.Template.Child()
    fields_group: Adw.PreferencesGroup = Gtk.Template.Child()
    back_button: Gtk.Button = Gtk.Template.Child()
    kiosk_group: Adw.PreferencesGroup = Gtk.Template.Child()
    preview_scroll: Gtk.ScrolledWindow = Gtk.Template.Child()
    preview_separator: Gtk.Separator = Gtk.Template.Child()
    preview_toggle: Gtk.ToggleButton = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.model = FormModel()
        self._rows: list[FieldEditorRow] = []
        # If set, Save will suggest this path (used when editing an existing file)
        self._save_path: str | None = None
        self._preview_enabled = False

        # Wire the form-name entry (declared in UI template)
        self.form_name_row.connect("changed", self._on_form_name_changed)
        self._build_kiosk_section()

    def set_page(self, page):
        """Called by FormConfig after the tab is created, same pattern as FormPage."""
        self.page = page

    def load_from_model(self, model: FormModel):
        """Populate the builder from an existing FormModel (for editing a saved form)."""
        self.model = model
        self.form_name_row.set_text(model.form_name)
        self._load_kiosk_from_dict(model.kiosk)
        for ff in model.fields:
            self._append_row(ff)

    def set_save_path(self, path: str):
        """
        Pre-seed the save path so the file dialog opens at the original
        file's location and the user can overwrite with one click.
        """
        self._save_path = path

    def _build_kiosk_section(self):
        self._kiosk_reset_row = Adw.SpinRow.new_with_range(1, 60, 1)
        self._kiosk_reset_row.set_title("Auto-reset after (seconds)")
        self._kiosk_reset_row.set_subtitle("Form clears this many seconds after submission")
        self._kiosk_reset_row.set_value(5)
        self._kiosk_reset_row.connect("notify::value", self._sync_kiosk)
        self.kiosk_group.add(self._kiosk_reset_row)

        self._kiosk_idle_row = Adw.SpinRow.new_with_range(0, 600, 10)
        self._kiosk_idle_row.set_title("Idle timeout (seconds)")
        self._kiosk_idle_row.set_subtitle("Form resets after this long with no interaction; 0 = disabled")
        self._kiosk_idle_row.set_value(60)
        self._kiosk_idle_row.connect("notify::value", self._sync_kiosk)
        self.kiosk_group.add(self._kiosk_idle_row)

        self._kiosk_msg_row = Adw.EntryRow(title="Thank-you message")
        self._kiosk_msg_row.set_text("Thank you!")
        self._kiosk_msg_row.connect("changed", self._sync_kiosk)
        self.kiosk_group.add(self._kiosk_msg_row)

        self._kiosk_enabled_row = Adw.SwitchRow(title="Include kiosk settings in saved JSON")
        self._kiosk_enabled_row.set_subtitle("Off = standard form JSON; On = kiosk config embedded")
        self._kiosk_enabled_row.connect("notify::active", self._sync_kiosk)
        self.kiosk_group.add(self._kiosk_enabled_row)

    def _sync_kiosk(self, *_):
        if self._kiosk_enabled_row.get_active():
            self.model.kiosk = {
                "auto_reset_seconds": int(self._kiosk_reset_row.get_value()),
                "idle_timeout_seconds": int(self._kiosk_idle_row.get_value()),
                "thank_you_message": self._kiosk_msg_row.get_text(),
            }
        else:
            self.model.kiosk = {}
        self._on_model_changed()

    def _load_kiosk_from_dict(self, kiosk: dict):
        if not kiosk:
            return
        self._kiosk_enabled_row.set_active(True)
        self._kiosk_reset_row.set_value(float(kiosk.get("auto_reset_seconds", 5)))
        self._kiosk_idle_row.set_value(float(kiosk.get("idle_timeout_seconds", 60)))
        self._kiosk_msg_row.set_text(kiosk.get("thank_you_message", "Thank you!"))

    @Gtk.Template.Callback()
    def on_add_field_clicked(self, *_):
        dialog = FieldTypeDialog(self._add_field_of_type)
        dialog.present(self.get_root())

    @Gtk.Template.Callback()
    def on_save_clicked(self, *_):
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Save Form Config")

        json_filter = Gtk.FileFilter()
        json_filter.set_name("JSON files")
        json_filter.add_mime_type("application/json")
        json_filter.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(json_filter)
        file_dialog.set_filters(filters)

        if self._save_path:
            # Editing an existing file: open the dialog in the same folder
            # with the same filename pre-filled so one click overwrites it.
            existing = Gio.File.new_for_path(self._save_path)
            file_dialog.set_initial_file(existing)
        else:
            safe_name = (self.model.form_name or "form").lower().replace(" ", "_")
            file_dialog.set_initial_name(safe_name + ".json")

        file_dialog.save(self.get_root(), None, self._on_save_finish)

    def _on_form_name_changed(self, row):
        self.model.form_name = row.get_text()
        # Keep the tab title in sync if we have a page reference
        if hasattr(self, "page") and self.page and hasattr(self.page, "tab_page"):
            title = row.get_text() or "New Form"
            self.page.tab_page.set_title(f"✏ {title}")
        self._on_model_changed()

    def _add_field_of_type(self, ftype: str):
        ff = FormField(type=ftype, label="")
        self.model.fields.append(ff)
        self._append_row(ff, expanded=True)
        self._on_model_changed()

    def _append_row(self, ff: FormField, expanded: bool = False):
        row = FieldEditorRow(
            ff,
            on_delete=self._delete_row,
            on_move_up=self._move_up,
            on_move_down=self._move_down,
            on_changed=self._on_model_changed,
        )
        self._rows.append(row)
        self.fields_group.add(row)
        if expanded:
            row.set_expanded(True)

    def _delete_row(self, row: FieldEditorRow):
        self.model.fields.remove(row.form_field)
        self._rows.remove(row)
        self.fields_group.remove(row)
        self._on_model_changed()

    def _move_up(self, row: FieldEditorRow):
        idx = self._rows.index(row)
        if idx > 0:
            self._swap(idx, idx - 1)

    def _move_down(self, row: FieldEditorRow):
        idx = self._rows.index(row)
        if idx < len(self._rows) - 1:
            self._swap(idx, idx + 1)

    def _swap(self, i: int, j: int):
        # Swap in model
        self.model.fields[i], self.model.fields[j] = (
            self.model.fields[j],
            self.model.fields[i],
        )
        # Swap in row list, then rebuild visual order
        self._rows[i], self._rows[j] = self._rows[j], self._rows[i]
        for r in self._rows:
            self.fields_group.remove(r)
        for r in self._rows:
            self.fields_group.add(r)
        self._on_model_changed()

    @Gtk.Template.Callback()
    def on_preview_toggled(self, btn: Gtk.ToggleButton):
        self._preview_enabled = btn.get_active()
        self.preview_scroll.set_visible(self._preview_enabled)
        self.preview_separator.set_visible(self._preview_enabled)
        if self._preview_enabled:
            self._refresh_preview()

    def _on_model_changed(self):
        if self._preview_enabled:
            self._refresh_preview()

    def _refresh_preview(self):
        from .form_page import FormPage
        fp = FormPage(preview=True)
        fp.load_preview(self.model)
        self.preview_scroll.set_child(fp)

    def _on_save_finish(self, dialog, result):
        try:
            file = dialog.save_finish(result)
        except Exception:
            # User cancelled
            return

        path = file.get_path()
        if not path:
            self._show_toast("Could not determine save path")
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.model.to_json())
        except OSError as e:
            self._show_toast(f"Save failed: {e}")
            return

        self._show_toast(f"Saved to {path}")

        # Update tab title to reflect saved file name
        if hasattr(self, "page") and self.page and hasattr(self.page, "tab_page"):
            self.page.tab_page.set_title(os.path.basename(path))

        self._save_path = path

    @Gtk.Template.Callback()
    def on_back_clicked(self, *_):
        """
        Return to FormConfig with the saved JSON pre-selected.
        The user just needs to pick a CSV and hit Open Form.
        Only reachable after at least one successful Save.
        """
        from .form_config import FormConfig

        self.page.remove(self)

        form_config = FormConfig()
        form_config.set_page(self.page)
        self.page.append(form_config)

        if self._save_path:
            saved_file = Gio.File.new_for_path(self._save_path)
            form_config.preselect_config(saved_file)

            self.page.tab_page.set_title(os.path.basename(self._save_path))

    def _show_toast(self, message: str, timeout: int = 3):
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self.builder_toast_overlay.add_toast(toast)
