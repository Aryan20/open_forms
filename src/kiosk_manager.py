# kiosk_manager.py
#
# Copyright 2025 Aryan Kaushik
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, GLib


class KioskManager:
    """Fullscreens the form, shows a thank-you screen after submit, and resets on idle."""

    def __init__(self, form_page, kiosk_cfg: dict):
        self._form_page = form_page
        self._cfg = kiosk_cfg
        self._idle_timer_id: int | None = None
        self._progress_timer_id: int | None = None
        self._reset_countdown: int = 0

    def activate(self):
        root = self._form_page.get_root()
        if root:
            root.fullscreen()

        self._build_thankyou_screen()
        self._install_activity_tracking()
        self._restart_idle_timer()

    def deactivate(self):
        self._cancel_timers()
        root = self._form_page.get_root()
        if root:
            root.unfullscreen()

    def _build_thankyou_screen(self):
        box = self._form_page.thankyou_box

        icon = Gtk.Image.new_from_icon_name("checkbox-checked-symbolic")
        icon.set_pixel_size(72)
        icon.set_margin_bottom(12)
        box.append(icon)

        msg = self._cfg.get("thank_you_message", "Thank you!")
        lbl = Gtk.Label(label=msg)
        lbl.add_css_class("title-1")
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_max_width_chars(32)
        box.append(lbl)

        sub = self._cfg.get("auto_reset_seconds", 5)
        self._countdown_label = Gtk.Label()
        self._countdown_label.add_css_class("dim-label")
        self._countdown_label.set_label(f"Next form in {sub}…")
        self._countdown_label.set_margin_top(10)
        box.append(self._countdown_label)

        # print(Gtk.IconTheme.get_icon_names())

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_hexpand(True)
        self._progress_bar.set_margin_top(10)
        self._progress_bar.set_margin_start(48)
        self._progress_bar.set_margin_end(48)
        box.append(self._progress_bar)

    def show_thankyou(self):
        seconds = self._cfg.get("auto_reset_seconds", 5)
        self._reset_countdown = seconds
        self._progress_bar.set_fraction(1.0)
        self._countdown_label.set_label(f"Next form in {seconds}…")

        self._form_page.page_stack.set_visible_child_name("thankyou")
        self._cancel_reset_timer()
        self._progress_timer_id = GLib.timeout_add(500, self._on_progress_tick)

    def _on_progress_tick(self) -> bool:
        self._reset_countdown -= 0.5
        seconds = self._cfg.get("auto_reset_seconds", 5)
        fraction = max(0.0, self._reset_countdown / seconds)
        self._progress_bar.set_fraction(fraction)
        remaining = max(0, int(self._reset_countdown) + 1)
        self._countdown_label.set_label(f"Next form in {remaining}…")

        if self._reset_countdown <= 0:
            self._do_reset()
            self._progress_timer_id = None
            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def _do_reset(self):
        self._form_page._reset_form()
        self._form_page.page_stack.set_visible_child_name("form")
        self._restart_idle_timer()

    def _restart_idle_timer(self):
        self._cancel_idle_timer()
        idle_secs = self._cfg.get("idle_timeout_seconds", 0)
        if idle_secs > 0:
            self._idle_timer_id = GLib.timeout_add_seconds(idle_secs, self._on_idle_timeout)

    def _on_idle_timeout(self) -> bool:
        if self._form_page.page_stack.get_visible_child_name() == "form":
            self._form_page._reset_form()
        self._idle_timer_id = None
        return GLib.SOURCE_REMOVE

    def record_activity(self):
        self._restart_idle_timer()

    def _install_activity_tracking(self):
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda *_: self.record_activity())
        self._form_page.form_container.add_controller(motion)

    def _cancel_idle_timer(self):
        if self._idle_timer_id is not None:
            GLib.source_remove(self._idle_timer_id)
            self._idle_timer_id = None

    def _cancel_reset_timer(self):
        if self._progress_timer_id is not None:
            GLib.source_remove(self._progress_timer_id)
            self._progress_timer_id = None

    def _cancel_timers(self):
        self._cancel_idle_timer()
        self._cancel_reset_timer()
