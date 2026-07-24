# sync_panel.py
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
"""
Per-form sync panel (SYNC_ARCHITECTURE.md §6, adapted). Lets a single form
opt into pushing its responses to Google Sheets or WebDAV, and pick which
sheet/URL it targets. Account-level credentials (OAuth client, Google
connection, WebDAV username/password) are configured once, app-wide, in
sync_settings_dialog.py - not here.
"""

import threading

from gi.repository import Adw, GLib, Gtk

from .sync import BACKEND_LABELS, get_backend, is_backend_configured
from .sync.backend import SyncError
from .sync.google_sheets import extract_gid, extract_spreadsheet_id
from .sync.queue import db_path_for_csv, get_config, init_db, last_log_entry, set_config
from .sync.settings import get_interval
from .sync.worker import SyncWorker
from .utils import root_as_widget

_BACKEND_CHOICES = ["Disabled", BACKEND_LABELS["google_sheets"], BACKEND_LABELS["webdav"]]
_BACKEND_IDS = [None, "google_sheets", "webdav"]


class FormSyncPanel(Adw.Dialog):
    """
    Configures and (re)starts this form's background SyncWorker. `page` is
    the NewPage instance - its `sync_worker` slot holds the worker so it
    survives after this dialog closes, until the tab itself is closed.
    """

    def __init__(self, page):
        super().__init__()
        self._page = page
        self._form_name = (page.form_config or {}).get("form_name", "Form")
        self._csv_path = page.csv_file.get_path()
        self._db_path = db_path_for_csv(self._csv_path)
        init_db(self._db_path)

        self.set_title(f"Sync - {self._form_name}")
        self.set_content_width(420)

        self._build_ui()
        self._load_state()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        page = Adw.PreferencesPage()

        dest_group = Adw.PreferencesGroup(title="Sync This Form")
        page.add(dest_group)

        self._backend_row = Adw.ComboRow(
            title="Push responses to", model=Gtk.StringList.new(_BACKEND_CHOICES)
        )
        self._backend_row.connect("notify::selected", self._on_backend_changed)
        dest_group.add(self._backend_row)

        self._hint_row = Adw.ActionRow(title="Account not configured")
        hint_btn = Gtk.Button(label="Open Sync Settings", valign=Gtk.Align.CENTER)
        hint_btn.connect("clicked", self._on_open_global_settings)
        self._hint_row.add_suffix(hint_btn)
        dest_group.add(self._hint_row)

        self._sheet_id_row = Adw.EntryRow(title="Spreadsheet ID or link")
        self._sheet_id_row.set_show_apply_button(True)
        create_sheet_btn = Gtk.Button(
            icon_name="list-add-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Create a new spreadsheet"
        )
        create_sheet_btn.connect("clicked", self._on_create_sheet_clicked)
        self._sheet_id_row.add_suffix(create_sheet_btn)
        # "apply" only fires on the checkmark; Enter fires "entry-activated"
        self._sheet_id_row.connect("apply", self._on_sheet_id_applied)
        self._sheet_id_row.connect("entry-activated", self._on_sheet_id_applied)
        dest_group.add(self._sheet_id_row)

        self._webdav_url_row = Adw.EntryRow(title="WebDAV URL")
        self._webdav_url_row.connect("apply", self._on_webdav_url_applied)
        self._webdav_url_row.connect("entry-activated", self._on_webdav_url_applied)
        dest_group.add(self._webdav_url_row)

        status_group = Adw.PreferencesGroup(title="Status")
        page.add(status_group)

        self._status_row = Adw.ActionRow(title="Status", subtitle="Not configured")
        self._sync_now_btn = Gtk.Button(label="Sync Now", valign=Gtk.Align.CENTER)
        self._sync_now_btn.connect("clicked", self._on_sync_now_clicked)
        self._status_row.add_suffix(self._sync_now_btn)
        status_group.add(self._status_row)

        toolbar_view.set_content(page)
        self.set_child(toolbar_view)

    # -- State ---------------------------------------------------------------

    def _load_state(self):
        backend_id = get_config(self._db_path, "backend")
        try:
            self._backend_row.set_selected(_BACKEND_IDS.index(backend_id))
        except ValueError:
            self._backend_row.set_selected(0)

        self._sheet_id_row.set_text(get_config(self._db_path, "sheet_id") or "")
        self._webdav_url_row.set_text(get_config(self._db_path, "webdav_url") or "")

        self._update_visibility()
        self._refresh_status_row()

        # A worker may already be running from a previous time this dialog
        # was opened on this page - don't start a second one.
        if self._page.sync_worker is None and backend_id and is_backend_configured(backend_id):
            self._ensure_worker()

    def _selected_backend_id(self):
        return _BACKEND_IDS[self._backend_row.get_selected()]

    def _update_visibility(self):
        backend_id = self._selected_backend_id()
        self._sheet_id_row.set_visible(backend_id == "google_sheets")
        self._webdav_url_row.set_visible(backend_id == "webdav")

        configured = bool(backend_id) and is_backend_configured(backend_id)
        self._hint_row.set_visible(bool(backend_id) and not configured)
        if backend_id == "google_sheets":
            self._hint_row.set_title("Connect your Google account in Sync Settings first")
        elif backend_id == "webdav":
            self._hint_row.set_title("Add WebDAV credentials in Sync Settings first")

    def _refresh_status_row(self):
        entry = last_log_entry(self._db_path)
        if not entry:
            self._status_row.set_subtitle("Not yet synced")
            return
        if entry["status"] == "ok":
            self._status_row.set_subtitle(f"Last synced OK - {entry['timestamp']}")
        else:
            self._status_row.set_subtitle(f"Error: {entry['message']}")

    # -- Backend selection ---------------------------------------------------

    def _on_backend_changed(self, *_):
        backend_id = self._selected_backend_id()
        set_config(self._db_path, "backend", backend_id or "")
        self._update_visibility()

        if not backend_id:
            self._stop_worker()
        elif is_backend_configured(backend_id):
            self._ensure_worker()

    def _on_open_global_settings(self, *_):
        from .sync_settings_dialog import SyncSettingsDialog
        SyncSettingsDialog().present(root_as_widget(self.get_root()))

    # -- Google Sheets --------------------------------------------------------

    def _on_sheet_id_applied(self, *_):
        raw = self._sheet_id_row.get_text().strip()
        if not raw:
            return
        try:
            sheet_id = extract_spreadsheet_id(raw)
        except ValueError:
            self._status_row.set_subtitle(
                "Couldn't find a spreadsheet ID in that link - paste the ID or the sheet's URL"
            )
            return
        gid = extract_gid(raw)
        self._sheet_id_row.set_text(sheet_id)

        if not is_backend_configured("google_sheets"):
            self._status_row.set_subtitle("Connect your Google account in Sync Settings first")
            return

        backend = get_backend("google_sheets", self._form_name)
        self._status_row.set_subtitle("Looking up the sheet's tab…")

        def _link():
            try:
                tab_name = backend.get_sheet_title(sheet_id, gid)
                GLib.idle_add(self._on_sheet_id_linked, backend, sheet_id, tab_name, None)
            except SyncError as e:
                GLib.idle_add(self._on_sheet_id_linked, backend, sheet_id, None, e)

        threading.Thread(target=_link, daemon=True).start()

    def _on_sheet_id_linked(self, backend, sheet_id, tab_name, error):
        if error:
            self._status_row.set_subtitle(f"Error: {error}")
        else:
            backend.link_sheet(self._db_path, sheet_id, tab_name)
            self._status_row.set_subtitle(f'Linked to tab "{tab_name}"')
            self._ensure_worker()
        return GLib.SOURCE_REMOVE

    def _on_create_sheet_clicked(self, *_):
        if not is_backend_configured("google_sheets"):
            self._status_row.set_subtitle("Connect your Google account in Sync Settings first")
            return

        backend = get_backend("google_sheets", self._form_name)
        self._status_row.set_subtitle("Creating spreadsheet…")

        def _create():
            try:
                sheet_id = backend.create_spreadsheet(self._form_name)
                GLib.idle_add(self._on_sheet_created, backend, sheet_id, None)
            except SyncError as e:
                GLib.idle_add(self._on_sheet_created, backend, None, e)

        threading.Thread(target=_create, daemon=True).start()

    def _on_sheet_created(self, backend, sheet_id, error):
        if error:
            self._status_row.set_subtitle(f"Error: {error}")
        else:
            self._sheet_id_row.set_text(sheet_id)
            backend.link_sheet(self._db_path, sheet_id, self._form_name)
            self._status_row.set_subtitle("Spreadsheet created and linked")
            self._ensure_worker()
        return GLib.SOURCE_REMOVE

    # -- WebDAV -----------------------------------------------------------------

    def _on_webdav_url_applied(self, *_):
        url = self._webdav_url_row.get_text().strip()
        if not url:
            return
        backend = get_backend("webdav", self._form_name)
        backend.link(self._db_path, url)
        self._ensure_worker()

    # -- Worker lifecycle ---------------------------------------------------

    def _ensure_worker(self):
        backend_id = self._selected_backend_id()
        if not backend_id or not is_backend_configured(backend_id):
            return
        if self._page.sync_worker is not None:
            if self._page.sync_worker.is_alive():
                self._page.sync_worker.trigger()
                return
            self._page.sync_worker = None  # dead thread, drop it and start fresh below

        backend = get_backend(backend_id, self._form_name)
        worker = SyncWorker(
            backend, self._csv_path, self._db_path, interval=get_interval(), on_status=self._on_worker_status
        )
        self._page.sync_worker = worker
        worker.start()
        worker.trigger()

    def _stop_worker(self):
        if self._page.sync_worker is not None:
            self._page.sync_worker.stop()
            self._page.sync_worker = None

    def _on_sync_now_clicked(self, *_):
        if self._page.sync_worker is None:
            self._ensure_worker()
        else:
            self._page.sync_worker.trigger()
        self._status_row.set_subtitle("Syncing…")

    def _on_worker_status(self, status, message):
        GLib.idle_add(self._apply_worker_status, status, message)

    def _apply_worker_status(self, status, message):
        if status == "ok":
            self._status_row.set_subtitle(message or "Synced")
        else:
            self._status_row.set_subtitle(f"Error: {message}")
        return GLib.SOURCE_REMOVE

