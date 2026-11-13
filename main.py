# Copyright (c) 2026 Argo Andhika Nugroho
# Lisensi MIT - lihat file LICENSE. Nama pembuat wajib dicantumkan.
"""
main.py
=======
Titik awal aplikasi Prompter. Jalankan:  python main.py
Bisa juga membuka file langsung:          python main.py naskah.txt

Jika terjadi error, pesan akan muncul dan detailnya disimpan ke file
error.log di folder data aplikasi (lihat settings._data_dir).
"""

import datetime
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from settings import APP_AUTHOR, APP_DIR, APP_NAME, APP_VERSION

ERROR_LOG = APP_DIR / "error.log"


def handle_error(exc_type, exc_value, exc_traceback) -> None:
    """Tangkap semua error yang tidak tertangani: simpan ke log + tampilkan pesan."""
    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as log:
            log.write(f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====\n{detail}")
    except OSError:
        pass
    if QApplication.instance():
        QMessageBox.critical(
            None, "Prompter - Terjadi Kesalahan",
            f"{exc_type.__name__}: {exc_value}\n\nDetail tersimpan di:\n{ERROR_LOG}",
        )


def main() -> None:
    sys.excepthook = handle_error

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_AUTHOR)
    app.setStyle("Fusion")

    from editor_window import EditorWindow   # diimpor di sini agar error impor ikut tercatat

    window = EditorWindow()
    if len(sys.argv) > 1:          # file yang di-drag ke .exe / "Open with"
        window.open_file(sys.argv[1])
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
