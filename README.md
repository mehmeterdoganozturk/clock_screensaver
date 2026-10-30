# Fliqlo for Linux (GNOME / Wayland)

[Fliqlo](https://fliqlo.com/screensaver/) tarzı flip saat ekran koruyucusu — Ubuntu 26.04 GNOME Wayland için.

## Neden ayrı bir servis?
GNOME Wayland'de XScreenSaver gibi "ekran koruyucu modülü" takma API'si yoktur.
Bu proje iki parçadan oluşur:

| Parça | Görev |
|---|---|
| `fliqlo_linux/clock.py` | GTK4 tam ekran flip saat (tüm monitörlerde). Fare hareketi / tuş / tıklama ile kapanır. |
| `fliqlo_linux/daemon.py` | Mutter'ın `org.gnome.Mutter.IdleMonitor` D-Bus API'siyle boşta kalmayı izler, süre dolunca saati açar. systemd kullanıcı servisi olarak çalışır. |
| `fliqlo_linux/settings.py` | libadwaita ayar penceresi. |

Servis şunlara dikkat eder:
- Ekran kilitliyse saati açmaz; kilit devreye girerse saati kapatır.
- Video/sunum gibi boşta kalmayı engelleyen bir uygulama varsa açmaz (bitince 30 sn içinde açar).
- Aynı anda tek saat çalışır; ayar değişikliklerini anında uygular.

## Kurulum
```bash
./install.sh
```
`sudo` gerekmez; her şey `~/.local` ve `~/.config` altına kurulur.

## Kullanım
- Uygulamalar menüsü: **Fliqlo** (hemen başlat) ve **Fliqlo Ayarları**
- Terminal: `fliqlo`, `fliqlo --preview`, `fliqlo --12h --seconds`, `fliqlo-settings`
- Günlük: `journalctl --user -u fliqlo-daemon -f`

> **Not:** GNOME'un *Ayarlar → Güç → Ekranı Karart* süresi, Fliqlo'nun boşta kalma
> süresinden uzun (veya "Asla") olmalı; aksi halde GNOME ekranı saatten önce karartır.

## Kaldırma
```bash
./uninstall.sh
```
