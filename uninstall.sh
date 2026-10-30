#!/usr/bin/env bash
# Fliqlo for Linux kaldırma
set -u
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
systemctl --user disable --now fliqlo-daemon.service 2>/dev/null || true
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/fliqlo-daemon.service"
systemctl --user daemon-reload 2>/dev/null || true
rm -rf "$DATA/fliqlo-linux"
rm -f "$HOME/.local/bin/fliqlo" "$HOME/.local/bin/fliqlo-settings"
rm -f "$DATA/applications/fliqlo-linux.desktop" "$DATA/applications/fliqlo-linux-settings.desktop"
rm -f "$DATA/icons/hicolor/scalable/apps/fliqlo-linux.svg"
update-desktop-database "$DATA/applications" >/dev/null 2>&1 || true
echo "Kaldırıldı. (Ayarlar korunuyor: ~/.config/fliqlo-linux — istersen elle sil)"
