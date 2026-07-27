# sync_settings_dialog.py
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
App-wide sync settings (Menu -> Sync Settings). Configured once for the
whole app: the Google OAuth client + connected account, and WebDAV
credentials. Per-form choices (whether a form syncs at all, which sheet or
URL it targets) live in each form's own panel — see sync_panel.py.
"""

import threading

from gi.repository import Adw, GLib, Gtk

from .sync import keyring
from .sync.google_sheets import GoogleSheetsBackend
from .sync.settings import get_interval, set_interval
from .sync.webdav import WebDAVBackend


class SyncSettingsDialog(Adw.Dialog):
    """Account-level sync configuration, shared by every form."""

    def __init__(self):
        super().__init__()
        self.set_title("Sync Settings")
        self.set_content_width(440)
        self.set_content_height(520)

        self._build_ui()
        self._load_state()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        page = Adw.PreferencesPage()

        google_group = Adw.PreferencesGroup(
            title="Google Sheets",
            description=(
                "Create an OAuth client (type “Desktop app”) in the Google Cloud "
                "Console and paste its details here. Shared by every form."
            ),
        )
        page.add(google_group)

        self._client_id_row = Adw.EntryRow(title="OAuth Client ID")
        google_group.add(self._client_id_row)

        self._client_secret_row = Adw.PasswordEntryRow(title="OAuth Client Secret")
        google_group.add(self._client_secret_row)

        save_google_row = Adw.ActionRow()
        self._save_google_btn = Gtk.Button(label="Save", valign=Gtk.Align.CENTER)
        self._save_google_btn.add_css_class("suggested-action")
        self._save_google_btn.connect("clicked", self._on_save_google_clicked)
        save_google_row.add_suffix(self._save_google_btn)
        google_group.add(save_google_row)

        self._google_account_row = Adw.ActionRow(title="Google Account", subtitle="Not connected")
        self._google_connect_btn = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER)
        self._google_connect_btn.connect("clicked", self._on_google_connect_clicked)
        self._google_account_row.add_suffix(self._google_connect_btn)
        google_group.add(self._google_account_row)

        webdav_group = Adw.PreferencesGroup(
            title="WebDAV / Nextcloud",
            description="Each form's destination URL is set from that form's own Sync panel.",
        )
        page.add(webdav_group)

        self._webdav_user_row = Adw.EntryRow(title="Username")
        webdav_group.add(self._webdav_user_row)

        self._webdav_pass_row = Adw.PasswordEntryRow(title="Password / App Password")
        webdav_group.add(self._webdav_pass_row)

        self._webdav_status_row = Adw.ActionRow(title="Credentials", subtitle="Not configured")
        self._save_webdav_btn = Gtk.Button(label="Save", valign=Gtk.Align.CENTER)
        self._save_webdav_btn.add_css_class("suggested-action")
        self._save_webdav_btn.connect("clicked", self._on_save_webdav_clicked)
        self._webdav_status_row.add_suffix(self._save_webdav_btn)
        webdav_group.add(self._webdav_status_row)

        behaviour_group = Adw.PreferencesGroup(title="Sync Behaviour")
        page.add(behaviour_group)

        self._interval_row = Adw.SpinRow.new_with_range(10, 3600, 10)
        self._interval_row.set_title("Default sync interval (seconds)")
        self._interval_row.connect("notify::value", self._on_interval_changed)
        behaviour_group.add(self._interval_row)

        toolbar_view.set_content(page)
        self.set_child(toolbar_view)

    # -- State ---------------------------------------------------------------

    def _load_state(self):
        self._client_secret_row.set_text("")
        self._webdav_pass_row.set_text("")
        self._interval_row.set_value(get_interval())
        self._google_account_row.set_subtitle("Loading…")
        self._webdav_status_row.set_subtitle("Loading…")

        def _warm():
            keyring.warm_cache()
            GLib.idle_add(self._finish_load_state)

        threading.Thread(target=_warm, daemon=True).start()

    def _finish_load_state(self):
        self._client_id_row.set_text(GoogleSheetsBackend.get_client_id() or "")
        self._update_secret_placeholder()
        self._refresh_google_status()

        self._webdav_user_row.set_text(WebDAVBackend.get_username() or "")
        self._refresh_webdav_status()
        return GLib.SOURCE_REMOVE

    def _update_secret_placeholder(self):
        if GoogleSheetsBackend.has_client_credentials():
            self._client_secret_row.set_title("OAuth Client Secret (saved — leave blank to keep)")
        else:
            self._client_secret_row.set_title("OAuth Client Secret")

    def _refresh_google_status(self):
        connected = GoogleSheetsBackend.is_connected()
        self._google_account_row.set_subtitle("Connected" if connected else "Not connected")
        self._google_connect_btn.set_label("Disconnect" if connected else "Connect")

    def _refresh_webdav_status(self):
        connected = WebDAVBackend.is_connected()
        self._webdav_status_row.set_subtitle("Credentials saved" if connected else "Not configured")
        if connected:
            self._webdav_pass_row.set_title("Password / App Password (saved — leave blank to keep)")
        else:
            self._webdav_pass_row.set_title("Password / App Password")

    # -- Google Sheets --------------------------------------------------------

    def _on_save_google_clicked(self, *_):
        client_id = self._client_id_row.get_text().strip()
        secret = self._client_secret_row.get_text().strip()
        if not client_id:
            self._google_account_row.set_subtitle("Enter a Client ID first")
            return

        self._save_google_btn.set_sensitive(False)
        self._google_account_row.set_subtitle("Saving…")

        def _save():
            # Keyring calls can block on a portal round trip - keep off the UI thread.
            nonlocal secret
            try:
                if not secret:
                    secret = GoogleSheetsBackend.get_client_secret() or ""
                if not secret:
                    GLib.idle_add(self._on_google_save_done, "Enter a Client Secret first")
                    return
                GoogleSheetsBackend.set_client_credentials(client_id, secret)
                GLib.idle_add(self._on_google_save_done, None)
            except keyring.KeyringUnavailable as e:
                GLib.idle_add(self._on_google_save_done, f"Could not save credentials: {e}")

        threading.Thread(target=_save, daemon=True).start()

    def _on_google_save_done(self, error):
        self._save_google_btn.set_sensitive(True)
        if error:
            self._google_account_row.set_subtitle(error)
        else:
            self._client_secret_row.set_text("")
            self._update_secret_placeholder()
            self._google_account_row.set_subtitle("Client credentials saved")
        return GLib.SOURCE_REMOVE

    def _on_google_connect_clicked(self, *_):
        if GoogleSheetsBackend.is_connected():
            GoogleSheetsBackend.disconnect()
            self._refresh_google_status()
            return

        if not GoogleSheetsBackend.has_client_credentials():
            self._google_account_row.set_subtitle("Save a Client ID/Secret first")
            return

        backend = GoogleSheetsBackend()
        self._google_connect_btn.set_sensitive(False)
        self._google_account_row.set_subtitle("Waiting for authorization in your browser…")

        def on_complete(error):
            GLib.idle_add(self._on_oauth_complete, error)

        backend.start_oauth_flow(on_complete)

    def _on_oauth_complete(self, error):
        self._google_connect_btn.set_sensitive(True)
        if error:
            self._google_account_row.set_subtitle(f"Error: {error}")
        else:
            self._refresh_google_status()
        return GLib.SOURCE_REMOVE

    # -- WebDAV -----------------------------------------------------------------

    def _on_save_webdav_clicked(self, *_):
        username = self._webdav_user_row.get_text().strip()
        password = self._webdav_pass_row.get_text()
        if not username:
            self._webdav_status_row.set_subtitle("Enter a username first")
            return

        self._save_webdav_btn.set_sensitive(False)
        self._webdav_status_row.set_subtitle("Saving…")

        def _save():
            # Keyring calls can block on a portal round trip - keep off the UI thread.
            nonlocal password
            try:
                if not password:
                    if not WebDAVBackend.is_connected():
                        GLib.idle_add(self._on_webdav_save_done, "Enter a password first")
                        return
                    # Leave the saved password untouched — only the username changed.
                    current = keyring.load_token("app", "webdav")
                    password = current["password"] if current else ""
                WebDAVBackend.set_credentials(username, password)
                GLib.idle_add(self._on_webdav_save_done, None)
            except keyring.KeyringUnavailable as e:
                GLib.idle_add(self._on_webdav_save_done, f"Could not save credentials: {e}")

        threading.Thread(target=_save, daemon=True).start()

    def _on_webdav_save_done(self, error):
        self._save_webdav_btn.set_sensitive(True)
        if error:
            self._webdav_status_row.set_subtitle(error)
        else:
            self._webdav_pass_row.set_text("")
            self._refresh_webdav_status()
        return GLib.SOURCE_REMOVE

    # -- Behaviour ------------------------------------------------------------

    def _on_interval_changed(self, *_):
        set_interval(int(self._interval_row.get_value()))
