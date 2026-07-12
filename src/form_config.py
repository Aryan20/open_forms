# form_config.py
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
from gi.repository import Gtk, Gio, GLib

from .form_page import FormPage
from .builder_page import BuilderPage


@Gtk.Template(resource_path="/in/aryank/openforms/form_config.ui")
class FormConfig(Gtk.Box):
    """
    FormConfig is a GtkBox that hosts the buttons used to select
    the form config and csv file alongside the button to generate
    the final form. It is the first screen the user sees.
    """

    __gtype_name__ = "FormConfig"

    open_form_config_btn: Gtk.Button = Gtk.Template.Child()
    open_csv_btn: Gtk.Button = Gtk.Template.Child()
    create_form_btn: Gtk.Button = Gtk.Template.Child()
    new_csv_btn: Gtk.Button = Gtk.Template.Child()
    build_form_btn: Gtk.Button = Gtk.Template.Child()
    edit_in_builder_btn: Gtk.Button = Gtk.Template.Child()
    view_responses_btn: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self.page = None

        self.open_form_config_btn.connect("clicked", self._open_json_config)
        self.open_csv_btn.connect("clicked", self._open_csv)
        self.new_csv_btn.connect("clicked", self._create_new_csv)
        self.build_form_btn.connect("clicked", self._open_builder)
        self.edit_in_builder_btn.connect("clicked", self._edit_in_builder)
        self.view_responses_btn.connect("clicked", self._open_response_viewer)

    def set_page(self, page):
        """
        Set the page instance inside FormConfig to be able to load the
        form inside the page.
        """
        self.page = page

    def _open_file(self, title, suffix, callback):
        dialog = Gtk.FileDialog(title=title)

        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        file_filter = Gtk.FileFilter()
        file_filter.set_name(f"{suffix.upper()} files")
        file_filter.add_suffix(suffix)

        filter_store.append(file_filter)
        dialog.set_filters(filter_store)
        dialog.open(None, None, callback)

    def _create_new_csv(self, *_):
        dialog = Gtk.FileDialog(title="Create New CSV File")

        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        file_filter = Gtk.FileFilter()
        file_filter.set_name("CSV files")
        file_filter.add_suffix("csv")

        filter_store.append(file_filter)
        dialog.set_filters(filter_store)

        dialog.save(None, None, self._on_new_csv_selected)

    def _on_new_csv_selected(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            self.new_csv_btn.set_label(file.get_basename())
            if not self.page:
                return
            self.page.csv_file = file
            self._try_form_open()
        except GLib.Error:
            pass

    def _open_json_config(self, *_):
        self._open_file("Open Form Config", "json", self._on_json_selected)

    def _on_json_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)

            self.page.config_file = file
            self.page.form_config = self._load_config(file)
            self.open_form_config_btn.set_label(file.get_basename())
            self.edit_in_builder_btn.set_sensitive(True)
            self._try_form_open()
        except GLib.Error:
            pass  # cancelled

    def _open_csv(self, *_):
        self._open_file("Open CSV File", "csv", self._on_csv_selected)

    def _on_csv_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            self.open_csv_btn.set_label(file.get_basename())
            self.page.csv_file = file
            self._try_form_open()
        except GLib.Error:
            pass

    def _try_form_open(self):
        if self.page.config_file and self.page.csv_file:
            self.create_form_btn.set_sensitive(True)
            self.view_responses_btn.set_sensitive(True)
            self.create_form_btn.connect(
                "clicked", self._open_form_window, self.page.form_config
            )

    def _load_config(self, file: Gio.File) -> dict:
        path = file.get_path()
        if path is None:
            return {}

        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            raise ValueError("Config root must be an object")

        return config

    def _open_form_window(self, _button, __):
        self.page.remove(self)
        form_page = FormPage()
        form_page.set_page(self.page)
        self.page.append(form_page)

    def preselect_config(self, file: Gio.File):
        """
        Called by BuilderPage after saving to pre-fill the JSON config
        field, so the user only needs to pick a CSV and click Open Form.
        Mirrors what _on_json_selected does but without the file dialog.
        """
        self.page.config_file = file
        self.page.form_config = self._load_config(file)
        self.open_form_config_btn.set_label(file.get_basename())
        self.edit_in_builder_btn.set_sensitive(True)
        self._try_form_open()

    def _open_builder(self, *_):
        self.page.tab_page.set_title("New Form")

        self.page.remove(self)

        builder = BuilderPage()
        builder.set_page(self.page)
        self.page.append(builder)

    def _edit_in_builder(self, *_):
        """
        Open the already-selected JSON config in the builder for editing.
        Parses it into a FormModel, populates the BuilderPage, then swaps
        in the builder exactly like _open_builder does.
        On save the user can overwrite the original file or choose a new path.
        """
        from .form_model import FormModel

        config_file = self.page.config_file
        if not config_file:
            return

        path = config_file.get_path()
        if not path:
            return

        try:
            model = FormModel.from_file(path)
        except Exception as e:
            # Malformed JSON — surface the error via the existing toast pattern
            # by falling back gracefully; the file was already validated by
            # _load_config so this should only happen on disk race conditions.
            print(f"Could not parse config for editing: {e}")
            return

        self.page.tab_page.set_title(f"✏ {model.form_name or config_file.get_basename()}")

        self.page.remove(self)

        builder = BuilderPage()
        builder.set_page(self.page)
        builder.load_from_model(model)
        # Pre-set the save dialog's suggested path to the original file
        # so the user can hit Save and overwrite in one click.
        builder.set_save_path(path)
        self.page.append(builder)

    def _open_response_viewer(self, *_):
        if not self.page or not self.page.csv_file:
            return
        csv_path = self.page.csv_file.get_path()
        if not csv_path:
            return
        from .response_viewer import ResponseViewerDialog
        dialog = ResponseViewerDialog(csv_path)
        dialog.present(self.get_root())
