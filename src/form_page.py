# form_page.py
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

from gi.repository import Adw, Gtk, Gio, GLib
import json
import csv
import os

@Gtk.Template(resource_path="/in/aryank/openforms/form_page.ui")
class FormPage(Gtk.Box):
    __gtype_name__ = "FormPage"

    form_container = Gtk.Template.Child()
    submit_button = Gtk.Template.Child()
    form_toast_overlay = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.fields = {}  # label -> widget

    def set_page(self, page):
        self.page = page
        self.config = page.form_config
        self._build_form()

    def _build_form(self):
        form_name = self.config.get("form_name", None)
        if form_name:
            self.page.tab_page.set_title(form_name)
        fields_list = self.config.get('fields', None)
        if not fields_list:
            return
        for field in fields_list:
            assert "type" in field
            assert "label" in field
            label = field["label"]
            row, widget = self._create_field(label, field)
            if widget:
                self.fields[label] = widget
                self.form_container.append(row)
            elif row:
                self.form_container.append(row)

    def _create_field(self, label_text: str, field: dict):
        field_type = field.get("type")

        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        label = Gtk.Label(
            label=label_text,
            halign=Gtk.Align.START,
        )
        if field_type != "check":
            row.append(label)

        if field_type == "entry":
            widget = Gtk.Entry()
            row.append(widget)
        elif field_type == "check":
            widget = Gtk.CheckButton.new_with_label(label_text)
            row.append(widget)
        elif field_type == "radio":
            options = field.get("options")
            if not options:
                return None, None
            widget = []
            first_radio = None
            for option in options:
                radio_widget = Gtk.CheckButton.new_with_label(option)
                if first_radio:
                    radio_widget.set_group(first_radio)
                else:
                    first_radio = radio_widget
                row.append(radio_widget)
                widget.append(radio_widget)
        elif field_type == "text":
            widget = Gtk.TextView()
            widget.add_css_class('card')
            widget.set_left_margin(6)
            widget.set_top_margin(6)
            widget.set_bottom_margin(6)
            widget.set_right_margin(6)
            widget.remove_css_class('view')
            row.append(widget)
        elif field_type == "label":
            return row, None
        else:
            return None, None

        return row, widget

    @Gtk.Template.Callback()
    def on_submit_clicked(self, *_):
        data = self._collect_data()
        self._append_to_csv(data)
        self._reset_form()

        toast = Adw.Toast.new("Form data collected")
        toast.set_timeout(1)
        self.form_toast_overlay.add_toast(toast)

    def _collect_data(self) -> dict:
        data = {}

        for label, widget in self.fields.items():
            if isinstance(widget, Gtk.Entry):
                data[label] = widget.get_text()
            elif isinstance(widget, Gtk.TextView):
                text_buffer = widget.get_buffer()
                start_iter = text_buffer.get_start_iter()
                end_iter = text_buffer.get_end_iter()
                data[label] = text_buffer.get_text(start_iter, end_iter, True)
            elif isinstance(widget, list):
                for indv_widget in widget:
                    active = indv_widget.get_active()
                    if active:
                        data[label] = indv_widget.get_label()
            elif isinstance(widget, Gtk.CheckButton):
                active = widget.get_active()
                data[label] = True if active else False

            elif isinstance(widget, Gtk.SpinButton):
                data[label] = widget.get_value_as_int()

        return data

    def _append_to_csv(self, data: dict):
        file = self.page.csv_file

        if not file:
            return

        path = file.get_path()
        file_exists = os.path.exists(path)

        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())

            if not file_exists or os.stat(path).st_size == 0:
                writer.writeheader()

            writer.writerow(data)

    def _reset_form(self):
        for widget in self.fields.values():
            if isinstance(widget, Gtk.Entry):
                widget.set_text("")
            elif isinstance(widget, Gtk.TextView):
                text_buffer = widget.get_buffer()
                start_iter = text_buffer.get_start_iter()
                end_iter = text_buffer.get_end_iter()
                text_buffer.delete(start_iter, end_iter)
            elif isinstance(widget, list):
                for indv_widget in widget:
                    indv_widget.set_active(False)
            elif isinstance(widget, Gtk.SpinButton):
                widget.set_value(0)
            elif isinstance(widget, Gtk.CheckButton):
                widget.set_active(False)
