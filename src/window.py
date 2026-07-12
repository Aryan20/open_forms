# window.py
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

from gi.repository import Adw, Gtk, Gio
from .page import NewPage


@Gtk.Template(resource_path="/in/aryank/openforms/window.ui")
class OpenFormsWindow(Adw.ApplicationWindow):
    __gtype_name__ = "OpenFormsWindow"

    overview: Adw.TabOverview = Gtk.Template.Child()
    overview_open_button: Gtk.Button = Gtk.Template.Child()
    new_tab_button: Gtk.Button = Gtk.Template.Child()
    tab_view: Adw.TabView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.overview_open_button.connect(
            "clicked", lambda _: self.overview.set_open(True)
        )
        self.new_tab_button.connect("clicked", lambda _: self.add_page())
        self.overview.connect("create-tab", lambda _: self.add_page())
        self.tab_view.connect("create-window", lambda _: self.create_new_window())

        self.add_page()

    def add_page(self):
        page_box = NewPage()
        page = self.tab_view.append(page_box)
        page.set_title("New Form")
        page_box.set_tab_page(page)
        return page

    def open_form_from_history(self, entry: dict):
        """
        Open a new tab pre-filled with a config (and CSV, if it still
        exists) previously used to open a form. Called by HistoryDialog.
        """
        from .history_manager import remove_entry

        config_path = entry.get("config_path")
        if not config_path or not os.path.exists(config_path):
            remove_entry(config_path or "")
            self._show_history_error(
                "That form's config file could no longer be found and was removed from history."
            )
            return

        page_box = NewPage()
        tab_page = self.tab_view.append(page_box)
        page_box.set_tab_page(tab_page)
        tab_page.set_title(entry.get("form_name") or "New Form")

        try:
            page_box.form_config_widget.preselect_config(Gio.File.new_for_path(config_path))
        except Exception:
            remove_entry(config_path)
            self.tab_view.close_page(tab_page)
            self._show_history_error(
                "That form's config file is invalid and was removed from history."
            )
            return

        csv_path = entry.get("csv_path")
        if csv_path and os.path.exists(csv_path):
            page_box.form_config_widget.preselect_csv(Gio.File.new_for_path(csv_path))

        self.tab_view.set_selected_page(tab_page)

    def _show_history_error(self, message: str):
        dialog = Adw.AlertDialog(heading="Couldn't Reopen Form", body=message)
        dialog.add_response("ok", "OK")
        dialog.present(self)

    def create_new_window(self):
        new_window = OpenFormsWindow(application=self.get_application())
        new_window.present()
        return new_window.tab_view
