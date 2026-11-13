# Copyright (c) 2026 Argo Andhika Nugroho
# Lisensi MIT - lihat file LICENSE. Nama pembuat wajib dicantumkan.
"""
settings.py
===========
Tempat SEMUA pengaturan aplikasi didefinisikan, disimpan, dan dimuat.

Pengaturan disimpan otomatis ke file JSON:
    %APPDATA%\\Prompter\\pengaturan.json
Naskah terakhir disimpan otomatis ke:
    %APPDATA%\\Prompter\\naskah_terakhir.txt

>>> Ingin menambah pengaturan baru? Lihat README.md bagian
    "Cara menambah pengaturan baru".
"""

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

# Info aplikasi (tampil di judul jendela, menu Tentang, dan bantuan F1)
APP_NAME = "Prompter"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Argo Andhika Nugroho"
COPYRIGHT = f"© 2026 {APP_AUTHOR}"

# Folder penyimpanan data aplikasi (di Windows: C:\Users\<nama>\AppData\Roaming\Prompter)
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Prompter"
SETTINGS_FILE = APP_DIR / "pengaturan.json"
LAST_SCRIPT_FILE = APP_DIR / "naskah_terakhir.txt"

# 1 level kecepatan = berapa piksel per detik teks bergulir.
# Contoh: kecepatan 12 x 5 = 60 piksel per detik.
SPEED_FACTOR = 5


@dataclass
class Settings:
    """Semua pengaturan beserta nilai bawaannya (default)."""

    # --- Tampilan teks ---
    font_family: str = "Arial"
    font_size: int = 60          # ukuran huruf (point)
    bold: bool = False
    line_spacing: int = 150      # jarak antar baris dalam persen (100 = rapat)
    margin_percent: int = 10     # margin kiri & kanan, persen dari lebar layar
    align: str = "kiri"          # "kiri" | "tengah" | "rata"
    text_color: str = "#FFFFFF"
    bg_color: str = "#000000"

    # --- Gulir ---
    speed: int = 12              # 0 - 100 (lihat SPEED_FACTOR)
    countdown: int = 3           # hitung mundur sebelum mulai (detik), 0 = mati
    wheel_mode: str = "geser"    # fungsi roda mouse: "geser" (geser naskah) | "kecepatan"

    # --- Mode cermin (untuk kaca teleprompter) ---
    mirror_h: bool = False       # balik kiri-kanan
    mirror_v: bool = False       # balik atas-bawah

    # --- Bantuan baca ---
    show_guide: bool = True      # tampilkan penanda baris baca
    guide_position: int = 35     # posisi penanda, persen dari atas layar
    show_info: bool = True       # tampilkan bar info (waktu, kecepatan, progres)

    # --- Layar ---
    screen_index: int = 0        # monitor mana yang dipakai untuk layar baca
    fullscreen: bool = True

    # ------------------------------------------------------------------
    def save(self) -> None:
        """Simpan pengaturan ke file JSON."""
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass  # gagal simpan bukan masalah fatal, aplikasi tetap jalan

    @classmethod
    def load(cls) -> "Settings":
        """Muat pengaturan dari file. Nilai yang rusak/hilang diganti default."""
        settings = cls()
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings

        for field in fields(cls):
            value = data.get(field.name)
            # hanya pakai nilai dari file jika tipenya cocok dengan default
            if type(value) is type(getattr(settings, field.name)):
                setattr(settings, field.name, value)
        return settings

    def reset(self) -> None:
        """Kembalikan semua pengaturan ke default (objek yang sama tetap dipakai)."""
        default = Settings()
        for field in fields(self):
            setattr(self, field.name, getattr(default, field.name))


def load_last_script() -> str:
    """Ambil naskah terakhir yang ditulis pengguna (kosong jika belum ada)."""
    try:
        return LAST_SCRIPT_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


def save_last_script(text: str) -> None:
    """Simpan naskah saat ini supaya muncul lagi ketika aplikasi dibuka."""
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        LAST_SCRIPT_FILE.write_text(text, encoding="utf-8")
    except OSError:
        pass


def format_time(seconds: float) -> str:
    """Ubah detik menjadi teks mm:ss, mis. 75 -> "01:15"."""
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
