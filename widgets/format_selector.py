from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

import theme
from widgets.common import ElidedLabel, Segmented, section_label

MODES = ("Video", "Audio", "Thumbnail")


class _StreamTable(QTableWidget):
    """Table that shows a quiet message while empty."""

    empty_text = "Streams appear here after fetching"

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(theme.color("text3")))
            p.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, self.empty_text)
            p.end()

    def snapped_height(self, available):
        """Largest height <= ``available`` that shows only whole rows."""
        chrome = self.horizontalHeader().height() + 2 * self.frameWidth()
        hbar = self.horizontalScrollBar()
        if hbar.isVisible():
            chrome += hbar.height()
        row = self.verticalHeader().defaultSectionSize()
        rows = max(2, (available - chrome) // row)
        return chrome + rows * row


class _TableHolder(QWidget):
    """Lays out the stream table and the 'Selected' row below it.

    The table height is snapped to a whole number of rows so the last
    visible row is never cut in half by the frame; the remainder (< one
    row) is left as space below the 'Selected' row.
    """

    GAP = 8

    def __init__(self, table, footer, parent=None):
        super().__init__(parent)
        self.table = table
        self.footer = footer
        table.setParent(self)
        footer.setParent(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(table.snapped_height(0) + self.GAP + footer.sizeHint().height())
        # A horizontal scrollbar appearing/disappearing changes the chrome.
        table.horizontalScrollBar().rangeChanged.connect(lambda *_: self._relayout())

    def sizeHint(self):
        return QSize(400, 320)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        w, h = self.width(), self.height()
        fh = self.footer.sizeHint().height()
        th = self.table.snapped_height(h - self.GAP - fh)
        self.table.setGeometry(0, 0, w, th)
        self.footer.setGeometry(0, th + self.GAP, w, fh)


def _combo(min_width=0):
    c = QComboBox()
    c.setCursor(Qt.CursorShape.PointingHandCursor)
    theme.polish_combo(c)
    if min_width:
        c.setMinimumWidth(min_width)
    return c


def _field(label, widget):
    """Label above a control, as one vertical block."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(section_label(label))
    lay.addWidget(widget)
    return box


class FormatSelector(QWidget):
    format_selected = pyqtSignal(dict)
    mode_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.formats = []
        self._mode_before_audio_only = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Mode switch + per-mode options on one row.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(16)

        self.mode_switch = Segmented(MODES, button_width=88)
        self.mode_switch.group.idToggled.connect(self._on_mode_toggled)
        top.addWidget(_field("Mode", self.mode_switch), 0, Qt.AlignmentFlag.AlignBottom)

        self.options_stack = QStackedWidget()
        self.options_stack.addWidget(self._create_video_options())
        self.options_stack.addWidget(self._create_audio_options())
        self.options_stack.addWidget(self._create_thumbnail_options())
        top.addWidget(self.options_stack, 1, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(top)

        # Format table (optional manual pick of a specific stream).
        self.formats_box = QWidget()
        fb = QVBoxLayout(self.formats_box)
        fb.setContentsMargins(0, 0, 0, 0)
        fb.setSpacing(8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(section_label("Streams"))
        head.addStretch(1)
        hint = QLabel("Optional: pick a specific stream, otherwise the quality above is used")
        hint.setObjectName("Faint")
        head.addWidget(hint)
        fb.addLayout(head)

        self.format_table = _StreamTable()
        self.format_table.setObjectName("FormatTable")
        self.format_table.setColumnCount(7)
        self.format_table.setHorizontalHeaderLabels([
            "RESOLUTION", "FPS", "VIDEO CODEC", "AUDIO CODEC", "SIZE", "TYPE", "ID",
        ])
        header = self.format_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in range(6):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setFixedHeight(30)
        vh = self.format_table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(28)
        self.format_table.setShowGrid(False)
        self.format_table.setWordWrap(False)
        self.format_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.format_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.format_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.format_table.setAlternatingRowColors(True)
        self.format_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        # Scroll by whole rows so the snapped table never shows a half row.
        self.format_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.format_table.itemSelectionChanged.connect(self._on_selection_changed)

        sel_row = QWidget()
        sel = QHBoxLayout(sel_row)
        sel.setContentsMargins(0, 0, 0, 0)
        sel.setSpacing(8)
        sel.addWidget(section_label("Selected"))
        self.selected_label = ElidedLabel("Automatic")
        self.selected_label.setObjectName("Muted")
        sel.addWidget(self.selected_label, 1)
        fb.addWidget(_TableHolder(self.format_table, sel_row), 1)

        layout.addWidget(self.formats_box, 1)

    def _create_video_options(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        # Narrow minimum so the row fits the smallest window; grows (up to
        # 280px) when there is room for long labels like "1080p60 Full HD".
        self.video_quality = _combo(180)
        self.video_quality.setMaximumWidth(280)
        self.video_quality.currentIndexChanged.connect(self._on_video_quality_changed)
        self._reset_quality_combo()
        quality_field = _field("Quality", self.video_quality)
        quality_field.setMaximumWidth(280)
        quality_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(quality_field, 4)

        # A lone QRadioButton can never be unchecked again; use a checkbox.
        # Short label: the row (mode switch + quality + this) must fit the
        # narrowest workspace without clipping; details live in the tooltip.
        self.h264_check = QCheckBox("Prefer H.264")
        self.h264_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.h264_check.setToolTip(
            "Prefer H.264/AAC streams for maximum compatibility when they exist at the "
            "selected resolution. YouTube only offers H.264 up to 1080p, so higher "
            "resolutions use VP9 or AV1."
        )
        self.h264_check.setFixedHeight(30)
        lay.addWidget(self.h264_check, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addStretch(1)
        return w

    def _create_audio_options(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        self.audio_format = _combo(120)
        self.audio_format.addItems(["MP3", "M4A", "OPUS", "WAV", "FLAC"])
        lay.addWidget(_field("Format", self.audio_format))

        self.audio_bitrate = _combo(120)
        for kbps in ("128", "192", "256", "320"):
            self.audio_bitrate.addItem(f"{kbps} kbps", kbps)
        self.audio_bitrate.setCurrentIndex(1)
        lay.addWidget(_field("Bitrate", self.audio_bitrate))
        lay.addStretch(1)
        return w

    def _create_thumbnail_options(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        self.thumb_format = _combo(200)
        self.thumb_format.addItems(["Original (WebP/JPG)", "PNG", "JPG"])
        lay.addWidget(_field("Save as", self.thumb_format))
        lay.addStretch(1)
        return w

    # ----------------------------------------------------------------- mode

    def _on_mode_toggled(self, idx, checked):
        if not checked:
            return
        self.options_stack.setCurrentIndex(idx)
        # The stream table only applies to video downloads.
        self.formats_box.setEnabled(idx == 0)
        self.mode_changed.emit(idx)

    def get_mode(self):
        return max(0, self.mode_switch.index())

    # ------------------------------------------------------------- formats

    def set_formats(self, formats, qualities=None, generic_fallback=True, has_video=True):
        self.formats = formats
        self._populate_table(formats)
        if qualities is None:
            qualities = self._qualities_from_formats(formats)
        self.set_qualities(qualities, generic_fallback)
        self.set_has_video(has_video)

    def set_has_video(self, has_video):
        """Audio-only sources (SoundCloud, Bandcamp...) can't be saved as video."""
        video_btn = self.mode_switch.buttons[0]
        video_btn.setEnabled(has_video)
        video_btn.setToolTip("" if has_video else "This link has no video, only audio")
        if not has_video and self.get_mode() == 0:
            self._mode_before_audio_only = 0
            self.mode_switch.set_index(1)
        elif has_video and getattr(self, "_mode_before_audio_only", None) is not None:
            self.mode_switch.set_index(self._mode_before_audio_only)
            self._mode_before_audio_only = None

    def set_qualities(self, qualities, generic_fallback=True):
        """Populate the quality dropdown with only the heights available."""
        if not qualities and generic_fallback:
            # No per-format info (e.g. some playlists): fall back to a generic
            # list; the download format string degrades gracefully anyway.
            qualities = [{"height": h} for h in (2160, 1440, 1080, 720, 480, 360)]
        # Sites that don't report heights only get "Best available".
        qualities = qualities or []
        self.video_quality.blockSignals(True)
        self.video_quality.clear()
        self.video_quality.addItem("Best available", 0)
        for q in qualities:
            self.video_quality.addItem(self._quality_label(q), q["height"])

        # Default: highest quality up to 1080p, otherwise Best available
        default_index = 0
        for i in range(1, self.video_quality.count()):
            if self.video_quality.itemData(i) <= 1080:
                default_index = i
                break
        self.video_quality.setCurrentIndex(default_index)
        self.video_quality.setEnabled(True)
        self.video_quality.blockSignals(False)
        self._on_video_quality_changed(default_index)

    def _reset_quality_combo(self):
        self.video_quality.blockSignals(True)
        self.video_quality.clear()
        self.video_quality.addItem("Fetch a video first", 0)
        self.video_quality.setCurrentIndex(0)
        self.video_quality.setEnabled(False)
        self.video_quality.blockSignals(False)

    @staticmethod
    def _qualities_from_formats(formats):
        by_height = {}
        for fmt in formats:
            height = fmt.get("height", 0)
            if not height or fmt.get("fmt_type") == "audio-only":
                continue
            entry = by_height.setdefault(height, {"height": height, "fps": 0, "filesize": 0})
            try:
                entry["fps"] = max(entry["fps"], int(fmt.get("fps", 0)))
            except (TypeError, ValueError):
                pass
        return sorted(by_height.values(), key=lambda q: -q["height"])

    @staticmethod
    def _quality_label(q):
        names = {4320: "8K", 2160: "4K", 1440: "QHD", 1080: "Full HD", 720: "HD"}
        height = q["height"]
        fps = q.get("fps", 0)
        label = f"{height}p"
        if fps and fps > 30:
            label += f"{fps}"
        if height in names:
            label += f"  {names[height]}"
        size = q.get("filesize", 0)
        if size:
            label += f"  ~{FormatSelector._format_size(size)}"
        return label

    @staticmethod
    def _format_size(size_bytes):
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _populate_table(self, formats):
        self.format_table.clearSelection()
        self.format_table.setRowCount(0)
        self.format_table.setRowCount(len(formats))
        num_font = theme.tabular(self.format_table.font())
        for row, fmt in enumerate(formats):
            items = [
                fmt.get("resolution", "N/A"),
                fmt.get("fps", "N/A"),
                fmt.get("vcodec", "-"),
                fmt.get("acodec", "-"),
                fmt.get("filesize_str", "N/A"),
                fmt.get("fmt_type", ""),
                fmt.get("format_id", ""),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setFont(num_font)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.format_table.setItem(row, col, item)
        self.format_table.resizeColumnsToContents()
        self.selected_label.setText("Automatic")

    def _on_selection_changed(self):
        fmt = self.get_selected_format()
        if fmt:
            self.selected_label.setText(
                f"{fmt['resolution']}  {fmt['ext']}  {fmt['fmt_type']}  {fmt['filesize_str']}"
                f"  (id {fmt['format_id']})"
            )
            self.format_selected.emit(fmt)
        else:
            self.selected_label.setText("Automatic")

    def _on_video_quality_changed(self, index):
        max_height = self.video_quality.itemData(index) or 0
        for row in range(self.format_table.rowCount()):
            height_item = self.format_table.item(row, 0)
            if height_item:
                text = height_item.text().replace("p", "")
                try:
                    h = int(text)
                    self.format_table.setRowHidden(row, h > max_height and max_height > 0)
                except ValueError:
                    self.format_table.setRowHidden(row, False)
        self._on_selection_changed()

    def get_selected_format(self):
        model = self.format_table.selectionModel()
        rows = model.selectedRows() if model else []
        if rows:
            row = rows[0].row()
            # Ignore a selection that the quality filter has since hidden.
            if row < len(self.formats) and not self.format_table.isRowHidden(row):
                return self.formats[row]
        return None

    def get_video_options(self):
        return {
            "max_height": self.video_quality.currentData() or 0,
            "force_h264": self.h264_check.isChecked(),
        }

    def get_audio_options(self):
        return {
            "format": self.audio_format.currentText().lower(),
            "bitrate": self.audio_bitrate.currentData() or "192",
        }

    def get_thumbnail_options(self):
        return {"format": self.thumb_format.currentText()}

    def apply_preferences(self, config):
        """Restore saved user choices (audio format/bitrate, H.264, mode)."""
        self.h264_check.setChecked(bool(config.get("h264_enabled", False)))
        idx = self.audio_format.findText(str(config.get("audio_format", "mp3")).upper())
        if idx >= 0:
            self.audio_format.setCurrentIndex(idx)
        idx = self.audio_bitrate.findData(str(config.get("audio_bitrate", "192")))
        if idx >= 0:
            self.audio_bitrate.setCurrentIndex(idx)
        mode = {"video": 0, "audio": 1, "thumbnail": 2}.get(config.get("download_mode"), 0)
        self.mode_switch.set_index(mode)

    def store_preferences(self, config):
        config["h264_enabled"] = self.h264_check.isChecked()
        config["audio_format"] = self.audio_format.currentText().lower()
        config["audio_bitrate"] = self.audio_bitrate.currentData() or "192"
        mode = self.get_mode()
        if getattr(self, "_mode_before_audio_only", None) is not None and mode == 1:
            # Switched to Audio only because the link had no video.
            mode = self._mode_before_audio_only
        config["download_mode"] = ("video", "audio", "thumbnail")[mode]

    def clear(self):
        self.formats = []
        self.format_table.setRowCount(0)
        self.selected_label.setText("Automatic")
        self._reset_quality_combo()
        self.set_has_video(True)
