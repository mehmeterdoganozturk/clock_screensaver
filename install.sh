#!/usr/bin/env bash
# Fliqlo for Linux (GNOME/Wayland) — kullanıcıya özel kurulum (sudo gerekmez)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/fliqlo-linux"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> Bağımlılıklar kontrol ediliyor"
missing=()
python3 -c 'import gi; gi.require_version("Gtk","4.0"); from gi.repository import Gtk' 2>/dev/null || missing+=(gir1.2-gtk-4.0 python3-gi)
python3 -c 'import gi; gi.require_version("Adw","1"); from gi.repository import Adw' 2>/dev/null || missing+=(gir1.2-adw-1)
python3 -c 'import cairo; import gi; gi.require_foreign("cairo")' 2>/dev/null || missing+=(python3-gi-cairo python3-cairo)
python3 -c 'import gi; gi.require_version("PangoCairo","1.0"); from gi.repository import PangoCairo' 2>/dev/null || missing+=(gir1.2-pango-1.0)
if ((${#missing[@]})); then
    echo "Eksik paketler: ${missing[*]}"
    echo "Kurmak için:  sudo apt install ${missing[*]}"
    exit 1
fi

echo "==> Dosyalar kopyalanıyor: $DEST"
rm -rf "$DEST"
mkdir -p "$DEST" "$BIN" "$APPS" "$ICONS" "$UNITS"
cp -r "$SRC/fliqlo_linux" "$DEST/"
find "$DEST" -name '__pycache__' -prune -exec rm -rf {} +
chmod +x "$DEST/fliqlo_linux/"{clock,daemon,settings}.py
cp "$SRC/data/fliqlo-linux.svg" "$ICONS/fliqlo-linux.svg"

ln -sf "$DEST/fliqlo_linux/clock.py"    "$BIN/fliqlo"
ln -sf "$DEST/fliqlo_linux/settings.py" "$BIN/fliqlo-settings"

sed "s|@DEST@|$DEST|g" "$SRC/data/fliqlo-linux.desktop.in"          > "$APPS/fliqlo-linux.desktop"
sed "s|@DEST@|$DEST|g" "$SRC/data/fliqlo-linux-settings.desktop.in" > "$APPS/fliqlo-linux-settings.desktop"
sed "s|@DEST@|$DEST|g" "$SRC/data/fliqlo-daemon.service.in"         > "$UNITS/fliqlo-daemon.service"
update-desktop-database "$APPS" >/dev/null 2>&1 || true
gtk-update-icon-cache -q "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "==> Servis etkinleştiriliyor"
systemctl --user daemon-reload
systemctl --user enable fliqlo-daemon.service >/dev/null
systemctl --user restart fliqlo-daemon.service || true
sleep 1
systemctl --user --no-pager --lines=5 status fliqlo-daemon.service || true

delay=$(gsettings get org.gnome.desktop.session idle-delay 2>/dev/null | awk '{print $NF}')
echo
echo "Kurulum tamam."
echo "  • Uygulamalar menüsü: 'Fliqlo' (hemen başlat) ve 'Fliqlo Ayarları'"
echo "  • Terminal: fliqlo  |  fliqlo --preview  |  fliqlo-settings"
echo "  • Günlük:   journalctl --user -u fliqlo-daemon -f"
if [[ -n "${delay:-}" && "$delay" != "0" ]]; then
    echo
    echo "Not: GNOME 'Ekranı karart' süresi ${delay} sn. Saatin görünebilmesi için bu süre"
    echo "     Fliqlo'nun boşta kalma süresinden UZUN olmalı (Ayarlar > Güç > Ekranı Karart)."
fi
