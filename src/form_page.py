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

import csv
import os

from gi.repository import Adw, Gtk, Gio

from .utils import show_fatal_toast


@Gtk.Template(resource_path="/in/aryank/openforms/form_page.ui")
class FormPage(Gtk.Box):
    """
    This is the final Form page that appears.
    It is an instance of a GtkBox which will host all the fields.
    This class is responsible for displaying the form and saving
    the result.
    """

    __gtype_name__ = "FormPage"

    form_container: Gtk.Box = Gtk.Template.Child()
    submit_button: Gtk.Button = Gtk.Template.Child()
    form_toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.fields = {}

    def set_page(self, page):
        self.page = page
        self.config = page.form_config
        self._build_form()

    def _build_form(self):
        form_name = self.config.get("form_name", None)
        if form_name:
            if not self.page:
                show_fatal_toast(self.form_toast_overlay)
            self.page.tab_page.set_title(form_name)
        fields_list = self.config.get("fields", None)
        if not fields_list:
            return
        for field in fields_list:
            assert "type" in field
            assert "label" in field
            label = field["label"]
            row, widget = self._create_field(label, field)
            if widget:
                self.fields[field.get("id")] = {"widget": widget, "config": field}
                self.form_container.append(row)
            elif row:
                self.form_container.append(row)

    def _create_field(self, label_text: str, field: dict):
        field_type = field.get("type")

        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        if field.get("required", False):
            label_text = label_text + " *"

        label = Gtk.Label(
            label=label_text,
            halign=Gtk.Align.START,
        )

        if field_type == "label":
            style_list = field.get("style", [])
            for style in style_list:
                label.add_css_class(style)

        if field_type not in ("check", "picture"):
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
            widget.add_css_class("card")
            widget.set_left_margin(6)
            widget.set_top_margin(6)
            widget.set_bottom_margin(6)
            widget.set_right_margin(6)
            widget.remove_css_class("view")
            row.append(widget)
        elif field_type == "label":
            return row, None
        elif field_type == "picture":
            try:
                file = Gio.File.new_for_uri(field.get("uri", None))
                widget = Gtk.Picture()
                widget.set_file(file)
                widget.set_halign(3)
                widget.set_valign(3)
                widget.can_shrink = True
                width = field.get("width", 20)
                height = field.get("height", 20)
                widget.set_size_request(width, height)
                widget.set_content_fit(Gtk.ContentFit.CONTAIN)
                widget.set_margin_top(10)
                widget.set_margin_bottom(10)
                row.append(widget)
                return row, None
            except Exception as _e:
                toast = Adw.Toast(
                    f"Error in opening picture at {field.get('uri', None)}"
                )
                toast.set_timeout(4)
                self.form_toast_overlay.add_toast(toast)
                return None, None

        elif field_type == "calendar":
            widget = Gtk.Calendar()
            widget.remove_css_class("view")
            widget.add_css_class("card")
            row.append(widget)
        elif field_type == "spin":
            if "min" in field and "max" in field and "step" in field:
                widget = Gtk.SpinButton.new_with_range(
                    field["min"], field["max"], field["step"]
                )
            else:
                widget = Gtk.SpinButton()
            row.append(widget)
        else:
            return None, None

        style_list = field.get("style", [])
        for style in style_list:
            label.add_css_class(style)

        return row, widget

    @Gtk.Template.Callback()
    def on_submit_clicked(self, *_):
        data = self._collect_data()
        if not data:
            return
        self._append_to_csv(data)
        self._reset_form()

        toast = Adw.Toast.new("Form data collected")
        toast.set_timeout(1)
        self.form_toast_overlay.add_toast(toast)

    def _collect_data(self) -> dict:
        data = {}

        for field_id, field_dict in self.fields.items():
            widget = field_dict["widget"]
            field_value = None
            if isinstance(widget, Gtk.Entry):
                field_value = widget.get_text()
            elif isinstance(widget, Gtk.TextView):
                text_buffer = widget.get_buffer()
                start_iter = text_buffer.get_start_iter()
                end_iter = text_buffer.get_end_iter()
                field_value = text_buffer.get_text(start_iter, end_iter, True)
            elif isinstance(widget, list):
                for indv_widget in widget:
                    active = indv_widget.get_active()
                    if active:
                        field_value = indv_widget.get_label()
            elif isinstance(widget, Gtk.CheckButton):
                active = widget.get_active()
                field_value = True if active else False
            elif isinstance(widget, Gtk.Calendar):
                date = widget.get_date().format_iso8601()
                field_value = date
            elif isinstance(widget, Gtk.SpinButton):
                field_value = widget.get_value_as_int()
            field_dict_config = field_dict.get("config", None)
            if not field_dict_config:
                show_fatal_toast(self.form_toast_overlay)
            if field_dict_config.get("required", False):
                show_toast = False
                if field_value is None:
                    show_toast = True
                if isinstance(field_value, str) and field_value == "":
                    show_toast = True
                if isinstance(field_value, bool) and not field_value:
                    show_toast = True
                if show_toast:
                    toast = Adw.Toast.new(
                        f"Please fill the required field: {field_dict_config.get('label', 'All')}"
                    )
                    toast.set_timeout(2)
                    self.form_toast_overlay.add_toast(toast)
                    return None
            data[field_id] = field_value

        return data

    def _append_to_csv(self, data: dict):
        if self.page is None:
            show_fatal_toast(self.form_toast_overlay)

        file = self.page.csv_file

        if not file:
            show_fatal_toast(self.form_toast_overlay)

        path = file.get_path()
        if path is None:
            show_fatal_toast(self.form_toast_overlay)
        file_exists = os.path.exists(path)

        try:
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data.keys())

                if not file_exists or os.stat(path).st_size == 0:
                    writer.writeheader()

                writer.writerow(data)
        except Exception as _e:
            show_fatal_toast(self.form_toast_overlay)

    def _reset_form(self):
        for fields_dict in self.fields.values():
            widget = fields_dict["widget"]
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
