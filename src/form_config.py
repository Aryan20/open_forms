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

from gi.repository import Gtk, Adw, Gio, GLib
import json

from .form_page import FormPage

@Gtk.Template(resource_path="/in/aryank/openforms/form_config.ui")
class FormConfig(Gtk.Box):
    __gtype_name__ = "FormConfig"

    open_form_config_btn = Gtk.Template.Child()
    open_csv_btn = Gtk.Template.Child()
    create_form_btn = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self.open_form_config_btn.connect(
            "clicked", self._open_json_config
        )
        self.open_csv_btn.connect(
            "clicked", self._open_csv
        )

    def set_page(self, page):
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


    def _open_json_config(self, *_):
        self._open_file(
            "Open Form Config",
            "json",
            self._on_json_selected
        )

    def _on_json_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)

            self.page.config_file = file
            self.page.form_config = self._load_config(file)

            self._try_form_open()
        except GLib.Error:
            pass  # cancelled

    def _open_csv(self, *_):
        self._open_file(
            "Open CSV File",
            "csv",
            self._on_csv_selected
        )

    def _on_csv_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)

            self.page.csv_file = file
            self._try_form_open()
        except GLib.Error:
            pass

    def _try_form_open(self):
        if self.page.config_file and self.page.csv_file:
            self.create_form_btn.set_sensitive(True)
            self.create_form_btn.connect(
                "clicked", self._open_form_window, self.page.form_config
            )


    def _load_config(self, file: Gio.File) -> dict:
        path = file.get_path()

        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            raise ValueError("Config root must be an object")

        return config

    def _open_form_window(self, button, config):
        self.page.remove(self)
        form_page = FormPage()
        form_page.set_page(self.page)
        self.page.append(form_page)

