# Fliqlo for Linux (GNOME / Wayland) ⏰
**Retro Mekanik Çevirmeli Saat Ekran Koruyucusu (Ubuntu 24.04 / 26.04 Wayland Uyumlu)**

Meşhur [Fliqlo](https://fliqlo.com/) tarzı ikonik mekanik çevirmeli saat (Flip Clock) tasarımının modern Linux GNOME Wayland ortamı için sıfırdan geliştirilmiş GTK4 sürümüdür.

60 FPS pürüzsüz vektörel yaprak animasyonları, 12/24 saat formatları, isteğe bağlı canlı saniye ve tarih göstergeleriyle ekranınız boşta kaldığında çalışma alanınıza zarif bir retro dokunuş katar.

---

## 📑 İçindekiler
- [✨ Temel Özellikler](#-temel-özellikler)
- [🏗️ Sistem Mimarisi & Wayland Uyumu](#️-sistem-mimarisi--wayland-uyumu)
- [🖥️ Görsel Seçenekler & Formatlar](#️-görsel-seçenekler--formatlar)
- [🚀 Kurulum ve İlk Çalıştırma](#-kurulum-ve-ilk-çalıştırma)
- [🎮 Kullanım & Terminal Komutları](#-kullanım--terminal-komutları)
- [⚙️ Ayarlar & Yapılandırma](#️-ayarlar--yapılandırma)
- [💡 Önemli GNOME Güç Ayarı İpucu](#-önemli-gnome-güç-ayarı-ipucu)
- [📂 Proje Dizin Yapısı](#-proje-dizin-yapısı)
- [🗑️ Kaldırma](#️-kaldırma)
- [📜 Lisans & Telif Hakkı](#-lisans--telif-hakkı)

---

## ✨ Temel Özellikler

1. **Otantik Flip Clock Animasyonu (Cairo / GTK4)**:
   * Mekanik yaprakların düşüş anını 60 FPS akıcılıkla simüle eden gerçekçi 3D gölgeli vektör çizimi.
   * Keskin ve pürüzsüz tipografi; 1080p, 2K ve 4K ekranlarda hiçbir pikselleşme olmadan otomatik ölçeklenir.
2. **Çoklu Zaman & Tarih Formatları**:
   * **12 Saatlik Format (AM / PM)** veya **24 Saatlik Format**.
   * **Canlı Saniye Göstergesi**: İsteğe bağlı olarak saat ve dakikanın yanında dönen saniye yaprağı.
   * **Tarih Bandı**: Saatin altında gün, ay, yıl gösterimi (Örn: *31 Ekim 2026 Cumartesi*).
3. **Çoklu Monitör Desteği**:
   * Dizüstü bilgisayar ekranı ve bağlı harici monitörlerin tümünü algılar ve her ekranda tam ekran olarak bağımsız konumlanır.
4. **Masaüstü & Medya Duyarlılığı**:
   * Film/video izlerken veya sunum yaparken (`org.gnome.SessionManager.IsInhibited`) ekran koruyucu araya girmez.
   * Fare hareketi, klavye tuşu veya tıklamayla anında (gecikmesiz) kapanır.
5. **Modern Libadwaita / GTK4 Ayar Penceresi**:
   * Boşta kalma süresi, saat boyutu, renk temaları ve saniye/tarih tercihleri tek tıkla yapılandırılabilir.

---

## 🏗️ Sistem Mimarisi & Wayland Uyumu

GNOME Wayland oturumunda X11 ekran koruyucu kancaları bulunmadığı için Fliqlo, modern bir istemci-servis mimarisiyle çalışır:

```
+-------------------------------------------------------------+
|                     GNOME Mutter (Wayland)                  |
|          D-Bus: org.gnome.Mutter.IdleMonitor                |
+------------------------------▲------------------------------+
                               │ Boşta kalma süresi takibi
                               ▼
+-------------------------------------------------------------+
|                  Fliqlo Daemon (systemd --user)             |
|                    (fliqlo_linux/daemon.py)                 |
|                                                             |
|  * Oturum kilitli mi kontrolü                               |
|  * Medya / Inhibit engellemeleri kontrolü                   |
|  * Süre dolunca clock.py sürecini tam ekran başlatır        |
+------------------------------▲------------------------------+
                               │
                               ▼
+-------------------------------------------------------------+
|                     GTK4 Tam Ekran Saat                     |
|                    (fliqlo_linux/clock.py)                  |
|                                                             |
|  * Cairo 60 FPS Mekanik Flip Animasyonu                     |
|  * Çoklu monitör Gdk.Display desteği                        |
|  * Fare veya tuş basımıyla anında güvenli çıkış             |
+-------------------------------------------------------------+
```

---

## 🖥️ Görsel Seçenekler & Formatlar

* **Standart Mod**: Büyük retro saat ve dakika yaprakları.
* **Gelişmiş Mod (Saat + Dakika + Saniye)**: Saniyelerin akışını izlemek isteyenler için üçüncü kompakt flip kutusu.
* **Tarih Şeridi**: Saatin altında sistem diline uygun lokalize Türkçe/İngilizce tarih rozeti.
* **Boyutlandırma**: Küçük ekranlardan devasa 4K televizyonlara kadar %50 ile %150 arasında ölçekleme desteği.

---

## 🚀 Kurulum ve İlk Çalıştırma

Root (`sudo`) yetkisi gerektirmeden kullanıcı dizinine tek tıkla kurabilirsiniz:

```bash
git clone https://github.com/mehmeterdoganozturk/clock_screensaver.git
cd clock_screensaver
chmod +x install.sh
./install.sh
```

**Kurulum Betiği Neler Yapar?**
1. Python ve GTK4 dosyalarını `~/.local/share/fliqlo-screensaver/` dizinine kurar.
2. Terminal komutlarını (`fliqlo`, `fliqlo-settings`) `~/.local/bin` altına bağlar.
3. Arka plan izleme servisini `~/.config/systemd/user/fliqlo-daemon.service` olarak kaydeder ve başlatır.
4. GNOME menüsüne *Fliqlo* ve *Fliqlo Ayarları* kısayollarını ekler.

---

## 🎮 Kullanım & Terminal Komutları

* **Saati Hemen Tam Ekran Başlat**:
  ```bash
  fliqlo
  ```
* **Pencere Modunda Test Et (Önizleme)**:
  ```bash
  fliqlo --preview
  ```
* **12 Saat ve Saniyeli Başlat**:
  ```bash
  fliqlo --12h --seconds
  ```
* **Ayar Panelini Aç**:
  ```bash
  fliqlo-settings
  ```
* **Arka Plan Servis Durumunu İncele**:
  ```bash
  systemctl --user status fliqlo-daemon
  ```
* **Canlı Log Kayıtları**:
  ```bash
  journalctl --user -u fliqlo-daemon -f
  ```

---

## ⚙️ Ayarlar & Yapılandırma

Ayarlar penceresinden (`fliqlo-settings`) veya doğrudan `~/.config/fliqlo-screensaver/config.json` dosyasından yapılandırılabilir:

| Parametre | Açıklama | Varsayılan |
|---|---|---|
| `idle_minutes` | Saatin devreye gireceği boşta kalma süresi (dakika) | `5` |
| `time_format` | Saat formatı (`"24h"` veya `"12h"`) | `"24h"` |
| `show_seconds` | Canlı saniye yaprağını göster (`true`/`false`) | `false` |
| `show_date` | Saatin altında tarihi göster (`true`/`false`) | `true` |
| `scale` | Saat ölçeği (`0.5` ile `1.5` arası) | `1.0` |
| `lock_on_exit` | Saat kapatıldığında oturumu kilitle | `false` |

---

## 💡 Önemli GNOME Güç Ayarı İpucu

Ubuntu GNOME varsayılan olarak boşta kalınca ekranı karartır (Screen Dimming). Fliqlo'nun ekran kararmadan önce devreye girebilmesi için:

> **GNOME Ayarları → Güç (Power)** menüsüne gidin:
> * **"Ekranı Karart" (Dim Screen)** seçeneğini kapatın veya
> * Ekran karartma süresini Fliqlo'nun boşta kalma süresinden (Örn: 5 dk) daha uzun bir süreye (Örn: 15 dk) ayarlayın.

---

## 📂 Proje Dizin Yapısı

```
clock_screensaver/
├── LICENSE                        # Resmi MIT Lisans belgesi
├── README.md                      # Kapsamlı kullanım ve kurulum kılavuzu
├── install.sh                     # Otomatik kurulum ve systemd servisi kurucu
├── uninstall.sh                   # Temiz kaldırma betiği
├── data/                          # Masaüstü .desktop dosyaları ve ikonlar
└── fliqlo_linux/                  # Çekirdek Python paketi
    ├── daemon.py                  # Mutter IdleMonitor boşta kalma servis yöneticisi
    ├── clock.py                   # GTK4 + Cairo tam ekran flip saat çizim motoru
    ├── settings.py                # Libadwaita grafik ayarlar arayüzü
    ├── config.py                  # Yapılandırma JSON okuyucu/yazıcı
    ├── auth.py                    # Ekran kilidi ve şifre kontrol mekanizması
    └── compat.py                  # Linux Wayland / GNOME uyumluluk katmanı
```

---

## 🗑️ Kaldırma

Uygulamayı ve sistem servislerini tamamen kaldırmak için:

```bash
cd /home/erdogan/Projects/clock_screensaver
./uninstall.sh
```

---

## 📜 Lisans & Telif Hakkı

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak yayınlanmıştır.  
© 2026 **Mehmet Erdoğan Öztürk** <mehmeterdoganozturk@gmail.com>
