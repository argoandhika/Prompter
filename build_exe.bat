@echo off
REM ============================================================
REM  Membuat Prompter.exe
REM  Cukup klik dua kali file ini.
REM  Hasil: folder Aplikasi\  (jalankan Aplikasi\Prompter.exe)
REM
REM  Isi folder Aplikasi:
REM    Prompter.exe  -> aplikasinya
REM    _internal\    -> library Python/Qt, WAJIB ada di sebelah exe
REM
REM  Format folder (--onedir) dipakai karena terbuka dalam 1-2 detik.
REM  Format satu file (--onefile) butuh 10+ detik karena harus
REM  mengekstrak dirinya dulu setiap kali dibuka.
REM  Untuk dibagikan: zip seluruh folder Aplikasi.
REM ============================================================
cd /d "%~dp0"

if not exist .venv (
    echo [1/4] Membuat virtual environment...
    python -m venv .venv || goto :error
)

echo [2/4] Menginstal library...
.venv\Scripts\python -m pip install --quiet -r requirements.txt || goto :error

echo [3/4] Membuat file exe...
REM Semua file sementara PyInstaller ditaruh di folder "build" lalu dihapus.
.venv\Scripts\pyinstaller --noconfirm --clean --onedir --windowed --name Prompter ^
    --distpath build\dist --workpath build\work --specpath build ^
    --version-file "%~dp0version_info.txt" ^
    "%~dp0main.py" || goto :error

echo [4/4] Memindahkan hasil ke folder Aplikasi...
if exist Aplikasi rmdir /s /q Aplikasi
if exist Aplikasi goto :locked
REM Disalin (bukan dipindah) karena antivirus sering mengunci file exe yang baru dibuat.
robocopy build\dist\Prompter Aplikasi /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :error
rmdir /s /q build 2>nul

echo.
echo SELESAI! Jalankan: %~dp0Aplikasi\Prompter.exe
pause
exit /b 0

:locked
echo.
echo GAGAL: folder Aplikasi sedang dipakai. Tutup Prompter dulu, lalu coba lagi.
pause
exit /b 1

:error
echo.
echo GAGAL membuat exe. Lihat pesan error di atas.
pause
exit /b 1
