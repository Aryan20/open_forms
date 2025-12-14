# page.py
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
from .form_config import FormConfig

class NewPage(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        form_config = FormConfig()
        form_config.set_page(self)
        self.append(form_config)

        self.config_file = None
        self.csv_file = None
        self.form_config = None

    def set_tab_page(self, tab_page):
        self.tab_page = tab_page
