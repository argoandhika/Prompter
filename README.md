# Prompter

**© 2026 Argo Andhika Nugroho** · Lisensi [MIT](LICENSE)

Aplikasi teleprompter desktop untuk **Windows, macOS, dan Linux**.
Terinspirasi dari promptr.co dan teleprompter-online.com. Dibuat dengan **Python + PySide6 (Qt)**.

## Download & pasang

Ambil file untuk OS Anda di halaman [**Releases**](../../releases/latest):

| OS | File | Cara pakai |
|---|---|---|
| **Windows 10/11** | `Prompter-vX.Y.Z-windows.zip` | Ekstrak, klik dua kali `Prompter\Prompter.exe`. Jika muncul SmartScreen: *More info → Run anyway*. |
| **macOS** (Apple Silicon M1/M2/M3/M4) | `Prompter-vX.Y.Z-macos.zip` | Ekstrak, pindahkan `Prompter.app` ke *Applications*. Pertama kali: **klik kanan → Open → Open** (aplikasi belum ditandatangani Apple). |
| **Linux** (x86-64, glibc 2.35+) | `Prompter-vX.Y.Z-linux.tar.gz` | `tar -xzf Prompter-*-linux.tar.gz` lalu jalankan `./Prompter/Prompter` |

Tidak perlu menginstal Python. Di macOS, tombol **Ctrl** pada tabel di bawah = **⌘ Command**.

Ada masalah atau saran? Silakan buka [**Issues**](../../issues).

## Fitur

- Editor naskah, bisa buka/simpan file `.txt` / `.md`. Naskah terakhir tersimpan otomatis.
- Gulir sangat halus (OpenGL + VSync, posisi sub-piksel) dengan kecepatan 0–100.
- **Panel pengaturan satu baris di bawah layar baca**: mulai/jeda, ke awal, kecepatan
  (slider + tombol −/+), ukuran huruf, jarak baris, margin, cermin ↔ / ↕, info waktu,
  layar penuh, tutup. Semua bisa diubah saat prompter sedang berjalan.
  Tekan S untuk menyembunyikan; arahkan mouse ke bawah layar untuk memunculkan lagi.
- Hitung mundur sebelum mulai.
- **Mode cermin** kiri-kanan dan atas-bawah untuk kaca teleprompter.
- Penanda baris baca (panah merah) yang posisinya bisa diatur.
- Jenis/ukuran huruf, huruf tebal, jarak baris, margin, perataan, warna teks dan latar.
- Bar info: waktu berjalan, perkiraan sisa waktu, kecepatan, progres.
- Pilih monitor untuk layar baca (cocok untuk monitor kedua/teleprompter).
- Perubahan pengaturan langsung terlihat di layar baca, termasuk saat naskah diedit.
- Jumlah kata dan perkiraan durasi bicara.

## Tombol pintas di layar baca

| Tombol | Fungsi |
|---|---|
| S | Sembunyikan / tampilkan panel bawah |
| Spasi / Klik | Mulai / jeda |
| ↑ / ↓ | Kecepatan +1 / −1 (tahan Shift = ±5) |
| ← / → | Mundur / maju satu baris |
| Page Up / Page Down | Mundur / maju satu layar |
| Roda mouse | Geser naskah (meluncur halus) **atau** atur kecepatan — pilih di pengaturan / tombol 🖱 / tekan W |
| Shift + roda | Fungsi kebalikan dari mode roda yang dipilih |
| Ctrl + roda | Perbesar / perkecil huruf |
| Klik roda (tombol tengah) | **Auto-scroll ala browser**: muncul jangkar ⊙, gerakkan mouse ke bawah/atas → naskah meluncur, makin jauh makin cepat. Klik lagi / Esc = berhenti. Bisa juga tahan roda sambil geser, lepas = berhenti. Atur rasanya di `AUTOSCROLL_*` (prompter_window.py) |
| Home / End | Ke awal / akhir naskah |
| + / − | Perbesar / perkecil huruf |
| M / V | Cermin kiri-kanan / atas-bawah |
| G / I | Penanda baca / bar info |
| F / F11 | Layar penuh / jendela |
| F1 / H | Bantuan |
| Esc | Tutup layar baca |

Di editor: **F5** = mulai prompter, Ctrl+N/O/S = baru/buka/simpan.

## Struktur kode

```
Prompter/
├── main.py              Titik awal aplikasi (membuka jendela editor)
├── editor_window.py     Jendela utama: editor naskah + panel pengaturan
├── prompter_window.py   Layar baca: menggambar & menggulirkan naskah
├── control_bar.py       Panel pengaturan satu baris di bawah layar baca
├── settings.py          Daftar pengaturan + simpan/muat JSON + format_time
├── requirements.txt     Library yang dibutuhkan
├── build_exe.bat        Build manual di Windows  -> Aplikasi\Prompter.exe
├── build.sh             Build manual di macOS / Linux -> Aplikasi/Prompter.app atau Aplikasi/Prompter/
├── version_info.txt     Info versi & copyright yang tertanam di Prompter.exe
├── .github/workflows/build.yml   Build otomatis 3 OS + Release di GitHub Actions
├── .venv\               Python + library khusus proyek ini (dibuat otomatis, jangan diedit)
└── Aplikasi\            HASIL BUILD lokal (dibuat ulang setiap build, tidak masuk git)
```

Alur data: `EditorWindow` dan `PrompterWindow` memakai **objek `Settings` yang sama**.
- Panel editor diubah → `EditorWindow._set()` → simpan → `prompter.apply_settings(nama)`
- Panel bawah / keyboard di layar baca → `prompter.set_setting()` → sinyal `settings_changed`
  → panel editor & panel bawah ikut update
- Pengaturan di `LAYOUT_SETTINGS` (prompter_window.py) membuat naskah disusun ulang;
  yang lain (kecepatan, cermin, dll.) cukup digambar ulang, sehingga gulir tidak tersendat.

Kenapa gulirnya mulus (lihat juga komentar di `prompter_window.py`):
- Naskah dirender sekali jadi tile gambar, lalu digeser di posisi sub-piksel (OpenGL).
- Jam animasi dibulatkan ke kelipatan refresh monitor (`_frame_seconds`), jadi setiap
  gambar yang tampil bergeser dengan jarak yang sama.
- Layar penuh di Windows = jendela tanpa bingkai +1 piksel (`set_fullscreen`), bukan fullscreen
  asli, karena fullscreen OpenGL asli bisa macet di monitor utama Windows. macOS/Linux memakai
  fullscreen asli.
- Gulir manual (roda/panah) memakai model pegas (`_advance_manual_scroll`): kecepatan
  naik-turun bertahap. Atur rasanya lewat `SCROLL_SPRING` dan `WHEEL_STEP_LINES`.

Data pengguna (`pengaturan.json`, `naskah_terakhir.txt`, `error.log`) disimpan di:

| OS | Folder |
|---|---|
| Windows | `%APPDATA%\Prompter\` |
| macOS | `~/Library/Application Support/Prompter/` |
| Linux | `~/.config/Prompter/` |

Hapus folder itu untuk reset total. Jika terjadi error, detailnya tercatat di `error.log`.

## Menjalankan dari kode (untuk development)

Windows:
```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```
macOS / Linux:
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Membuat aplikasi secara manual

PyInstaller hanya bisa membuat aplikasi untuk OS tempat ia dijalankan
(exe Windows harus dibuat di Windows, aplikasi Mac di Mac, dst.).

- **Windows**: klik dua kali **`build_exe.bat`** (tutup Prompter dulu). Hasil: **`Aplikasi\Prompter.exe`**.
  Folder `_internal` di sebelahnya berisi library Python/Qt dan **wajib ada**.
- **macOS / Linux**: jalankan `bash build.sh`. Hasil: `Aplikasi/Prompter.app` (Mac) atau
  `Aplikasi/Prompter/Prompter` (Linux).

Untuk dipindah ke komputer lain, salin/zip **seluruh folder** `Aplikasi` (tidak perlu instal Python).

## Build otomatis 3 OS & merilis versi baru (GitHub Actions)

File `.github/workflows/build.yml` membuat versi Windows, macOS, dan Linux di server GitHub.

- **Setiap push ke `main`**: GitHub membuat & menguji aplikasi di 3 OS. Hasilnya bisa diunduh untuk
  dicoba di tab **Actions** → pilih run → bagian **Artifacts**.
- **Merilis versi baru**:
  1. Naikkan versi di `settings.py` (`APP_VERSION`) dan `version_info.txt`, lalu commit & push.
  2. Buat dan kirim tag:
     ```sh
     git tag v1.2.0
     git push origin v1.2.0
     ```
  3. Tunggu ±10 menit. Halaman **Releases** otomatis berisi
     `Prompter-v1.2.0-windows.zip`, `-macos.zip`, dan `-linux.tar.gz`.

## Panduan maintenance

### Mengganti versi aplikasi

Ubah `APP_VERSION` di `settings.py` **dan** angka versi di `version_info.txt`
(yang tampil di klik kanan exe → Properties → Details), lalu build ulang
(atau buat tag baru, lihat bagian di atas).

### Cara menambah pengaturan baru (contoh: "huruf miring")

1. **settings.py**: tambahkan field di class `Settings`:
   ```python
   italic: bool = False
   ```
2. **editor_window.py**: tambahkan satu baris di grup yang cocok, misalnya `_build_text_group()`:
   ```python
   self._add_check(form, "Huruf miring", "italic")
   ```
   Fungsi pembantu yang tersedia: `_add_spin` (angka), `_add_check` (centang), `_add_color` (warna).
3. **prompter_window.py**: pakai nilainya, misalnya di `rebuild_document()`:
   ```python
   font.setItalic(s.italic)
   ```

4. (Opsional) agar bisa diubah saat prompter berjalan, tambahkan di `control_bar.py`:
   ```python
   self._add_toggle("Miring", "italic", "Huruf miring")
   ```
   dan masukkan `"italic"` ke `LAYOUT_SETTINGS` di `prompter_window.py` karena memengaruhi susunan teks.

Penyimpanan dan sinkronisasi ke panel berjalan otomatis.

### Cara menambah tombol keyboard baru

Tambahkan satu baris di `PrompterWindow._build_key_actions()` (tombol → fungsi), contoh:
```python
K.Key_R: self.go_to_start,
```
lalu satu baris di `HELP_LINES` supaya muncul di layar bantuan F1.

### Hal yang sering diubah

| Ingin mengubah | Lokasi |
|---|---|
| Nilai default pengaturan | `settings.py` → class `Settings` |
| Seberapa cepat 1 level kecepatan | `settings.py` → `SPEED_FACTOR` |
| Warna panah penanda | `prompter_window.py` → `GUIDE_COLOR` |
| Teks contoh saat pertama dibuka | `editor_window.py` → `SAMPLE_TEXT` |
| Kecepatan bicara untuk estimasi durasi | `editor_window.py` → `WORDS_PER_MINUTE` |
| Tampilan bar info / hitung mundur | `prompter_window.py` → `_draw_info_bar` / `_draw_countdown` |

## Lisensi & Hak Cipta

Copyright (c) 2026 **Argo Andhika Nugroho**.

Kode ini dirilis dengan [lisensi MIT](LICENSE). Anda boleh memakai, mengubah, dan
membagikan ulang kode ini, termasuk untuk keperluan komersial, **dengan syarat
pemberitahuan hak cipta di atas dan isi file `LICENSE` tetap disertakan** di setiap salinan
atau turunannya. Menghapus nama pembuat berarti melanggar lisensi.
