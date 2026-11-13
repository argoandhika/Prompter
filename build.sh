#!/usr/bin/env bash
# Copyright (c) 2026 Argo Andhika Nugroho
# Lisensi MIT - lihat file LICENSE.
# ============================================================
#  Membuat aplikasi Prompter di macOS / Linux.
#  (Di Windows pakai build_exe.bat)
#
#  Jalankan dari folder proyek:   bash build.sh
#  Hasil:
#    macOS : Aplikasi/Prompter.app   (klik dua kali untuk membuka)
#    Linux : Aplikasi/Prompter/Prompter   (jalankan file ini)
#
#  Biasanya tidak perlu dijalankan manual: GitHub Actions
#  (.github/workflows/build.yml) membuat versi Windows, macOS,
#  dan Linux otomatis setiap ada tag baru, mis. v1.1.0.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "[1/4] Membuat virtual environment..."
    python3 -m venv .venv
fi

echo "[2/4] Menginstal library..."
.venv/bin/python -m pip install --quiet -r requirements.txt

echo "[3/4] Membuat aplikasi..."
.venv/bin/pyinstaller --noconfirm --clean --onedir --windowed --name Prompter \
    --osx-bundle-identifier com.argoandhika.prompter \
    --distpath build/dist --workpath build/work --specpath build \
    "$PWD/main.py"

echo "[4/4] Memindahkan hasil ke folder Aplikasi..."
rm -rf Aplikasi
mkdir -p Aplikasi
if [ "$(uname)" = "Darwin" ]; then
    cp -R build/dist/Prompter.app Aplikasi/
    echo "SELESAI! Buka: Aplikasi/Prompter.app"
else
    cp -R build/dist/Prompter Aplikasi/
    echo "SELESAI! Jalankan: Aplikasi/Prompter/Prompter"
fi
rm -rf build
