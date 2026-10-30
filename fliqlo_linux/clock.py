#!/usr/bin/env python3
"""Fliqlo tarzı flip saat — GTK4, Wayland uyumlu.

Kullanım:
    clock.py              # ekran koruyucu modu (tam ekran, hareket/tuş ile çıkar)
    clock.py --preview    # pencere modunda önizleme (Esc/Q çıkar, F tam ekran)
"""

import argparse
import math
import os
import signal
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, PangoCairo  # noqa: E402
import cairo  # noqa: E402

from fliqlo_linux import auth  # noqa: E402
from fliqlo_linux import config as cfgmod  # noqa: E402
from fliqlo_linux.compat import unix_signal_add  # noqa: E402

APP_ID = "io.github.fliqlo_linux.Clock"

FONT_FAMILIES = "Helvetica Neue,Helvetica,Inter,Ubuntu Sans,Ubuntu,DejaVu Sans"
BG = (0.0, 0.0, 0.0)
CARD = (0.071, 0.071, 0.071)
DIGIT = (0.718, 0.718, 0.718)
FLIP_DURATION = 0.6          # saniye
GRACE_SECONDS = 1.0          # açılıştan sonra girişleri yok sayma süresi
MOTION_THRESHOLD = 12.0      # piksel; bundan az fare titremesi çıkışa sebep olmaz


def rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Card:
    """Tek bir flip kartının durumu (ör. saat veya dakika)."""

    def __init__(self, key):
        self.cur = key
        self.prev = None
        self.start = 0.0

    def set(self, key, now, animate):
        if key == self.cur:
            return False
        self.prev = self.cur if animate else None
        self.cur = key
        self.start = now
        return animate

    def progress(self, now):
        if self.prev is None:
            return None
        p = (now - self.start) / FLIP_DURATION
        if p >= 1.0:
            self.prev = None
            return None
        return max(0.0, p)


class ClockView(Gtk.DrawingArea):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.cards = []
        self._cache = {}
        self._cache_geom = None
        self._tick_id = None
        self._timer_id = None
        self._update_time(initial=True)
        self.set_draw_func(self._draw)
        self.connect("unrealize", self._on_unrealize)
        self._schedule_next_second()

    # ---------- zaman ----------
    def _keys(self):
        t = time.localtime()
        if self.cfg.use_24h:
            hour = (f"{t.tm_hour:02d}", "")
        else:
            h12 = t.tm_hour % 12 or 12
            hour = (str(h12), "PM" if t.tm_hour >= 12 else "AM")
        keys = [hour, (f"{t.tm_min:02d}", "")]
        if self.cfg.show_seconds:
            keys.append((f"{t.tm_sec:02d}", ""))
        return keys

    def _update_time(self, initial=False):
        keys = self._keys()
        now = time.monotonic()
        if initial or len(keys) != len(self.cards):
            self.cards = [Card(k) for k in keys]
            self.queue_draw()
            return
        animating = False
        changed = False
        for card, key in zip(self.cards, keys):
            if card.cur != key:
                changed = True
                animating |= card.set(key, now, self.cfg.animate)
        if animating:
            self._ensure_tick()
        elif changed:
            self.queue_draw()

    def _schedule_next_second(self):
        # Bir sonraki saniye sınırına hizalı zamanlayıcı (kayma olmaz)
        frac = time.time() % 1.0
        delay = int((1.0 - frac) * 1000) + 5
        self._timer_id = GLib.timeout_add(delay, self._on_second)

    def _on_second(self):
        self._timer_id = None
        self._update_time()
        self._schedule_next_second()
        return GLib.SOURCE_REMOVE

    def _ensure_tick(self):
        if self._tick_id is None:
            self._tick_id = self.add_tick_callback(self._on_tick)
        self.queue_draw()

    def _on_tick(self, _widget, _clock):
        self.queue_draw()
        now = time.monotonic()
        if any(c.progress(now) is not None for c in self.cards):
            return GLib.SOURCE_CONTINUE
        self._tick_id = None
        return GLib.SOURCE_REMOVE

    def _on_unrealize(self, *_):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    # ---------- çizim ----------
    def _scale_factor(self):
        native = self.get_native()
        surface = native.get_surface() if native else None
        if surface is not None and hasattr(surface, "get_scale"):
            try:
                return max(1.0, float(surface.get_scale()))
            except Exception:
                pass
        return float(max(1, self.get_scale_factor()))

    def _geometry(self, w, h):
        n = len(self.cards)
        gap_ratio = 0.06
        s = self.cfg.scale
        h_max = h * 0.74 * s if self.cfg.show_date else h * 0.80 * s
        cw = min(w * 0.92 * s / (n + gap_ratio * (n - 1)), h_max)
        cw = max(1.0, math.floor(cw))
        ch = cw
        gap = math.floor(cw * gap_ratio)
        total = n * cw + (n - 1) * gap

        date_font_size = max(12, math.floor(ch * 0.045))
        date_gap = math.floor(ch * 0.05)
        date_h = math.floor(date_font_size * 2.3) if self.cfg.show_date else 0
        total_h = ch + (date_gap + date_h if self.cfg.show_date else 0)

        x0 = math.floor((w - total) / 2)
        y0 = math.floor((h - total_h) / 2)
        return cw, ch, gap, x0, y0

    def _card_surface(self, key, cw, ch, scale):
        geom = (cw, ch, scale)
        if self._cache_geom != geom:
            self._cache.clear()
            self._cache_geom = geom
        surf = self._cache.get(key)
        if surf is not None:
            return surf
        if len(self._cache) > 64:
            self._cache.clear()

        pw, ph = max(1, math.ceil(cw * scale)), max(1, math.ceil(ch * scale))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, pw, ph)
        surf.set_device_scale(scale, scale)
        cr = cairo.Context(surf)

        rounded_rect(cr, 0, 0, cw, ch, cw * 0.055)
        cr.set_source_rgb(*CARD)
        cr.fill()

        text, sub = key
        layout = PangoCairo.create_layout(cr)
        fd = Pango.FontDescription.from_string(FONT_FAMILIES)
        fd.set_weight(Pango.Weight.BOLD)
        fd.set_absolute_size(ch * 0.72 * Pango.SCALE)
        layout.set_font_description(fd)
        try:
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_font_features_new("tnum=1"))
            layout.set_attributes(attrs)
        except Exception:
            pass

        # Dikey hizalama için sabit referans ("0") -> tüm rakamlar aynı hizada
        layout.set_text("0", -1)
        ref_ink, _ = layout.get_pixel_extents()
        layout.set_text(text, -1)
        _ink, logical = layout.get_pixel_extents()
        x = (cw - logical.width) / 2 - logical.x
        y = (ch - ref_ink.height) / 2 - ref_ink.y
        cr.move_to(x, y)
        cr.set_source_rgb(*DIGIT)
        PangoCairo.show_layout(cr, layout)

        if sub:
            sl = PangoCairo.create_layout(cr)
            sfd = Pango.FontDescription.from_string(FONT_FAMILIES)
            sfd.set_weight(Pango.Weight.BOLD)
            sfd.set_absolute_size(ch * 0.075 * Pango.SCALE)
            sl.set_font_description(sfd)
            sl.set_text(sub, -1)
            cr.move_to(cw * 0.06, ch * 0.05)
            PangoCairo.show_layout(cr, sl)

        surf.flush()
        self._cache[key] = surf
        return surf

    @staticmethod
    def _half(cr, surf, x, y, cw, ch, top, sy=1.0, shade=0.0):
        if sy < 0.005:
            return
        mid = y + ch / 2
        cr.save()
        if sy != 1.0:
            cr.translate(0, mid)
            cr.scale(1, sy)
            cr.translate(0, -mid)
        if top:
            cr.rectangle(x, y, cw, ch / 2)
        else:
            cr.rectangle(x, mid, cw, ch / 2)
        cr.clip()
        cr.set_source_surface(surf, x, y)
        cr.paint()
        if shade > 0:
            cr.set_source_rgba(0, 0, 0, min(1.0, shade))
            cr.paint()
        cr.restore()

    def _draw(self, _area, cr, w, h):
        cr.set_source_rgb(*BG)
        cr.paint()
        if w < 4 or h < 4 or not self.cards:
            return
        scale = self._scale_factor()
        cw, ch, gap, x0, y0 = self._geometry(w, h)
        now = time.monotonic()
        line = max(1.0, round(ch * 0.012 * scale) / scale)

        for i, card in enumerate(self.cards):
            x = x0 + i * (cw + gap)
            y = y0
            new = self._card_surface(card.cur, cw, ch, scale)
            p = card.progress(now)
            if p is None:
                cr.set_source_surface(new, x, y)
                cr.paint()
            else:
                old = self._card_surface(card.prev, cw, ch, scale)
                self._half(cr, new, x, y, cw, ch, top=True)
                if p < 0.5:
                    s = math.cos(p * math.pi)            # 1 -> 0
                    self._half(cr, old, x, y, cw, ch, top=False,
                               shade=(1 - s) * 0.25)
                    self._half(cr, old, x, y, cw, ch, top=True, sy=s,
                               shade=(1 - s) * 0.6)
                else:
                    s = -math.cos(p * math.pi)           # 0 -> 1
                    self._half(cr, old, x, y, cw, ch, top=False,
                               shade=s * 0.25)
                    self._half(cr, new, x, y, cw, ch, top=False, sy=s,
                               shade=(1 - s) * 0.6)
            # Kartı ortadan bölen siyah çizgi
            cr.set_source_rgb(*BG)
            cr.rectangle(x, y + ch / 2 - line / 2, cw, line)
            cr.fill()

        if self.cfg.show_date:
            day_str = time.strftime("%A")
            date_str = time.strftime("%B %-d %Y")
            date_font_size = max(12, math.floor(ch * 0.045))
            date_gap = math.floor(ch * 0.05)

            layout_day = PangoCairo.create_layout(cr)
            fd_day = Pango.FontDescription.from_string(FONT_FAMILIES)
            fd_day.set_weight(Pango.Weight.NORMAL)
            fd_day.set_absolute_size(date_font_size * 0.85 * Pango.SCALE)
            layout_day.set_font_description(fd_day)
            layout_day.set_text(day_str, -1)
            _ink, logical_day = layout_day.get_pixel_extents()

            layout_date = PangoCairo.create_layout(cr)
            fd_date = Pango.FontDescription.from_string(FONT_FAMILIES)
            fd_date.set_weight(Pango.Weight.BOLD)
            fd_date.set_absolute_size(date_font_size * 1.1 * Pango.SCALE)
            layout_date.set_font_description(fd_date)
            layout_date.set_text(date_str, -1)
            _ink, logical_date = layout_date.get_pixel_extents()

            y_day = y0 + ch + date_gap
            x_day = (w - logical_day.width) / 2 - logical_day.x
            cr.move_to(x_day, y_day)
            cr.set_source_rgba(0.65, 0.65, 0.65, 0.85)
            PangoCairo.show_layout(cr, layout_day)

            y_date = y_day + logical_day.height + 4
            x_date = (w - logical_date.width) / 2 - logical_date.x
            cr.move_to(x_date, y_date)
            cr.set_source_rgba(0.90, 0.90, 0.90, 0.95)
            PangoCairo.show_layout(cr, layout_date)

        if self.cfg.brightness < 1.0:
            cr.set_source_rgba(0, 0, 0, 1.0 - self.cfg.brightness)
            cr.paint()


class LockOverlay(Gtk.Box):
    def __init__(self, on_success_cb, on_dismiss_cb, timeout_seconds=20):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.on_success = on_success_cb
        self.on_dismiss = on_dismiss_cb
        self.timeout_seconds = timeout_seconds
        self.user, self.full_name, self.avatar_path = auth.get_user_info()

        self.add_css_class("macos-lock-card")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        # Avatar
        self.avatar_area = Gtk.DrawingArea()
        self.avatar_area.set_content_width(84)
        self.avatar_area.set_content_height(84)
        self.avatar_area.set_halign(Gtk.Align.CENTER)
        self.avatar_area.set_draw_func(self._draw_avatar)
        self.append(self.avatar_area)

        # Full Name
        lbl_name = Gtk.Label(label=self.full_name)
        lbl_name.add_css_class("macos-lock-name")
        self.append(lbl_name)

        # Input Box
        box_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box_input.set_halign(Gtk.Align.CENTER)

        self.entry = Gtk.PasswordEntry(placeholder_text="Parola")
        self.entry.set_show_peek_icon(True)
        self.entry.add_css_class("macos-lock-entry")
        self.entry.connect("activate", self._on_submit)
        box_input.append(self.entry)

        btn_submit = Gtk.Button(icon_name="go-next-symbolic")
        btn_submit.add_css_class("macos-lock-btn")
        btn_submit.connect("clicked", self._on_submit)
        box_input.append(btn_submit)

        self.append(box_input)

        # Error label
        self.lbl_error = Gtk.Label(label="")
        self.lbl_error.add_css_class("macos-lock-error")
        self.lbl_error.set_visible(False)
        self.append(self.lbl_error)

        self.avatar_texture = None
        if self.avatar_path:
            try:
                f = Gio.File.new_for_path(self.avatar_path)
                self.avatar_texture = Gdk.Texture.new_from_file(f)
            except Exception:
                pass

        self._timer_id = None
        self._failed_count = 0

    def _draw_avatar(self, area, cr, w, h):
        r = min(w, h) / 2
        cr.arc(w / 2, h / 2, r, 0, 2 * math.pi)
        cr.clip()

        if self.avatar_texture:
            tw = self.avatar_texture.get_width()
            th = self.avatar_texture.get_height()
            s = max(w / tw, h / th)
            cr.save()
            cr.translate((w - tw * s) / 2, (h - th * s) / 2)
            cr.scale(s, s)
            Gdk.cairo_set_source_pixbuf(cr, Gdk.pixbuf_get_from_texture(self.avatar_texture), 0, 0)
            cr.paint()
            cr.restore()
        else:
            cr.set_source_rgb(0.2, 0.2, 0.24)
            cr.paint()
            cr.set_source_rgb(0.8, 0.8, 0.8)
            cr.arc(w / 2, h / 2 - 8, r * 0.4, 0, 2 * math.pi)
            cr.fill()
            cr.arc(w / 2, h + 8, r * 0.7, 0, 2 * math.pi)
            cr.fill()

    def reset_timeout(self, seconds=None):
        if seconds is None:
            seconds = self.timeout_seconds
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._timer_id = GLib.timeout_add_seconds(seconds, self._on_timeout)

    def _on_timeout(self):
        self._timer_id = None
        self.dismiss()
        return GLib.SOURCE_REMOVE

    def show_prompt(self):
        self.lbl_error.set_visible(False)
        self.entry.set_text("")
        self.entry.set_sensitive(True)
        self.set_visible(True)
        self.reset_timeout()
        self.entry.grab_focus()

    def dismiss(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self.set_visible(False)
        self.entry.set_text("")
        self.lbl_error.set_visible(False)
        if self.on_dismiss:
            self.on_dismiss()

    def _on_submit(self, *_):
        pwd_text = self.entry.get_text()
        if not pwd_text:
            return

        self.entry.set_sensitive(False)
        self.lbl_error.set_text("Doğrulanıyor...")
        self.lbl_error.set_visible(True)

        def worker():
            ok = auth.pam_verify_password(self.user, pwd_text)
            GLib.idle_add(self._on_auth_result, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _on_auth_result(self, ok):
        self.entry.set_sensitive(True)
        if ok:
            self.lbl_error.set_visible(False)
            if self._timer_id is not None:
                GLib.source_remove(self._timer_id)
                self._timer_id = None
            self.on_success()
        else:
            self._failed_count += 1
            if self._failed_count >= 5:
                if self.on_dismiss:
                    self.on_dismiss(fallback_lock=True)
                return GLib.SOURCE_REMOVE

            self.lbl_error.set_text("Hatalı parola")
            self.lbl_error.set_visible(True)
            self.entry.set_text("")
            self.entry.grab_focus()
            self._shake()
            self.reset_timeout(15)
        return GLib.SOURCE_REMOVE

    def _shake(self):
        offsets = [-10, 10, -8, 8, -4, 4, -2, 2, 0]
        def step(idx=0):
            if idx < len(offsets):
                off = offsets[idx]
                self.set_margin_start(max(0, off))
                self.set_margin_end(max(0, -off))
                GLib.timeout_add(35, lambda: step(idx + 1))
            else:
                self.set_margin_start(0)
                self.set_margin_end(0)
            return GLib.SOURCE_REMOVE
        step(0)


class ClockWindow(Gtk.ApplicationWindow):
    def __init__(self, app, cfg, monitor=None, preview=False):
        super().__init__(application=app, title="Fliqlo")
        self.app = app
        self.cfg = cfg
        self.preview = preview
        self.add_css_class("fliqlo")

        self.view = ClockView(cfg)
        self.overlay = Gtk.Overlay()
        self.overlay.set_child(self.view)
        self.set_child(self.overlay)
        self._origin = None

        self.lock_card = None
        if not preview and cfg.lock_on_exit and cfg.lock_mode == "macos":
            self.lock_card = LockOverlay(
                on_success_cb=self._on_auth_success,
                on_dismiss_cb=self._on_auth_dismiss,
                timeout_seconds=cfg.lock_timeout
            )
            self.overlay.add_overlay(self.lock_card)
            self.lock_card.set_visible(False)
            self.connect("notify::is-active", self._on_active_changed)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        if not preview:
            motion = Gtk.EventControllerMotion()
            motion.connect("motion", self._on_motion)
            self.add_controller(motion)
            scroll = Gtk.EventControllerScroll.new(
                Gtk.EventControllerScrollFlags.BOTH_AXES)
            scroll.connect("scroll", self._on_scroll)
            self.add_controller(scroll)
            self.set_decorated(False)
            self.set_cursor(Gdk.Cursor.new_from_name("none", None))
            if monitor is not None:
                self.fullscreen_on_monitor(monitor)
            else:
                self.fullscreen()
        else:
            self.set_default_size(960, 540)

    def _is_card_active(self):
        return self.lock_card is not None and self.lock_card.get_visible()

    def show_lock(self):
        if self.lock_card is not None:
            self.present()
            self.set_cursor(Gdk.Cursor.new_from_name("default", None))
            self.lock_card.show_prompt()
            self.set_focus(self.lock_card.entry)
            self.lock_card.entry.grab_focus()

    def hide_lock(self):
        if self.lock_card is not None and self.lock_card.get_visible():
            self.lock_card.dismiss()
            self.set_cursor(Gdk.Cursor.new_from_name("none", None))

    def _on_auth_success(self):
        self.app.unlock_and_exit()

    def _on_auth_dismiss(self, fallback_lock=False):
        self.set_cursor(Gdk.Cursor.new_from_name("none", None))
        self._origin = None
        if fallback_lock:
            self.app.fallback_lock()

    def _on_active_changed(self, w, _pspec):
        if not w.get_property("is-active"):
            GLib.timeout_add(300, self._check_external_focus_loss)

    def _check_external_focus_loss(self):
        if self.app._quitting or not self.app.past_grace():
            return GLib.SOURCE_REMOVE
        if self.preview or not self.cfg.lock_on_exit or self.cfg.lock_mode != "macos":
            return GLib.SOURCE_REMOVE
        # Alt+Tab ile masaüstü pencerelerine kaçıldıysa ekranı hemen kilitle
        if not any(win.get_property("is-active") for win in self.app.windows):
            print("[fliqlo-watchdog] Odak kaybedildi (Alt+Tab vb.), GNOME kilidi devreye giriyor...", file=sys.stderr)
            self.app.fallback_lock()
        return GLib.SOURCE_REMOVE

    # ---- giriş olayları ----
    def _on_key(self, _ctrl, keyval, _code, _state):
        if self.preview:
            if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
                self.app.quit()
            elif keyval in (Gdk.KEY_f, Gdk.KEY_F, Gdk.KEY_F11):
                if self.is_fullscreen():
                    self.unfullscreen()
                else:
                    self.fullscreen()
            return True

        if self._is_card_active():
            if keyval == Gdk.KEY_Escape:
                self.hide_lock()
                return True
            self.lock_card.reset_timeout()
            return False

        # Çoklu monitör: diğer ekranda açıksa orayı kapat
        other_active = next((w for w in self.app.windows if w != self and w._is_card_active()), None)
        if other_active:
            other_active.hide_lock()

        self.app.user_activity(self)

        # Uyanma tuşu yazılabilir bir karakter/rakam ise ilk karakteri doğrudan kutuya aktar
        ch = Gdk.keyval_to_unicode(keyval)
        if ch and chr(ch).isprintable():
            char_str = chr(ch)
            if self.lock_card and self.lock_card.entry:
                self.lock_card.entry.set_text(char_str)
                self.lock_card.entry.set_position(-1)
        return True

    def _on_click(self, *_):
        if self.preview:
            return
        if self._is_card_active():
            self.lock_card.reset_timeout()
            return
        self.app.user_activity(self)

    def _on_scroll(self, *_):
        if self.preview:
            return
        if self._is_card_active():
            self.lock_card.reset_timeout()
            return True
        self.app.user_activity(self)
        return True

    def _on_motion(self, _ctrl, x, y):
        if self._is_card_active():
            self.lock_card.reset_timeout()
            return

        # Çoklu monitör: Fare diğer ekrandan bu ekrana geldiyse kilit kutusunu bu ekrana taşı
        other_active = next((w for w in self.app.windows if w != self and w._is_card_active()), None)
        if other_active:
            other_active.hide_lock()
            self.show_lock()
            return

        if not self.app.past_grace():
            self._origin = (x, y)
            return
        if self._origin is None:
            self._origin = (x, y)
            return
        dx, dy = x - self._origin[0], y - self._origin[1]
        if math.hypot(dx, dy) > MOTION_THRESHOLD:
            self.app.user_activity(self)


class ClockApp(Gtk.Application):
    def __init__(self, args):
        flags = Gio.ApplicationFlags.NON_UNIQUE if args.preview else Gio.ApplicationFlags.DEFAULT_FLAGS
        super().__init__(application_id=APP_ID, flags=flags)
        self.args = args
        self.cfg = cfgmod.load()
        if args.h24:
            self.cfg.use_24h = True
        if args.h12:
            self.cfg.use_24h = False
        if args.seconds:
            self.cfg.show_seconds = True
        if getattr(args, "date", False):
            self.cfg.show_date = True
        if getattr(args, "no_date", False):
            self.cfg.show_date = False
        self.started = 0.0
        self.windows = []
        self._quitting = False
        self._rebuild_pending = False

    def past_grace(self):
        return time.monotonic() - self.started > GRACE_SECONDS

    def user_activity(self, source_window=None):
        if not self.past_grace() or self._quitting:
            return

        if not self.cfg.lock_on_exit or self.args.no_lock or self.args.preview:
            self._quitting = True
            self.quit()
            return

        if self.cfg.lock_mode == "macos":
            win = source_window or (self.windows[0] if self.windows else None)
            if win and hasattr(win, "show_lock"):
                win.show_lock()
            return

        self._quitting = True
        self._lock_then_quit()

    def unlock_and_exit(self):
        """macOS tarzı şifre doğru girilince kilit ekranına atmadan masaüstünü açar."""
        self._quitting = True
        self.quit()

    def fallback_lock(self):
        """Çok sayıda hatalı deneme olursa sistem güvenliği için GNOME'u kilitler."""
        self._quitting = True
        self._lock_then_quit()

    def _lock_then_quit(self):
        """Saat ekrandayken kilidi iste; kilit ekranı gelince kapan.
        Böylece masaüstü bir an bile görünmez."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.signal_subscribe(
                "org.gnome.ScreenSaver", "org.gnome.ScreenSaver", "ActiveChanged",
                "/org/gnome/ScreenSaver", None, Gio.DBusSignalFlags.NONE,
                lambda *a: a[-1].unpack()[0] and self.quit())
            bus.call(
                "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver", "Lock", None, None,
                Gio.DBusCallFlags.NONE, 5000, None, self._on_lock_reply)
        except GLib.Error as e:
            print("Kilitleme başarısız:", e.message, file=sys.stderr)
            self._lock_fallback()
        # Ne olursa olsun takılı kalma
        GLib.timeout_add(2500, lambda: (self.quit(), False)[1])

    def _on_lock_reply(self, bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error as e:
            print("Kilitleme başarısız:", e.message, file=sys.stderr)
            self._lock_fallback()

    def _lock_fallback(self):
        try:
            Gio.Subprocess.new(["loginctl", "lock-session"], Gio.SubprocessFlags.NONE)
        except GLib.Error:
            pass

    def do_startup(self):
        Gtk.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_string("""
window.fliqlo {
    background-color: black;
}

.macos-lock-card {
    background-color: rgba(28, 28, 32, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 28px;
    padding: 30px 40px;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.85);
    min-width: 290px;
}

.macos-lock-name {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
    margin-top: 6px;
    margin-bottom: 10px;
}

.macos-lock-entry {
    background-color: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 22px;
    color: #ffffff;
    padding: 7px 16px;
    font-size: 15px;
    min-width: 210px;
}

.macos-lock-entry:focus {
    border-color: rgba(0, 122, 255, 0.85);
    background-color: rgba(255, 255, 255, 0.18);
    box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.35);
}

.macos-lock-btn {
    background-color: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 22px;
    color: #ffffff;
    padding: 7px 12px;
}

.macos-lock-btn:hover {
    background-color: rgba(255, 255, 255, 0.32);
}

.macos-lock-error {
    font-size: 13px;
    font-weight: bold;
    color: #ff453a;
    margin-top: 6px;
}
""")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            unix_signal_add(sig, self._on_signal)

    def _on_signal(self):
        if self.cfg.lock_on_exit and not self.args.preview and not self.args.no_lock:
            self._lock_fallback()
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_activate(self):
        if self.windows:
            for w in self.windows:
                w.present()
            return
        self.started = time.monotonic()
        try:
            if self.args.preview:
                win = ClockWindow(self, self.cfg, preview=True)
                self.windows.append(win)
                win.present()
                return
            display = Gdk.Display.get_default()
            monitors = display.get_monitors()
            monitors.connect("items-changed", self._on_monitors_changed)
            self._build_windows()
        except Exception as e:
            print(f"do_activate error: {e}", file=sys.stderr)
            self.quit()

    def _build_windows(self):
        for w in self.windows:
            w.destroy()
        self.windows = []
        monitors = Gdk.Display.get_default().get_monitors()
        targets = [monitors.get_item(i) for i in range(monitors.get_n_items())]
        if not self.cfg.all_monitors or not targets:
            targets = targets[:1] or [None]
        for mon in targets:
            win = ClockWindow(self, self.cfg, monitor=mon)
            self.windows.append(win)
            win.present()

    def _on_monitors_changed(self, *_):
        if not self._rebuild_pending and not self._quitting:
            self._rebuild_pending = True
            GLib.timeout_add(500, self._rebuild)

    def _rebuild(self):
        self._rebuild_pending = False
        if not self._quitting:
            self.hold()
            self._build_windows()
            self.release()
        return GLib.SOURCE_REMOVE


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fliqlo tarzı flip saat")
    ap.add_argument("--preview", "--window", action="store_true",
                    help="pencere modunda aç (hareketle kapanmaz)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--24h", dest="h24", action="store_true", help="24 saat biçimi")
    g.add_argument("--12h", dest="h12", action="store_true", help="12 saat biçimi")
    ap.add_argument("--seconds", action="store_true", help="saniyeyi göster")
    dg = ap.add_mutually_exclusive_group()
    dg.add_argument("--date", dest="date", action="store_true", help="tarihi göster")
    dg.add_argument("--no-date", dest="no_date", action="store_true", help="tarihi gizle")
    ap.add_argument("--no-lock", action="store_true",
                    help="kapanırken ekranı kilitleme")
    args = ap.parse_args(argv)
    app = ClockApp(args)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
