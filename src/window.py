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

from gi.repository import Adw, Gtk
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

    def create_new_window(self):
        new_window = OpenFormsWindow(application=self.get_application())
        new_window.present()
        return new_window.tab_view
