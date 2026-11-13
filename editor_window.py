# Copyright (c) 2026 Argo Andhika Nugroho
# Lisensi MIT - lihat file LICENSE. Nama pembuat wajib dicantumkan.
"""
editor_window.py
================
Jendela utama: tempat menulis naskah dan mengatur tampilan prompter.

Susunan jendela:
  - Toolbar  : Baru, Buka, Simpan, Simpan Sebagai, Mulai Prompter (F5)
  - Kiri     : editor naskah
  - Kanan    : panel pengaturan
  - Bawah    : jumlah kata & perkiraan durasi

Setiap pengaturan yang diubah langsung disimpan dan langsung diterapkan
ke layar baca jika sedang terbuka.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from prompter_window import PrompterWindow, centered_rect
from settings import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    COPYRIGHT,
    UI_FONT_FAMILIES,
    Settings,
    format_time,
    load_last_script,
    save_last_script,
)

APP_TITLE = APP_NAME
WORDS_PER_MINUTE = 130   # rata-rata kecepatan bicara, untuk perkiraan durasi

ALIGN_OPTIONS = {"kiri": "Rata kiri", "tengah": "Tengah", "rata": "Rata kiri-kanan"}
WHEEL_OPTIONS = {"geser": "Geser naskah", "kecepatan": "Atur kecepatan"}

SAMPLE_TEXT = """Selamat datang di Prompter!

Tulis atau tempel naskah Anda di sini, lalu tekan F5 atau tombol "Mulai Prompter".

Di layar baca, tekan SPASI untuk mulai atau jeda. Gunakan panah atas dan bawah untuk mengatur kecepatan. Tekan F1 untuk melihat semua tombol pintas.

Untuk kaca teleprompter, aktifkan mode cermin dengan menekan tombol M.

Selamat membaca!
"""


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        self.current_file: Path | None = None
        self.prompter: PrompterWindow | None = None
        self.controls: dict[str, QWidget] = {}   # nama pengaturan -> widget-nya

        self.resize(1150, 720)
        self._build_toolbar()
        self._build_layout()
        self.statusBar().addPermanentWidget(QLabel(COPYRIGHT))

        self.editor.setPlainText(load_last_script() or SAMPLE_TEXT)
        self.editor.document().setModified(False)
        self._update_title()
        self._update_stats()

    # ==================================================================
    # Membangun tampilan
    # ==================================================================
    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Utama")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        def add_action(text, shortcut, handler):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.setToolTip(f"{text} ({shortcut})")
            action.triggered.connect(handler)
            toolbar.addAction(action)
            return action

        add_action("Baru", "Ctrl+N", self.new_file)
        add_action("Buka...", "Ctrl+O", self.open_file_dialog)
        add_action("Simpan", "Ctrl+S", self.save_file)
        add_action("Simpan Sebagai...", "Ctrl+Shift+S", self.save_file_as)
        toolbar.addSeparator()
        start = add_action("▶  Mulai Prompter", "F5", self.start_prompter)
        toolbar.widgetForAction(start).setStyleSheet(
            "font-weight: bold; color: white; background: #c62828; padding: 6px 14px; border-radius: 4px;"
        )
        toolbar.addSeparator()
        add_action("Tentang", "F12", self.show_about)

    def show_about(self) -> None:
        QMessageBox.about(
            self, f"Tentang {APP_NAME}",
            f"<h3>{APP_NAME} {APP_VERSION}</h3>"
            f"<p>Aplikasi teleprompter desktop.</p>"
            f"<p>Dibuat oleh <b>{APP_AUTHOR}</b><br>{COPYRIGHT}</p>"
            f"<p>Dirilis dengan lisensi MIT (lihat file LICENSE).</p>",
        )

    def _build_layout(self) -> None:
        # --- Editor naskah ---
        self.editor = QPlainTextEdit()
        editor_font = QFont()
        editor_font.setFamilies(UI_FONT_FAMILIES)
        editor_font.setPointSize(13)
        self.editor.setFont(editor_font)
        self.editor.setPlaceholderText("Tulis atau tempel naskah di sini...")
        self.editor.textChanged.connect(self._on_text_changed)

        # --- Panel pengaturan (bisa di-scroll) ---
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(self._build_text_group())
        panel_layout.addWidget(self._build_scroll_group())
        panel_layout.addWidget(self._build_mirror_group())
        panel_layout.addWidget(self._build_screen_group())

        reset_button = QPushButton("Kembalikan ke Default")
        reset_button.clicked.connect(self.reset_settings)
        panel_layout.addWidget(reset_button)

        hint = QLabel("Di layar baca tekan <b>F1</b> untuk melihat semua tombol pintas.")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)
        panel_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(380)

        splitter = QSplitter()
        splitter.addWidget(self.editor)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([750, 400])
        self.setCentralWidget(splitter)

    def _build_text_group(self) -> QGroupBox:
        group = QGroupBox("Teks")
        form = QFormLayout(group)

        font_box = FontPicker(self.settings.font_family)
        font_box.currentTextChanged.connect(lambda family: self._set("font_family", family))
        form.addRow("Jenis huruf", font_box)
        self.controls["font_family"] = font_box

        self._add_spin(form, "Ukuran huruf", "font_size", 8, 200)
        self._add_check(form, "Huruf tebal", "bold")
        self._add_spin(form, "Jarak baris", "line_spacing", 100, 300, suffix=" %", step=10)
        self._add_spin(form, "Margin samping", "margin_percent", 0, 40, suffix=" %")

        align_box = QComboBox()
        for key, label in ALIGN_OPTIONS.items():
            align_box.addItem(label, key)
        align_box.setCurrentIndex(max(0, align_box.findData(self.settings.align)))
        align_box.currentIndexChanged.connect(lambda _: self._set("align", align_box.currentData()))
        form.addRow("Perataan", align_box)
        self.controls["align"] = align_box

        self._add_color(form, "Warna teks", "text_color")
        self._add_color(form, "Warna latar", "bg_color")
        return group

    def _build_scroll_group(self) -> QGroupBox:
        group = QGroupBox("Gulir")
        form = QFormLayout(group)

        # Kecepatan: angka + slider yang saling terhubung
        speed_spin = self._add_spin(form, "Kecepatan", "speed", 0, 100)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setValue(self.settings.speed)
        self.speed_slider.valueChanged.connect(speed_spin.setValue)
        speed_spin.valueChanged.connect(self.speed_slider.setValue)
        form.addRow("", self.speed_slider)

        self._add_spin(form, "Hitung mundur", "countdown", 0, 10, suffix=" detik")

        wheel_box = QComboBox()
        for key, label in WHEEL_OPTIONS.items():
            wheel_box.addItem(label, key)
        wheel_box.setCurrentIndex(max(0, wheel_box.findData(self.settings.wheel_mode)))
        wheel_box.currentIndexChanged.connect(lambda _: self._set("wheel_mode", wheel_box.currentData()))
        wheel_box.setToolTip("Ctrl + roda = ukuran huruf, Shift + roda = fungsi kebalikannya,\n"
                             "klik roda = auto-scroll ala browser (gerakkan mouse naik/turun)")
        form.addRow("Fungsi roda mouse", wheel_box)
        self.controls["wheel_mode"] = wheel_box
        return group

    def _build_mirror_group(self) -> QGroupBox:
        group = QGroupBox("Mode Cermin && Bantuan Baca")
        form = QFormLayout(group)
        self._add_check(form, "Cermin kiri-kanan (kaca teleprompter)", "mirror_h")
        self._add_check(form, "Cermin atas-bawah", "mirror_v")
        self._add_check(form, "Tampilkan penanda baris baca", "show_guide")
        self._add_spin(form, "Posisi penanda", "guide_position", 5, 95, suffix=" % dari atas")
        self._add_check(form, "Tampilkan bar info (waktu, progres)", "show_info")
        return group

    def _build_screen_group(self) -> QGroupBox:
        group = QGroupBox("Layar")
        form = QFormLayout(group)

        screen_box = QComboBox()
        for i, screen in enumerate(QGuiApplication.screens()):
            size = screen.geometry()
            screen_box.addItem(f"Monitor {i + 1}  ({size.width()}x{size.height()})", i)
        screen_box.setCurrentIndex(min(self.settings.screen_index, screen_box.count() - 1))
        screen_box.currentIndexChanged.connect(lambda i: self._set("screen_index", i))
        form.addRow("Tampilkan di", screen_box)
        self.controls["screen_index"] = screen_box

        self._add_check(form, "Layar penuh", "fullscreen")
        return group

    # --- Pembuat widget pengaturan (supaya kode di atas tetap pendek) ---
    def _add_spin(self, form, label, name, minimum, maximum, suffix="", step=1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.setValue(getattr(self.settings, name))
        spin.valueChanged.connect(lambda value: self._set(name, value))
        form.addRow(label, spin)
        self.controls[name] = spin
        return spin

    def _add_check(self, form, label, name) -> QCheckBox:
        check = QCheckBox(label)
        check.setChecked(getattr(self.settings, name))
        check.toggled.connect(lambda value: self._set(name, value))
        form.addRow(check)
        self.controls[name] = check
        return check

    def _add_color(self, form, label, name) -> QPushButton:
        button = QPushButton()

        def pick_color():
            color = QColorDialog.getColor(QColor(getattr(self.settings, name)), self, label)
            if color.isValid():
                self._set(name, color.name())
                _paint_color_button(button, color.name())

        button.clicked.connect(pick_color)
        _paint_color_button(button, getattr(self.settings, name))
        form.addRow(label, button)
        self.controls[name] = button
        return button

    # ==================================================================
    # Pengaturan
    # ==================================================================
    def _set(self, name: str, value) -> None:
        """Ubah satu pengaturan, simpan, lalu terapkan ke layar baca."""
        setattr(self.settings, name, value)
        self.settings.save()
        if self.prompter:
            self.prompter.apply_settings(name)

    def _sync_controls(self) -> None:
        """Samakan isi panel dengan self.settings (mis. setelah diubah via keyboard)."""
        for name, widget in self.controls.items():
            value = getattr(self.settings, name)
            widget.blockSignals(True)
            if isinstance(widget, QSpinBox):
                widget.setValue(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, FontPicker):
                widget.select(value)
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif isinstance(widget, QPushButton):
                _paint_color_button(widget, value)
            widget.blockSignals(False)
        # slider kecepatan ikut menyesuaikan (tanpa memicu sinyal lagi)
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(self.settings.speed)
        self.speed_slider.blockSignals(False)

    def _on_prompter_settings_changed(self) -> None:
        self.settings.save()
        self._sync_controls()

    def reset_settings(self) -> None:
        self.settings.reset()
        self.settings.save()
        self._sync_controls()
        if self.prompter:
            self.prompter.apply_settings()

    # ==================================================================
    # Layar baca
    # ==================================================================
    def start_prompter(self) -> None:
        if self.prompter:   # sudah terbuka -> cukup tampilkan ke depan
            self.prompter.raise_()
            self.prompter.activateWindow()
            return

        self.prompter = PrompterWindow(self.settings, self.editor.toPlainText())
        self.prompter.settings_changed.connect(self._on_prompter_settings_changed)
        self.prompter.closed.connect(self._on_prompter_closed)

        screens = QGuiApplication.screens()
        screen = screens[min(self.settings.screen_index, len(screens) - 1)]
        self.prompter.setScreen(screen)
        # ukuran jendela biasa (70% layar, di tengah monitor yang dipilih)
        self.prompter.setGeometry(centered_rect(screen.geometry()))
        self.prompter.set_fullscreen(self.settings.fullscreen)

    def _on_prompter_closed(self) -> None:
        self.prompter = None
        self.activateWindow()

    # ==================================================================
    # Naskah & file
    # ==================================================================
    def _on_text_changed(self) -> None:
        self._update_stats()
        self._update_title()
        if self.prompter:
            self.prompter.set_text(self.editor.toPlainText())

    def _update_stats(self) -> None:
        text = self.editor.toPlainText()
        words = len(text.split())
        seconds = words / WORDS_PER_MINUTE * 60
        self.statusBar().showMessage(
            f"{words} kata  ·  {len(text)} karakter  ·  "
            f"perkiraan durasi bicara ±{format_time(seconds)} "
            f"({WORDS_PER_MINUTE} kata/menit)"
        )

    def _update_title(self) -> None:
        name = self.current_file.name if self.current_file else "Naskah tanpa nama"
        star = "*" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{star}{name} - {APP_TITLE}")

    def _confirm_discard(self) -> bool:
        """Tanya simpan jika file yang dibuka sudah diubah. True = boleh lanjut."""
        if not (self.current_file and self.editor.document().isModified()):
            return True
        answer = QMessageBox.question(
            self, APP_TITLE, f"Simpan perubahan pada {self.current_file.name}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file()
        return answer == QMessageBox.StandardButton.Discard

    def new_file(self) -> None:
        if not self._confirm_discard():
            return
        self.current_file = None
        self.editor.clear()
        self.editor.document().setModified(False)
        self._update_title()

    def open_file_dialog(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Buka Naskah", "", "File teks (*.txt *.md);;Semua file (*.*)"
        )
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        data = Path(path).read_bytes()
        # coba UTF-8 dulu, jika gagal pakai encoding Windows lama
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = data.decode("utf-8", errors="replace")

        self.current_file = Path(path)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self._update_title()

    def save_file(self) -> bool:
        if not self.current_file:
            return self.save_file_as()
        try:
            self.current_file.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, APP_TITLE, f"Gagal menyimpan file:\n{error}")
            return False
        self.editor.document().setModified(False)
        self._update_title()
        return True

    def save_file_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Naskah", "naskah.txt", "File teks (*.txt)")
        if not path:
            return False
        self.current_file = Path(path)
        return self.save_file()

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        if self.prompter:
            self.prompter.close()
        save_last_script(self.editor.toPlainText())
        self.settings.save()
        event.accept()


class FontPicker(QComboBox):
    """Pilihan jenis huruf. Daftar font Windows baru dimuat saat dropdown
    pertama kali dibuka, karena memuatnya butuh 1-3 detik (aplikasi jadi lambat dibuka)."""

    def __init__(self, family: str):
        super().__init__()
        self.loaded = False
        self.addItem(family)

    def select(self, family: str) -> None:
        if self.findText(family) < 0:
            self.addItem(family)
        self.setCurrentText(family)

    def showPopup(self) -> None:
        if not self.loaded:
            self.loaded = True
            current = self.currentText()
            self.blockSignals(True)
            self.clear()
            self.addItems(QFontDatabase.families())
            self.select(current)
            self.blockSignals(False)
        super().showPopup()


def _paint_color_button(button: QPushButton, color: str) -> None:
    """Tampilkan warna di tombol pemilih warna."""
    text_color = "#000000" if QColor(color).lightness() > 128 else "#FFFFFF"
    button.setText(color.upper())
    button.setStyleSheet(f"background: {color}; color: {text_color}; padding: 4px;")
