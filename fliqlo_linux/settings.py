#!/usr/bin/env python3
"""Fliqlo ayarları (libadwaita)."""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from fliqlo_linux import config as cfgmod  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
SERVICE = "fliqlo-daemon.service"


def systemctl(*args):
    try:
        r = subprocess.run(["systemctl", "--user", *args],
                           capture_output=True, text=True, timeout=10)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Fliqlo Ayarları")
        self.set_default_size(980, 560)
        self.cfg = cfgmod.load()
        self._save_src = None

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                        margin_top=12, margin_bottom=18,
                        margin_start=18, margin_end=18)
        columns = Gtk.Box(spacing=18, homogeneous=True)
        outer.append(columns)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(outer)
        toolbar.set_content(scroller)
        self.set_content(toolbar)

        # İki sütun: sol = ekran koruyucu, sağ = görünüm, alt = butonlar
        slots = [columns, columns, outer]

        class _Page:
            @staticmethod
            def add(group):
                group.set_valign(Gtk.Align.START)
                slots.pop(0).append(group)

        page = _Page()

        # --- Ekran koruyucu ---
        g1 = Adw.PreferencesGroup(title="Ekran Koruyucu",
                                  description="Bilgisayar boşta kaldığında saati tam ekran gösterir.")
        page.add(g1)

        self.sw_enabled = Adw.SwitchRow(title="Etkin")
        self.sw_enabled.set_active(self.cfg.enabled)
        self.sw_enabled.connect("notify::active", self._changed)
        g1.add(self.sw_enabled)

        self.sp_idle = Adw.SpinRow.new_with_range(0.5, 240, 0.5)
        self.sp_idle.set_title("Boşta kalma süresi (dakika)")
        self.sp_idle.set_digits(1)
        self.sp_idle.set_value(self.cfg.idle_minutes)
        self.sp_idle.connect("notify::value", self._changed)
        g1.add(self.sp_idle)

        self.sw_inhibit = Adw.SwitchRow(
            title="Video oynarken başlatma",
            subtitle="Uygulamalar boşta kalmayı engellediğinde (video, sunum) saati açma")
        self.sw_inhibit.set_active(self.cfg.respect_inhibit)
        self.sw_inhibit.connect("notify::active", self._changed)
        g1.add(self.sw_inhibit)

        self.sw_lock = Adw.SwitchRow(
            title="Saatten çıkarken ekranı kilitle",
            subtitle="Geri döndüğünüzde kilit ekranı açılır (parola gerekir)")
        self.sw_lock.set_active(self.cfg.lock_on_exit)
        self.sw_lock.connect("notify::active", self._changed)
        g1.add(self.sw_lock)

        self.combo_lock_mode = Adw.ComboRow(
            title="Kilit ekranı tarzı",
            subtitle="macOS tarzında şifre girilmezse kutu kaybolur ve saat oynamaya devam eder")
        model = Gtk.StringList.new(["macOS Tarzı (Entegre Şifre & Geri Çekilme)", "Ubuntu / GNOME Kilit Ekranı"])
        self.combo_lock_mode.set_model(model)
        self.combo_lock_mode.set_selected(0 if self.cfg.lock_mode == "macos" else 1)
        self.combo_lock_mode.set_sensitive(self.cfg.lock_on_exit)
        self.combo_lock_mode.connect("notify::selected", self._changed)
        g1.add(self.combo_lock_mode)

        self.status_row = Adw.ActionRow(title="Servis durumu")
        btn_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)

        self.btn_toggle_service = Gtk.Button(label="Durdur", valign=Gtk.Align.CENTER)
        self.btn_toggle_service.connect("clicked", self._toggle_service)

        self.btn_restart_service = Gtk.Button(label="Yeniden başlat", valign=Gtk.Align.CENTER)
        self.btn_restart_service.connect("clicked", self._restart_service)

        btn_box.append(self.btn_toggle_service)
        btn_box.append(self.btn_restart_service)
        self.status_row.add_suffix(btn_box)
        g1.add(self.status_row)

        # --- Görünüm ---
        g2 = Adw.PreferencesGroup(title="Görünüm")
        page.add(g2)

        self.sw_24h = Adw.SwitchRow(title="24 saat biçimi",
                                    subtitle="Kapalıysa 12 saat (AM/PM)")
        self.sw_24h.set_active(self.cfg.use_24h)
        self.sw_24h.connect("notify::active", self._changed)
        g2.add(self.sw_24h)

        self.sw_sec = Adw.SwitchRow(title="Saniyeyi göster")
        self.sw_sec.set_active(self.cfg.show_seconds)
        self.sw_sec.connect("notify::active", self._changed)
        g2.add(self.sw_sec)

        self.sw_date = Adw.SwitchRow(title="Tarihi göster",
                                     subtitle="Saatin altında gün, ay, yıl")
        self.sw_date.set_active(self.cfg.show_date)
        self.sw_date.connect("notify::active", self._changed)
        g2.add(self.sw_date)

        self.sw_anim = Adw.SwitchRow(title="Çevirme animasyonu")
        self.sw_anim.set_active(self.cfg.animate)
        self.sw_anim.connect("notify::active", self._changed)
        g2.add(self.sw_anim)

        self.sw_all = Adw.SwitchRow(title="Tüm monitörlerde göster")
        self.sw_all.set_active(self.cfg.all_monitors)
        self.sw_all.connect("notify::active", self._changed)
        g2.add(self.sw_all)

        self.sp_bright = Adw.SpinRow.new_with_range(10, 100, 5)
        self.sp_bright.set_title("Parlaklık (%)")
        self.sp_bright.set_value(round(self.cfg.brightness * 100))
        self.sp_bright.connect("notify::value", self._changed)
        g2.add(self.sp_bright)

        self.sp_scale = Adw.SpinRow.new_with_range(50, 100, 5)
        self.sp_scale.set_title("Boyut (%)")
        self.sp_scale.set_value(round(self.cfg.scale * 100))
        self.sp_scale.connect("notify::value", self._changed)
        g2.add(self.sp_scale)

        # --- Önizleme ---
        g3 = Adw.PreferencesGroup()
        page.add(g3)
        box = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        b1 = Gtk.Button(label="Pencerede önizle")
        b1.connect("clicked", lambda *_: self._launch(["--preview"]))
        b2 = Gtk.Button(label="Şimdi başlat")
        b2.add_css_class("suggested-action")
        b2.connect("clicked", lambda *_: self._launch([]))
        box.append(b1)
        box.append(b2)
        g3.add(box)

        self._refresh_status()
        GLib.timeout_add_seconds(3, self._refresh_status)

    def _changed(self, *_):
        # Hızlı değişikliklerde diske tek seferde yaz
        if self._save_src is not None:
            GLib.source_remove(self._save_src)
        self._save_src = GLib.timeout_add(250, self._save)

    def _save(self):
        self._save_src = None
        c = self.cfg
        c.enabled = self.sw_enabled.get_active()
        c.idle_minutes = self.sp_idle.get_value()
        c.respect_inhibit = self.sw_inhibit.get_active()
        c.lock_on_exit = self.sw_lock.get_active()
        self.combo_lock_mode.set_sensitive(c.lock_on_exit)
        c.lock_mode = "macos" if self.combo_lock_mode.get_selected() == 0 else "gnome"
        c.use_24h = self.sw_24h.get_active()
        c.show_seconds = self.sw_sec.get_active()
        c.show_date = self.sw_date.get_active()
        c.animate = self.sw_anim.get_active()
        c.all_monitors = self.sw_all.get_active()
        c.brightness = self.sp_bright.get_value() / 100.0
        c.scale = self.sp_scale.get_value() / 100.0
        try:
            cfgmod.save(c)
        except OSError as e:
            self.status_row.set_subtitle(f"Ayarlar kaydedilemedi: {e}")
        return GLib.SOURCE_REMOVE

    def flush(self):
        if self._save_src is not None:
            GLib.source_remove(self._save_src)
            self._save()

    def _launch(self, extra):
        self.flush()
        args = [sys.executable, os.path.join(HERE, "clock.py"), *extra]
        try:
            Gio.Subprocess.new(args, Gio.SubprocessFlags.NONE)
        except GLib.Error as e:
            self.status_row.set_subtitle(f"Başlatılamadı: {e.message}")

    def _refresh_status(self):
        rc, out = systemctl("is-active", SERVICE)
        if out == "active":
            self.status_row.set_subtitle("Çalışıyor ✓")
            self.btn_toggle_service.set_label("Durdur")
            self.btn_toggle_service.remove_css_class("suggested-action")
            self.btn_toggle_service.add_css_class("destructive-action")
            self.btn_restart_service.set_sensitive(True)
        else:
            self.status_row.set_subtitle(f"Durduruldu ({out})" if out else "Durduruldu")
            self.btn_toggle_service.set_label("Başlat")
            self.btn_toggle_service.remove_css_class("destructive-action")
            self.btn_toggle_service.add_css_class("suggested-action")
            self.btn_restart_service.set_sensitive(False)
        return GLib.SOURCE_CONTINUE

    def _toggle_service(self, *_):
        self.flush()
        rc, out = systemctl("is-active", SERVICE)
        if out == "active":
            systemctl("stop", SERVICE)
        else:
            # Fliqlo başlatıldığında Aerial durdurulur (çakışmayı önler)
            systemctl("stop", "aerial-daemon.service")
            systemctl("start", SERVICE)
        self._refresh_status()

    def _restart_service(self, *_):
        self.flush()
        systemctl("restart", SERVICE)
        self._refresh_status()


class SettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.fliqlo_linux.Settings")

    def do_activate(self):
        win = self.get_active_window()
        if win is None:
            win = SettingsWindow(self)
            win.connect("close-request", lambda w: (w.flush(), False)[1])
        win.present()


if __name__ == "__main__":
    sys.exit(SettingsApp().run(sys.argv))
