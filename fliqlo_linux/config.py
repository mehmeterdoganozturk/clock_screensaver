"""Ortak ayar dosyası yönetimi: ~/.config/fliqlo-linux/config.ini"""

import configparser
import os
from dataclasses import dataclass, asdict, fields

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "fliqlo-linux",
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.ini")


@dataclass
class Config:
    # Saat görünümü
    use_24h: bool = True          # False => 12 saat (AM/PM)
    show_seconds: bool = False
    show_date: bool = True        # saatin altında Türkçe tarih
    brightness: float = 1.0       # 0.1 - 1.0
    scale: float = 1.0            # 0.5 - 1.0 (kartların ekrana göre boyutu)
    animate: bool = True
    # Ekran koruyucu servisi
    enabled: bool = True
    idle_minutes: float = 5.0     # boşta kalma süresi (dakika)
    respect_inhibit: bool = True  # video vb. oynarken başlatma
    all_monitors: bool = True
    lock_on_exit: bool = True     # saatten çıkarken ekranı kilitle
    lock_mode: str = "macos"      # "macos" (dahili şifre kutusu & timeout) veya "gnome" (sistem kilit ekranı)
    lock_timeout: int = 20        # saniye; şifre girilmezse kutunun kaybolup saatin devam etme süresi

    def clamp(self) -> "Config":
        self.brightness = min(1.0, max(0.1, float(self.brightness)))
        self.scale = min(1.0, max(0.5, float(self.scale)))
        self.idle_minutes = min(240.0, max(0.25, float(self.idle_minutes)))
        if self.lock_mode not in ("macos", "gnome"):
            self.lock_mode = "macos"
        try:
            self.lock_timeout = min(120, max(5, int(self.lock_timeout)))
        except (ValueError, TypeError):
            self.lock_timeout = 20
        return self


def _to_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on", "evet")


def load() -> Config:
    cfg = Config()
    parser = configparser.ConfigParser()
    try:
        parser.read(CONFIG_PATH, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return cfg.clamp()
    if not parser.has_section("fliqlo"):
        return cfg.clamp()
    sec = parser["fliqlo"]
    for f in fields(Config):
        if f.name not in sec:
            continue
        raw = sec[f.name]
        try:
            if f.type in (bool, "bool"):
                setattr(cfg, f.name, _to_bool(raw))
            elif f.type in (float, "float"):
                setattr(cfg, f.name, float(raw))
            else:
                setattr(cfg, f.name, raw)
        except ValueError:
            pass  # bozuk değer -> varsayılan kalsın
    return cfg.clamp()


def save(cfg: Config) -> None:
    cfg.clamp()
    os.makedirs(CONFIG_DIR, exist_ok=True)
    parser = configparser.ConfigParser()
    parser["fliqlo"] = {k: str(v) for k, v in asdict(cfg).items()}
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        parser.write(fh)
    os.replace(tmp, CONFIG_PATH)  # atomik yazma
