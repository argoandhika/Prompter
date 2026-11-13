# Copyright (c) 2026 Argo Andhika Nugroho
# Lisensi MIT - lihat file LICENSE. Nama pembuat wajib dicantumkan.
"""
control_bar.py
==============
Panel pengaturan SATU BARIS di bagian bawah layar baca, sehingga kecepatan,
ukuran huruf, cermin, dll. bisa diubah SAAT prompter sedang berjalan.

- Selalu tampil. Tekan S untuk sembunyikan/tampilkan; jika tersembunyi,
  arahkan mouse ke bagian bawah layar untuk memunculkannya lagi.
- Tidak ikut dicermin (panel ini untuk operator).
- Semua kontrol tidak mengambil fokus keyboard, jadi tombol Spasi/panah
  tetap bekerja untuk layar baca.

Menambah kontrol baru: tambahkan satu baris di __init__ memakai
_add_stepper / _add_toggle / _add_button.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider

from settings import format_time

STYLE = """
QFrame#controlBar { background: rgb(28, 28, 28); border-top: 1px solid #444; }
QLabel { color: #ddd; font-size: 14px; }
QLabel#value { color: #fff; font-weight: bold; min-width: 34px; qproperty-alignment: AlignCenter; }
QLabel#info { color: #aaa; font-size: 13px; }
QPushButton {
    color: #eee; background: #3a3a3a; border: 1px solid #555;
    border-radius: 4px; padding: 6px 10px; font-size: 14px;
}
QPushButton:hover { background: #4a4a4a; }
QPushButton:checked { background: #c62828; border-color: #e53935; }
QPushButton#play { background: #2e7d32; font-weight: bold; min-width: 80px; }
QPushButton#step { min-width: 22px; max-width: 22px; padding: 6px 4px; font-weight: bold; }
QSlider::groove:horizontal { height: 6px; background: #555; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #e53935; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -7px 0; background: #fff; border-radius: 9px; }
"""


class ControlBar(QFrame):
    def __init__(self, prompter):
        super().__init__(prompter)
        self.prompter = prompter
        self.settings = prompter.settings
        self.setObjectName("controlBar")
        self.setStyleSheet(STYLE)
        self.value_labels = {}   # nama pengaturan -> label angka
        self.toggles = {}        # nama pengaturan -> tombol on/off

        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(10, 6, 10, 6)
        self.row.setSpacing(4)

        # Mulai / jeda & ke awal
        self.play_button = self._add_button("▶ Mulai", prompter.toggle_play)
        self.play_button.setObjectName("play")
        self._add_button("⏮", prompter.go_to_start, "Ke awal naskah (Home)")
        self._gap()

        # Kecepatan: tombol − / slider / tombol +
        self.row.addWidget(QLabel("Kecepatan"))
        self._add_button("−", lambda: prompter.change_speed(-1), "Pelan (panah bawah)", "step")
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_slider.setMinimumWidth(120)
        self.speed_slider.valueChanged.connect(lambda v: prompter.set_setting("speed", v))
        self.row.addWidget(self.speed_slider, 1)
        self._add_button("+", lambda: prompter.change_speed(+1), "Cepat (panah atas)", "step")
        self.speed_label = QLabel()
        self.speed_label.setObjectName("value")
        self.row.addWidget(self.speed_label)
        self._gap()

        # Tampilan teks
        self._add_stepper("Huruf", "font_size", 8, 200, 4)
        self._add_stepper("Jarak", "line_spacing", 100, 300, 10, "%")
        self._add_stepper("Margin", "margin_percent", 0, 40, 2, "%")
        self._gap()

        # Cermin
        self._add_toggle("Cermin ↔", "mirror_h", "Balik kiri-kanan (M)")
        self._add_toggle("Cermin ↕", "mirror_v", "Balik atas-bawah (V)")
        self._gap()

        # Fungsi roda mouse: geser naskah <-> atur kecepatan
        self.wheel_button = self._add_button("", prompter.toggle_wheel_mode,
                                             "Fungsi roda mouse (W). Ctrl+roda = ukuran huruf")
        self._gap()

        # Info waktu & progres
        self.info_label = QLabel()
        self.info_label.setObjectName("info")
        self.row.addWidget(self.info_label)
        self._gap()

        self._add_button("⛶", prompter.toggle_fullscreen, "Layar penuh / jendela (F)")
        self._add_button("✕", prompter.close, "Tutup layar baca (Esc)")

        # Info waktu diperbarui 4x per detik
        self.info_timer = QTimer(self)
        self.info_timer.timeout.connect(self.update_info)
        self.info_timer.start(250)

        self.sync()

    # --- Pembuat kontrol ---
    def _add_button(self, text, handler=None, tooltip="", object_name="") -> QPushButton:
        button = QPushButton(text)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        if object_name:
            button.setObjectName(object_name)
        if handler:
            button.clicked.connect(handler)
        self.row.addWidget(button)
        return button

    def _add_stepper(self, label, name, minimum, maximum, step, suffix="") -> None:
        """Label + tombol − + angka + tombol +."""
        def change(delta):
            value = min(maximum, max(minimum, getattr(self.settings, name) + delta))
            self.prompter.set_setting(name, value)

        self.row.addWidget(QLabel(label))
        self._add_button("−", lambda: change(-step), object_name="step")
        value_label = QLabel()
        value_label.setObjectName("value")
        value_label.setProperty("suffix", suffix)
        self.row.addWidget(value_label)
        self._add_button("+", lambda: change(+step), object_name="step")
        self.row.addSpacing(6)
        self.value_labels[name] = value_label

    def _add_toggle(self, text, name, tooltip="") -> None:
        button = self._add_button(text, tooltip=tooltip)
        button.setCheckable(True)
        button.toggled.connect(lambda v: self.prompter.set_setting(name, v))
        self.toggles[name] = button

    def _gap(self) -> None:
        self.row.addSpacing(14)

    # --- Samakan tampilan panel dengan pengaturan & status terkini ---
    def sync(self) -> None:
        s = self.settings
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(s.speed)
        self.speed_slider.blockSignals(False)
        self.speed_label.setText(str(s.speed))

        for name, label in self.value_labels.items():
            label.setText(f"{getattr(s, name)}{label.property('suffix')}")
        for name, button in self.toggles.items():
            button.blockSignals(True)
            button.setChecked(getattr(s, name))
            button.blockSignals(False)

        self.play_button.setText("⏸ Jeda" if self.prompter.playing else "▶ Mulai")
        self.wheel_button.setText("🖱 Roda: Kecepatan" if s.wheel_mode == "kecepatan" else "🖱 Roda: Geser")
        self.update_info()

    def update_info(self) -> None:
        progress, remaining = self.prompter.progress_info()
        self.info_label.setText(
            f"{format_time(self.prompter.read_seconds)} · sisa ±{format_time(remaining)} · {progress * 100:.0f}%"
        )
