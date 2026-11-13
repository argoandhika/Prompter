# Copyright (c) 2026 Argo Andhika Nugroho
# Lisensi MIT - lihat file LICENSE. Nama pembuat wajib dicantumkan.
"""
prompter_window.py
==================
Layar baca (teleprompter) yang menampilkan naskah dan menggulirkannya.

Cara kerja singkat (kenapa gulirnya mulus):
  1. Naskah disusun oleh QTextDocument (huruf, wrap, jarak baris).
  2. Naskah dirender SEKALI menjadi potongan gambar ("tile") setinggi
     TILE_HEIGHT piksel. Tile hanya dibuat ulang jika pengaturan/naskah berubah.
  3. Layar digambar dengan OpenGL setiap ~8 ms (timer presisi). `offset`
     ditambah sesuai kecepatan x waktu yang benar-benar berlalu, lalu tile
     digambar di posisi pecahan piksel (sub-piksel) -> gerakan halus.
     Gulir manual (mouse/panah) meluncur halus lewat `scroll_remaining`.
  4. Mode cermin cukup dengan membalik "kanvas" (painter.scale(-1, 1)).

Tombol keyboard dijelaskan di HELP_LINES di bawah.
"""

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAbstractTextDocumentLayout,
    QColor,
    QCursor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPalette,
    QPolygonF,
    QSurfaceFormat,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from control_bar import ControlBar
from settings import APP_NAME, APP_VERSION, COPYRIGHT, SPEED_FACTOR, Settings, format_time

# Teks bantuan yang muncul saat menekan F1 / H
HELP_LINES = [
    ("S", "Sembunyikan / tampilkan panel bawah"),
    ("Spasi / Klik", "Mulai / jeda"),
    ("Panah Atas / Bawah", "Kecepatan +1 / -1 (Shift = 5)"),
    ("Panah Kiri / Kanan", "Mundur / maju satu baris"),
    ("Page Up / Page Down", "Mundur / maju satu layar"),
    ("Roda mouse", "Geser naskah / atur kecepatan (W = ganti)"),
    ("Ctrl + roda", "Perbesar / perkecil huruf"),
    ("Klik roda", "Auto-scroll: gerakkan mouse naik/turun"),
    ("Home / End", "Ke awal / ke akhir naskah"),
    ("+ / -", "Perbesar / perkecil huruf"),
    ("M", "Cermin kiri-kanan"),
    ("V", "Cermin atas-bawah"),
    ("G", "Tampilkan / sembunyikan penanda baca"),
    ("I", "Tampilkan / sembunyikan bar info"),
    ("F / F11", "Layar penuh / jendela"),
    ("F1 / H", "Tampilkan bantuan ini"),
    ("Esc", "Tutup layar baca"),
]

ALIGNMENTS = {
    "kiri": Qt.AlignmentFlag.AlignLeft,
    "tengah": Qt.AlignmentFlag.AlignHCenter,
    "rata": Qt.AlignmentFlag.AlignJustify,
}

UI_FONT = "Segoe UI"                # huruf untuk bar info, pesan, dan bantuan
GUIDE_COLOR = QColor(255, 70, 70)   # warna panah penanda baca
HUD_DURATION_MS = 1200              # lama pesan singkat (mis. "Jeda") tampil
TILE_HEIGHT = 256                   # tinggi satu potongan gambar naskah (piksel); kecil = render lebih ringan
FRAME_INTERVAL_MS = 8               # jarak antar frame animasi (~125 fps)
SCROLL_SPRING = 16                  # kekakuan "pegas" gulir manual: besar = cepat sampai, kecil = lebih lembut
WHEEL_STEP_LINES = 0.5              # 1 putaran roda mouse = setengah baris

# Auto-scroll ala browser (klik roda, lalu gerakkan mouse naik/turun)
AUTOSCROLL_DEAD_ZONE = 12           # jarak (piksel) dari titik jangkar yang belum menggulir
AUTOSCROLL_FACTOR = 5.0             # kecepatan = jarak mouse x faktor ini (piksel/detik)
AUTOSCROLL_MAX_SPEED = 4000         # batas kecepatan auto-scroll (piksel/detik)
AUTOSCROLL_SMOOTHING = 12           # makin besar makin cepat mengikuti gerakan mouse
CURSOR_HIDE_MS = 3000               # kursor mouse sembunyi setelah diam selama ini
SHOW_BAR_ZONE = 80                  # mouse di bawah layar (piksel) -> panel muncul lagi

# Pengaturan yang mengubah susunan baris -> naskah perlu disusun ulang
LAYOUT_SETTINGS = {"font_family", "font_size", "bold", "line_spacing", "margin_percent", "align",
                   "text_color"}


class PrompterWindow(QOpenGLWidget):
    # Dipancarkan saat pengaturan diubah lewat keyboard (agar panel editor ikut update)
    settings_changed = Signal()
    # Dipancarkan saat jendela ditutup
    closed = Signal()

    def __init__(self, settings: Settings, text: str):
        super().__init__()
        self.settings = settings   # objek yang SAMA dengan milik editor
        self.text = text

        self.setWindowTitle("Prompter - Layar Baca")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # Animasi digerakkan timer presisi (bukan VSync). VSync di sebagian laptop
        # bisa turun ke 5-20 fps (mode hemat daya / monitor tertentu) -> patah-patah.
        surface = QSurfaceFormat()
        surface.setSwapInterval(0)
        self.setFormat(surface)
        self.frame_timer = QTimer(self)
        self.frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.frame_timer.timeout.connect(self._on_frame_timer)
        self.frame_timer.start(FRAME_INTERVAL_MS)
        self.is_fullscreen = False
        self.normal_geometry = None   # ukuran jendela sebelum layar penuh

        # Dokumen teks + cache potongan gambar naskah
        self.doc = QTextDocument(self)
        self.doc.setDocumentMargin(0)
        self.doc.setUndoRedoEnabled(False)
        self.line_height = 50.0
        self.tiles: dict[int, QImage] = {}
        self.wanted_tiles: list[int] = []   # tile yang sebaiknya disiapkan lebih dulu

        # Status gulir
        self.offset = 0.0           # seberapa jauh naskah sudah bergulir (piksel)
        self.scroll_remaining = 0.0 # sisa gulir manual (mouse/panah) yang sedang meluncur
        self.scroll_velocity = 0.0  # kecepatan luncur gulir manual (piksel/detik)
        self.wheel_accum = 0        # sisa putaran roda (untuk mode kecepatan / mouse presisi tinggi)
        self.autoscroll_anchor = None   # titik klik roda (QPointF) saat auto-scroll aktif
        self.autoscroll_velocity = 0.0  # kecepatan auto-scroll saat ini (piksel/detik)
        self.autoscroll_started = 0     # waktu mulai (ms), untuk membedakan klik vs tahan-geser
        self.playing = False
        self.countdown_left = 0.0   # sisa hitung mundur (detik)
        self.read_seconds = 0.0     # total waktu berjalan
        self.show_help = False
        self.hud_text = ""          # pesan singkat di tengah layar
        self.hud_until = 0

        # Jam presisi tinggi untuk menghitung jarak waktu antar frame
        self.clock = QElapsedTimer()
        self.clock.start()
        self.last_frame_ns = self.clock.nsecsElapsed()

        # Panel pengaturan satu baris di bawah (lihat control_bar.py)
        self.control_bar = ControlBar(self)
        self.settings_changed.connect(self.control_bar.sync)

        # Kursor mouse disembunyikan otomatis saat mouse diam
        self.cursor_timer = QTimer(self)
        self.cursor_timer.setSingleShot(True)
        self.cursor_timer.timeout.connect(self._hide_cursor)
        self.cursor_timer.start(CURSOR_HIDE_MS)

        self.step = 1   # langkah perubahan kecepatan (5 jika Shift ditekan)
        self.key_actions = self._build_key_actions()
        self.rebuild_document()

    # ==================================================================
    # Fungsi yang dipanggil dari luar (editor)
    # ==================================================================
    def set_text(self, text: str) -> None:
        """Ganti isi naskah (dipanggil saat pengguna mengetik di editor)."""
        self.text = text
        self.rebuild_document()

    def apply_settings(self, name: str | None = None) -> None:
        """Terapkan pengaturan terbaru dari editor. `name` = pengaturan yang berubah
        (None = semua)."""
        self._refresh(name)
        self.control_bar.sync()

    def set_setting(self, name: str, value) -> None:
        """Ubah satu pengaturan dari panel bawah, lalu kabari editor."""
        setattr(self.settings, name, value)
        self._refresh(name)
        self.settings_changed.emit()

    def _refresh(self, name: str | None) -> None:
        """Naskah hanya disusun ulang jika perlu, agar gulir tidak tersendat."""
        if name is None or name in LAYOUT_SETTINGS:
            self.rebuild_document()
        else:
            self.update()

    # ==================================================================
    # Menyusun dokumen teks
    # ==================================================================
    def rebuild_document(self) -> None:
        """Susun ulang naskah sesuai pengaturan, posisi baca tetap dipertahankan."""
        old_height = self.doc.size().height()
        progress = self.offset / old_height if old_height > 0 else 0.0

        s = self.settings
        font = QFont(s.font_family)
        font.setPointSize(max(8, s.font_size))
        font.setBold(s.bold)
        self.doc.setDefaultFont(font)
        self.doc.setPlainText(self.text)

        # Jarak baris & perataan diterapkan ke seluruh paragraf
        block_format = QTextBlockFormat()
        block_format.setLineHeight(
            float(s.line_spacing), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        )
        block_format.setAlignment(ALIGNMENTS.get(s.align, Qt.AlignmentFlag.AlignLeft))
        cursor = QTextCursor(self.doc)
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(block_format)

        self.doc.setTextWidth(self._text_width())
        self.line_height = QFontMetricsF(font).lineSpacing() * s.line_spacing / 100

        self.tiles.clear()   # gambar lama sudah tidak berlaku
        self.offset = self._clamp_offset(progress * self.doc.size().height())
        self.update()

    def _text_width(self) -> float:
        margin = self.width() * self.settings.margin_percent / 100
        return max(100.0, self.width() - 2 * margin)

    def max_offset(self) -> float:
        """Offset maksimum: saat baris terakhir berada di penanda baca."""
        return max(0.0, self.doc.size().height() - self.line_height)

    def _clamp_offset(self, offset: float) -> float:
        """Batasi posisi gulir agar tidak lewat dari awal/akhir naskah."""
        return min(max(0.0, offset), self.max_offset())

    def progress_info(self) -> tuple[float, float]:
        """(progres 0-1, perkiraan sisa waktu dalam detik) untuk bar info & panel bawah."""
        max_offset = self.max_offset()
        progress = self.offset / max_offset if max_offset > 0 else 0.0
        speed_px = self.settings.speed * SPEED_FACTOR
        remaining = (max_offset - self.offset) / speed_px if speed_px > 0 else 0.0
        return progress, remaining

    def _get_tile(self, index: int) -> QImage:
        """Ambil potongan gambar naskah ke-`index` (dibuat jika belum ada)."""
        tile = self.tiles.get(index)
        if tile is not None:
            return tile

        ratio = self.devicePixelRatioF()   # agar tajam di layar dengan skala 125%/150%
        width = self._text_width()
        tile = QImage(math.ceil(width * ratio), math.ceil(TILE_HEIGHT * ratio),
                      QImage.Format.Format_ARGB32_Premultiplied)
        tile.setDevicePixelRatio(ratio)
        tile.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tile)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.translate(0, -index * TILE_HEIGHT)
        context = QAbstractTextDocumentLayout.PaintContext()
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Text, QColor(self.settings.text_color))
        context.palette = palette
        context.clip = QRectF(0, index * TILE_HEIGHT, width, TILE_HEIGHT)
        self.doc.documentLayout().draw(painter, context)
        painter.end()

        self.tiles[index] = tile
        return tile

    # ==================================================================
    # Kontrol gulir
    # ==================================================================
    def toggle_play(self) -> None:
        if self.playing:
            self.playing = False
            self.countdown_left = 0
            self._show_hud("Jeda")
            self.control_bar.sync()
            return

        if self.offset >= self.max_offset():
            self.offset = 0.0   # sudah di akhir -> ulang dari awal
            self.read_seconds = 0.0
        self.playing = True
        self.last_frame_ns = self.clock.nsecsElapsed()
        # Hitung mundur hanya jika mulai dari awal naskah
        self.countdown_left = float(self.settings.countdown) if self.offset <= 0 else 0.0
        if self.countdown_left == 0:
            self._show_hud("Jalan")
        self.control_bar.sync()
        self.update()

    def scroll_by(self, pixels: float) -> None:
        """Geser naskah langsung (tanpa animasi)."""
        self.scroll_remaining = 0.0
        self.scroll_velocity = 0.0
        self.offset = self._clamp_offset(self.offset + pixels)
        self.update()

    def smooth_scroll(self, pixels: float) -> None:
        """Geser naskah dengan meluncur halus (mouse, panah, Page Up/Down)."""
        already_moving = self._is_animating()
        self.scroll_remaining += pixels
        if not already_moving:
            # hanya "bangunkan" animasi jika sedang diam. Jika sudah bergerak, frame
            # terjadwal berikutnya akan memprosesnya; frame tambahan di luar jadwal
            # justru membuat satu refresh monitor terlewat (tersendat).
            self.last_frame_ns = self.clock.nsecsElapsed()
            self.update()

    def go_to_start(self) -> None:
        self.playing = False
        self.read_seconds = 0.0
        self.scroll_by(-self.offset)
        self._show_hud("Ke awal")
        self.control_bar.sync()

    def go_to_end(self) -> None:
        self.playing = False
        self.scroll_by(self.max_offset() - self.offset)
        self._show_hud("Ke akhir")
        self.control_bar.sync()

    def toggle_control_bar(self) -> None:
        self.control_bar.setVisible(not self.control_bar.isVisible())
        self.update()   # bar info gambar muncul/hilang mengikuti panel

    def _hide_cursor(self) -> None:
        if not self.control_bar.underMouse():
            self.setCursor(Qt.CursorShape.BlankCursor)

    def change_speed(self, delta: int) -> None:
        self.settings.speed = min(100, max(0, self.settings.speed + delta))
        self._show_hud(f"Kecepatan {self.settings.speed}")
        self.settings_changed.emit()

    def change_font_size(self, delta: int) -> None:
        self.settings.font_size = min(200, max(8, self.settings.font_size + delta))
        self.rebuild_document()
        self._show_hud(f"Ukuran huruf {self.settings.font_size}")
        self.settings_changed.emit()

    def toggle_setting(self, name: str, label: str) -> None:
        """Balik nilai pengaturan bertipe True/False, mis. mirror_h."""
        new_value = not getattr(self.settings, name)
        setattr(self.settings, name, new_value)
        self._show_hud(f"{label}: {'ON' if new_value else 'OFF'}")
        self.settings_changed.emit()

    def toggle_fullscreen(self) -> None:
        self.set_fullscreen(not self.is_fullscreen)

    def set_fullscreen(self, on: bool) -> None:
        """Layar penuh versi 'jendela tanpa bingkai seukuran monitor'.

        Fullscreen asli (showFullScreen) pada jendela OpenGL membuat Windows
        memakai mode eksklusif; di monitor utama tampilannya bisa macet.
        Tinggi +1 piksel mencegah Windows mendeteksinya sebagai fullscreen eksklusif.
        """
        center = self.geometry().center()
        screen = QGuiApplication.screenAt(center) or self.screen()
        area = screen.geometry()
        if on:
            if not self.is_fullscreen:
                self.normal_geometry = self.geometry()
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
            self.setGeometry(area.x(), area.y(), area.width(), area.height() + 1)
        else:
            self.setWindowFlags(Qt.WindowType.Window)
            if self.normal_geometry and self.normal_geometry.width() < area.width():
                self.setGeometry(self.normal_geometry)
            else:
                self.setGeometry(centered_rect(area))
        self.is_fullscreen = on
        self.show()
        self.activateWindow()
        self.setFocus()

    def toggle_help(self) -> None:
        self.show_help = not self.show_help
        self.update()

    def close_help_or_window(self) -> None:
        if self.autoscroll_anchor is not None:
            self._stop_autoscroll()
        elif self.show_help:
            self.toggle_help()
        else:
            self.close()

    def _show_hud(self, text: str) -> None:
        self.hud_text = text
        self.hud_until = self.clock.elapsed() + HUD_DURATION_MS
        self.update()

    # ==================================================================
    # Animasi (dijalankan setiap frame, ~125x per detik)
    # ==================================================================
    def _frame_seconds(self) -> float:
        """Waktu animasi (detik) sejak frame sebelumnya, DIBULATKAN ke kelipatan
        refresh monitor (mis. 16,7 ms di 60 Hz).

        Monitor hanya menampilkan gambar setiap refresh. Jika posisi dihitung pada
        waktu acak (mis. frame tambahan karena putaran roda), jarak gerak antar
        gambar yang tampil jadi tidak rata -> terasa tersendat. Dengan pembulatan,
        setiap gambar yang tampil bergeser tepat sesuai 1 refresh.
        """
        refresh = self.screen().refreshRate() if self.screen() else 60.0
        frame_ns = 1e9 / max(refresh, 24.0)
        now = self.clock.nsecsElapsed()
        elapsed = now - self.last_frame_ns

        if elapsed > 1e8:                      # lebih dari 0,1 detik diam -> mulai baru
            self.last_frame_ns = now
            return frame_ns / 1e9
        frames = round(elapsed / frame_ns)     # 0 = masih di refresh yang sama
        if frames > 0:
            self.last_frame_ns += frames * frame_ns
            # koreksi kecil agar jam animasi tidak pelan-pelan bergeser dari jam monitor
            self.last_frame_ns += (now - self.last_frame_ns) * 0.1
        return frames * frame_ns / 1e9

    def _advance(self) -> None:
        dt = self._frame_seconds()
        self._advance_manual_scroll(dt)
        self._advance_autoscroll(dt)
        if self.playing and self.countdown_left > 0:
            self.countdown_left = max(0.0, self.countdown_left - dt)
        elif self.playing:
            self.offset += self.settings.speed * SPEED_FACTOR * dt
            self.read_seconds += dt
            if self.offset >= self.max_offset():
                self.offset = self.max_offset()
                self.playing = False
                self._show_hud("Selesai")
                self.control_bar.sync()

        if self.hud_text and self.clock.elapsed() > self.hud_until:
            self.hud_text = ""

    def _advance_manual_scroll(self, dt: float) -> None:
        """Gulir manual meluncur seperti pegas: kecepatannya naik-turun bertahap
        (tidak pernah melompat), jadi putaran roda beruntun tetap tersambung mulus."""
        if not (self.scroll_remaining or self.scroll_velocity):
            return
        w = SCROLL_SPRING
        steps = max(1, math.ceil(dt * 240))   # dipecah kecil-kecil agar perhitungan stabil
        h = dt / steps
        for _ in range(steps):
            # pegas teredam kritis: tarik ke tujuan, rem sesuai kecepatan
            accel = w * w * self.scroll_remaining - 2 * w * self.scroll_velocity
            self.scroll_velocity += accel * h
            step = self.scroll_velocity * h
            self.scroll_remaining -= step
            new_offset = self._clamp_offset(self.offset + step)
            if new_offset != self.offset + step:   # mentok di awal/akhir naskah
                self.scroll_remaining = self.scroll_velocity = 0.0
            self.offset = new_offset

        if abs(self.scroll_remaining) < 0.2 and abs(self.scroll_velocity) < 5:
            self.offset = self._clamp_offset(self.offset + self.scroll_remaining)
            self.scroll_remaining = self.scroll_velocity = 0.0

    def _is_animating(self) -> bool:
        return bool(self.playing or self.hud_text or self.scroll_remaining or self.scroll_velocity
                    or self.autoscroll_anchor is not None)

    # ------------------------------------------------------------------
    # Auto-scroll ala browser: klik roda -> gerakkan mouse naik/turun
    # ------------------------------------------------------------------
    def _start_autoscroll(self, pos: QPointF) -> None:
        self.autoscroll_anchor = QPointF(pos)
        self.autoscroll_velocity = 0.0
        self.autoscroll_started = self.clock.elapsed()
        self.cursor_timer.stop()
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.last_frame_ns = self.clock.nsecsElapsed()
        self.update()

    def _stop_autoscroll(self) -> None:
        self.autoscroll_anchor = None
        self.autoscroll_velocity = 0.0
        self.unsetCursor()
        self.cursor_timer.start(CURSOR_HIDE_MS)
        self.update()

    def _cursor_y(self) -> float:
        """Posisi kursor saat ini (koordinat jendela), dibaca langsung dari sistem
        sehingga tetap terbaca walau kursor berada di atas panel bawah / di luar jendela."""
        return self.mapFromGlobal(QCursor.pos()).y()

    def _autoscroll_target_speed(self) -> float:
        """Kecepatan tujuan (piksel/detik) dari jarak mouse ke titik jangkar."""
        distance = self._cursor_y() - self.autoscroll_anchor.y()
        if abs(distance) <= AUTOSCROLL_DEAD_ZONE:
            return 0.0
        speed = (abs(distance) - AUTOSCROLL_DEAD_ZONE) * AUTOSCROLL_FACTOR
        # mouse di bawah titik klik = naskah maju, di atas = mundur (apa pun mode cerminnya)
        return min(speed, AUTOSCROLL_MAX_SPEED) * (1 if distance > 0 else -1)

    def _advance_autoscroll(self, dt: float) -> None:
        if self.autoscroll_anchor is None:
            return
        # kecepatan mengikuti mouse secara bertahap (tidak melompat) -> mulus
        target = self._autoscroll_target_speed()
        self.autoscroll_velocity += (target - self.autoscroll_velocity) * (1 - math.exp(-dt * AUTOSCROLL_SMOOTHING))
        self.offset = self._clamp_offset(self.offset + self.autoscroll_velocity * dt)

    def _on_frame_timer(self) -> None:
        """Minta frame baru hanya jika ada yang bergerak (hemat CPU saat diam)."""
        if self._is_animating():
            self.update()

    # ==================================================================
    # Menggambar layar
    # ==================================================================
    def paintGL(self) -> None:
        self._advance()

        s = self.settings
        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)  # posisi sub-piksel
        painter.fillRect(self.rect(), QColor(s.bg_color))

        # Mode cermin: balik seluruh kanvas. Semua yang digambar setelah ini ikut terbalik.
        if s.mirror_h:
            painter.translate(w, 0)
            painter.scale(-1, 1)
        if s.mirror_v:
            painter.translate(0, h)
            painter.scale(1, -1)

        guide_y = h * s.guide_position / 100
        self._draw_script(painter, w, h, guide_y)
        if s.show_guide:
            self._draw_guide(painter, w, guide_y)
        if s.show_info and not self.control_bar.isVisible():   # panel bawah sudah memuat info
            self._draw_info_bar(painter, w, h)
        if self.playing and self.countdown_left > 0:
            self._draw_countdown(painter, w, h)
        if self.hud_text:
            self._draw_hud(painter, w, h)
        painter.resetTransform()   # di bawah ini untuk operator -> selalu tidak dicermin
        if self.autoscroll_anchor is not None:
            self._draw_autoscroll_anchor(painter)
        if self.show_help:
            self._draw_help(painter, w, h)
        painter.end()

    def _draw_autoscroll_anchor(self, painter: QPainter) -> None:
        """Ikon jangkar auto-scroll (lingkaran + panah atas/bawah), seperti di browser."""
        c = self.autoscroll_anchor
        painter.setPen(QColor(60, 60, 60))
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawEllipse(c, 16, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(40, 40, 40))
        painter.drawEllipse(c, 2.5, 2.5)
        for direction in (-1, 1):   # panah atas & bawah
            tip = c.y() + direction * 12
            base = c.y() + direction * 6
            painter.drawPolygon(QPolygonF([QPointF(c.x(), tip), QPointF(c.x() - 5, base), QPointF(c.x() + 5, base)]))

    def _draw_script(self, painter: QPainter, w: int, h: int, guide_y: float) -> None:
        left = (w - self._text_width()) / 2
        # baris pertama dimulai tepat di penanda baca
        top = guide_y - self.line_height / 2 - self.offset

        # tile mana saja yang terlihat di layar
        first = max(0, math.floor(-top / TILE_HEIGHT))
        last = math.floor((h - top) / TILE_HEIGHT)
        last_in_doc = math.floor(self.doc.size().height() / TILE_HEIGHT)

        for index in range(first, min(last, last_in_doc) + 1):
            painter.drawImage(QPointF(left, top + index * TILE_HEIGHT), self._get_tile(index))

        # Tile di depan (±1 layar) disiapkan DI SELA-SELA frame, bukan di tengah
        # frame, supaya gulir tidak tersendat saat melewati batas tile.
        ahead = math.ceil(h / TILE_HEIGHT) + 1
        self.wanted_tiles = [i for i in [*range(last + 1, last + 1 + ahead), first - 1, first - 2]
                             if 0 <= i <= last_in_doc]
        if any(i not in self.tiles for i in self.wanted_tiles):
            QTimer.singleShot(0, self._prepare_one_tile)

        # buang tile yang sudah jauh tertinggal / terlalu jauh di depan (hemat memori)
        for index in [i for i in self.tiles if i < first - 3 or i > last + ahead + 1]:
            del self.tiles[index]

    def _prepare_one_tile(self) -> None:
        """Render satu tile yang belum siap (dipanggil setelah frame selesai digambar)."""
        for index in self.wanted_tiles:
            if index not in self.tiles:
                self._get_tile(index)
                return

    def _draw_guide(self, painter: QPainter, w: int, guide_y: float) -> None:
        # pita transparan tipis di baris yang sedang dibaca
        band = QColor(self.settings.text_color)
        band.setAlpha(25)
        painter.fillRect(QRectF(0, guide_y - self.line_height / 2, w, self.line_height), band)

        # panah di kiri dan kanan
        size = max(12.0, min(self.line_height * 0.5, 40.0))
        left_arrow = QPolygonF([
            QPointF(6, guide_y - size / 2), QPointF(6 + size, guide_y), QPointF(6, guide_y + size / 2)
        ])
        right_arrow = QPolygonF([
            QPointF(w - 6, guide_y - size / 2), QPointF(w - 6 - size, guide_y), QPointF(w - 6, guide_y + size / 2)
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(GUIDE_COLOR)
        painter.drawPolygon(left_arrow)
        painter.drawPolygon(right_arrow)

    def _draw_info_bar(self, painter: QPainter, w: int, h: int) -> None:
        progress, remaining = self.progress_info()

        # latar bar info agar tidak tertimpa naskah
        strip = QColor(self.settings.bg_color)
        strip.setAlpha(230)
        painter.fillRect(QRectF(0, h - 38, w, 38), strip)

        # garis progres di paling bawah
        painter.fillRect(QRectF(0, h - 5, w, 5), QColor(80, 80, 80))
        painter.fillRect(QRectF(0, h - 5, w * progress, 5), GUIDE_COLOR)

        status = "BERJALAN" if self.playing else "JEDA"
        info = (
            f"{status}   |   Waktu {format_time(self.read_seconds)}   |   "
            f"Sisa ±{format_time(remaining)}   |   Kecepatan {self.settings.speed}   |   "
            f"{progress * 100:.0f}%   |   S = panel pengaturan   |   F1 = bantuan"
        )
        painter.setFont(_ui_font(16))
        painter.setPen(QColor(160, 160, 160))
        painter.drawText(QRectF(0, h - 32, w, 24), Qt.AlignmentFlag.AlignCenter, info)

    def _draw_countdown(self, painter: QPainter, w: int, h: int) -> None:
        painter.setFont(_ui_font(int(min(w, h) / 3), bold=True))
        painter.setPen(GUIDE_COLOR)
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                         str(math.ceil(self.countdown_left)))

    def _draw_hud(self, painter: QPainter, w: int, h: int) -> None:
        box = QRectF(w / 2 - 200, h - 110, 400, 56)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 190))
        painter.drawRoundedRect(box, 12, 12)
        painter.setFont(_ui_font(28, bold=True))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, self.hud_text)

    def _draw_help(self, painter: QPainter, w: int, h: int) -> None:
        row_h = 34
        box_w, box_h = 640, row_h * len(HELP_LINES) + 115
        box = QRectF((w - box_w) / 2, (h - box_h) / 2, box_w, box_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 20, 250))
        painter.drawRoundedRect(box, 14, 14)

        painter.setFont(_ui_font(22, bold=True))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(box.left(), box.top() + 12, box_w, 36),
                         Qt.AlignmentFlag.AlignCenter, "Tombol Pintas")

        y = box.top() + 60
        for key, description in HELP_LINES:
            painter.setFont(_ui_font(18, bold=True))
            painter.setPen(GUIDE_COLOR)
            painter.drawText(QRectF(box.left() + 30, y, 250, row_h), Qt.AlignmentFlag.AlignVCenter, key)
            painter.setFont(_ui_font(18))
            painter.setPen(QColor(230, 230, 230))
            painter.drawText(QRectF(box.left() + 290, y, box_w - 310, row_h),
                             Qt.AlignmentFlag.AlignVCenter, description)
            y += row_h

        painter.setFont(_ui_font(14))
        painter.setPen(QColor(140, 140, 140))
        painter.drawText(QRectF(box.left(), y + 8, box_w, 24), Qt.AlignmentFlag.AlignCenter,
                         f"{APP_NAME} {APP_VERSION}  ·  {COPYRIGHT}")

    # ==================================================================
    # Input keyboard & mouse
    # ==================================================================
    def _build_key_actions(self) -> dict:
        """Daftar tombol -> fungsi. Tambah tombol baru cukup di sini (+ HELP_LINES)."""
        K = Qt.Key
        return {
            K.Key_Space: self.toggle_play,
            K.Key_Up: lambda: self.change_speed(+self.step),
            K.Key_Down: lambda: self.change_speed(-self.step),
            K.Key_Left: lambda: self.smooth_scroll(-self.line_height),
            K.Key_Right: lambda: self.smooth_scroll(+self.line_height),
            K.Key_PageUp: lambda: self.smooth_scroll(-self.height() * 0.7),
            K.Key_PageDown: lambda: self.smooth_scroll(+self.height() * 0.7),
            K.Key_Home: self.go_to_start,
            K.Key_End: self.go_to_end,
            K.Key_Plus: lambda: self.change_font_size(+4),
            K.Key_Equal: lambda: self.change_font_size(+4),
            K.Key_Minus: lambda: self.change_font_size(-4),
            K.Key_Underscore: lambda: self.change_font_size(-4),
            K.Key_M: lambda: self.toggle_setting("mirror_h", "Cermin kiri-kanan"),
            K.Key_V: lambda: self.toggle_setting("mirror_v", "Cermin atas-bawah"),
            K.Key_G: lambda: self.toggle_setting("show_guide", "Penanda baca"),
            K.Key_I: lambda: self.toggle_setting("show_info", "Bar info"),
            K.Key_F: self.toggle_fullscreen,
            K.Key_F11: self.toggle_fullscreen,
            K.Key_F1: self.toggle_help,
            K.Key_H: self.toggle_help,
            K.Key_S: self.toggle_control_bar,
            K.Key_W: self.toggle_wheel_mode,
            K.Key_Escape: self.close_help_or_window,
        }

    def keyPressEvent(self, event) -> None:
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.step = 5 if shift else 1
        action = self.key_actions.get(event.key())
        if action:
            action()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.autoscroll_anchor is not None:
            self._stop_autoscroll()        # klik apa saja saat auto-scroll = berhenti
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._start_autoscroll(event.position())
        elif event.button() == Qt.MouseButton.LeftButton:
            self.toggle_play()

    def mouseReleaseEvent(self, event) -> None:
        # gaya "tahan roda sambil geser": lepas tombol = berhenti
        # (klik singkat tetap aktif sampai klik berikutnya, seperti di browser)
        if event.button() == Qt.MouseButton.MiddleButton and self.autoscroll_anchor is not None:
            held_ms = self.clock.elapsed() - self.autoscroll_started
            moved = abs(event.position().y() - self.autoscroll_anchor.y()) > AUTOSCROLL_DEAD_ZONE
            if held_ms > 400 and moved:
                self._stop_autoscroll()

    def mouseMoveEvent(self, event) -> None:
        if self.autoscroll_anchor is not None:
            return                          # kursor ↕ tetap tampil selama auto-scroll
        self.unsetCursor()
        self.cursor_timer.start(CURSOR_HIDE_MS)
        # panel tersembunyi + mouse diarahkan ke bawah layar -> tampilkan lagi
        if not self.control_bar.isVisible() and event.position().y() > self.height() - SHOW_BAR_ZONE:
            self.toggle_control_bar()

    def wheelEvent(self, event) -> None:
        """Roda mouse:
        - biasa  : geser naskah ATAU atur kecepatan (pilih di pengaturan "Fungsi roda mouse")
        - Ctrl   : perbesar / perkecil huruf
        - Shift  : kebalikan dari mode yang dipilih
        """
        modifiers = event.modifiers()
        delta = event.angleDelta().y()   # 120 = satu "klik" putaran roda

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._wheel_clicks(delta, lambda n: self.change_font_size(2 * n))
            return

        mode = self.settings.wheel_mode
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mode = "geser" if mode == "kecepatan" else "kecepatan"
            delta = delta or event.angleDelta().x()   # sebagian mouse mengirim Shift+roda sebagai horizontal

        if mode == "kecepatan":
            # roda ke bawah = lebih cepat, ke atas = lebih pelan
            self._wheel_clicks(delta, lambda n: self.change_speed(-n))
        elif not event.pixelDelta().isNull():
            self.scroll_by(-event.pixelDelta().y())   # touchpad: ikuti jari langsung
        else:
            self.smooth_scroll(-delta / 120 * self.line_height * WHEEL_STEP_LINES)

    def _wheel_clicks(self, delta: int, action) -> None:
        """Ubah putaran roda menjadi 'klik' utuh (mouse presisi tinggi mengirim pecahan)."""
        self.wheel_accum += delta
        clicks = int(self.wheel_accum / 120)
        if clicks:
            self.wheel_accum -= clicks * 120
            action(clicks)

    def toggle_wheel_mode(self) -> None:
        new_mode = "kecepatan" if self.settings.wheel_mode == "geser" else "geser"
        self.set_setting("wheel_mode", new_mode)
        self._show_hud(f"Roda mouse: {'atur kecepatan' if new_mode == 'kecepatan' else 'geser naskah'}")

    def resizeGL(self, w: int, h: int) -> None:
        self.rebuild_document()   # lebar berubah -> susun ulang baris
        bar_height = self.control_bar.sizeHint().height()
        hidden_pixel = 1 if self.is_fullscreen else 0   # lihat set_fullscreen()
        self.control_bar.setGeometry(0, self.height() - bar_height - hidden_pixel, self.width(), bar_height)

    def closeEvent(self, event) -> None:
        self.playing = False
        self.frame_timer.stop()
        self.cursor_timer.stop()
        self.control_bar.info_timer.stop()
        self.closed.emit()
        super().closeEvent(event)


def centered_rect(area: QRect, fraction: float = 0.7) -> QRect:
    """Kotak seukuran `fraction` dari `area` (mis. 70% layar), tepat di tengahnya."""
    w, h = int(area.width() * fraction), int(area.height() * fraction)
    return QRect(area.x() + (area.width() - w) // 2, area.y() + (area.height() - h) // 2, w, h)


def _ui_font(pixel_size: int, bold: bool = False) -> QFont:
    font = QFont(UI_FONT)
    font.setPixelSize(max(1, pixel_size))
    font.setBold(bold)
    return font
