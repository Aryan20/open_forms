# utils.py
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


from typing import cast

from gi.repository import Adw, Gtk


def root_as_widget(root: Gtk.Root | None) -> Gtk.Widget | None:
    """Every real Gtk.Root is a Widget too, but the stubs don't say so."""
    return cast(Gtk.Widget, root) if root is not None else None


def root_as_window(root: Gtk.Root | None) -> Gtk.Window | None:
    """Every real Gtk.Root here is a Window too, but the stubs don't say so."""
    return cast(Gtk.Window, root) if root is not None else None


def show_fatal_toast(toast_overlay) -> None:
    """Show a fatal error toast when app state is invalid."""
    toast = Adw.Toast(
        title=(
            "Something went wrong.\n"
            "Please reopen the form or restart the application."
        ),
        timeout=6,
    )

    toast.set_priority(Adw.ToastPriority.HIGH)

    toast_overlay.add_toast(toast)
