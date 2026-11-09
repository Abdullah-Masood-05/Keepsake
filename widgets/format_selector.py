from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QCheckBox, QComboBox, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QSizePolicy, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

import theme
from widgets import motion
from widgets.common import ElidedLabel, Segmented, section_label
from widgets.kit import Disclosure, mix

MODES = ("Video", "Audio", "Thumbnail")
CHIP_COLUMNS = 4


class _QualityChip(QAbstractButton):
    """Selectable quality card: resolution on top, name/size underneath."""

    def __init__(self, title, sub="", parent=None):
        super().__init__(parent)
        self._title = title
        self._sub = sub
        self.setCheckable(True)
        self.setAutoExclusive(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(46)
        self.setMinimumWidth(0)
        # 0..1 amounts the paint code blends palette colours with.
        self._sel = 1.0 if self.isChecked() else 0.0
        self._hov = 0.0
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        self._go("_sel", 1.0 if checked else 0.0, motion.BASE, "_anim_sel")

    def _go(self, attr, end, ms, key):
        def on_value(v, attr=attr):
            setattr(self, attr, float(v))
            self.update()
        if not self.isVisible() or motion.REDUCED:
            on_value(end)
            return
        motion.tween(self, getattr(self, attr), end, on_value, ms=ms,
                     curve=motion.EASE_OUT, key=key)

    def sizeHint(self):
        return QSize(110, 46)

    def minimumSizeHint(self):
        return QSize(0, 46)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            bg, border = QColor(theme.color("input")), QColor(theme.color("border"))
            c1, c2 = QColor(theme.color("text3")), QColor(theme.color("text3"))
        else:
            h, s = self._hov, self._sel
            # Hover and selection are independent 0..1 amounts so both can
            # fade in and out smoothly and overlap mid-transition.
            bg = mix(mix("input", "hover", h), "selection", s)
            border = mix(mix("border", "border_strong", h), "accent_line", s)
            c1 = QColor(theme.color("text"))
            c2 = mix("text3", "text2", max(h, s))
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(bg)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(rect, 3, 3)
        inner = rect.adjusted(12, 0, -10, 0)
        f1 = QFont(self.font())
        f1.setPixelSize(14)
        f1.setWeight(QFont.Weight.DemiBold)
        f2 = QFont(self.font())
        f2.setPixelSize(11)
        fm1, fm2 = p.fontMetrics(), p.fontMetrics()
        p.setFont(f1)
        fm1 = p.fontMetrics()
        p.setFont(f2)
        fm2 = p.fontMetrics()
        h1, h2 = fm1.height(), fm2.height() if self._sub else 0
        top = (rect.height() - (h1 + h2 + (1 if self._sub else 0))) / 2 + rect.top()
        p.setFont(f1)
        p.setPen(c1)
        p.drawText(QRectF(inner.left(), top, inner.width(), h1),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   fm1.elidedText(self._title, Qt.TextElideMode.ElideRight, int(inner.width())))
        if self._sub:
            p.setFont(f2)
            p.setPen(c2)
            p.drawText(QRectF(inner.left(), top + h1 + 1, inner.width(), h2),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       fm2.elidedText(self._sub, Qt.TextElideMode.ElideRight, int(inner.width())))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(theme.color("accent_line")), 1, Qt.PenStyle.DotLine))
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 2, 2)
        p.end()

    def enterEvent(self, event):
        self._go("_hov", 1.0, motion.FAST, "_anim_hov")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._go("_hov", 0.0, motion.BASE, "_anim_hov")
        super().leaveEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        self.update()


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

        # Video section: quality chips + collapsible stream table.
        self.formats_box = QWidget()
        fb = QVBoxLayout(self.formats_box)
        fb.setContentsMargins(0, 0, 0, 0)
        fb.setSpacing(8)
        fb.addWidget(section_label("Quality"))
        self.chip_host = QWidget()
        self.chip_grid = QGridLayout(self.chip_host)
        self.chip_grid.setContentsMargins(0, 0, 0, 0)
        self.chip_grid.setSpacing(8)
        for c in range(CHIP_COLUMNS):
            self.chip_grid.setColumnStretch(c, 1)
        fb.addWidget(self.chip_host)
        self._chips = []
        self._quality_meta = []
        fb.addSpacing(6)

        self.streams_head = Disclosure("Streams")
        self.streams_head.hint.setText("Optional: pick a specific stream")
        self.streams_head.toggled.connect(self._on_streams_toggled)
        fb.addWidget(self.streams_head)

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
        self.streams_body = _TableHolder(self.format_table, sel_row)
        self.streams_body.setVisible(False)
        self._body_min = self.streams_body.minimumHeight()
        fb.addWidget(self.streams_body, 1)

        layout.addWidget(self.formats_box)
        self._tail_index = layout.count()
        layout.addStretch(1)
        self._root_layout = layout
        self._on_streams_toggled(False)
        self._rebuild_chips()

    def _on_streams_toggled(self, opened):
        body = self.streams_body
        if not self.isVisible() or motion.REDUCED:
            self._finish_streams(opened)
            return
        start = body.height() if body.isVisible() else 0
        end = body.sizeHint().height() if opened else 0
        # While moving, keep the content packed at the top so the section
        # grows by exactly the body's height; the spare-height stretch is
        # restored when the motion ends.
        self._root_layout.setStretch(self._tail_index - 1, 0)
        self._root_layout.setStretch(self._tail_index, 1)
        body.setMinimumHeight(0)  # the body's own minimum would defeat the cap
        body.setMaximumHeight(start)
        body.setVisible(True)
        motion.tween(
            self, start, end, lambda v: body.setMaximumHeight(max(0, round(v))),
            ms=motion.BASE, curve=motion.EASE_OUT,
            finished=lambda: self._finish_streams(opened), key="_anim_streams",
        )

    def _finish_streams(self, opened):
        body = self.streams_body
        body.setMinimumHeight(self._body_min)
        body.setMaximumHeight(16777215)  # remove the cap
        body.setVisible(opened)
        # Give the table all spare height while open, otherwise keep the
        # content packed at the top.
        self._root_layout.setStretch(self._tail_index - 1, 1 if opened else 0)
        self._root_layout.setStretch(self._tail_index, 0 if opened else 1)

    def _create_video_options(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        # The combo is the data model behind the quality chips (and keeps
        # get_video_options()/stream filtering simple); it is never shown.
        self.video_quality = _combo(180)
        self.video_quality.setParent(self)
        self.video_quality.hide()
        self.video_quality.currentIndexChanged.connect(self._on_video_quality_changed)
        self.video_quality.currentIndexChanged.connect(self._sync_chips)
        self._reset_quality_combo()

        # A lone QRadioButton can never be unchecked again; use a checkbox.
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

    # ------------------------------------------------------------- chips

    def _rebuild_chips(self):
        for chip in self._chips:
            self.chip_grid.removeWidget(chip)
            chip.setParent(None)
            chip.deleteLater()
        self._chips = []
        enabled = self.video_quality.isEnabled()
        animate = enabled and self.chip_host.isVisible() and not motion.REDUCED
        for i, (title, sub, tip) in enumerate(self._quality_meta):
            chip = _QualityChip(title, sub)
            chip.setToolTip(tip)
            chip.setEnabled(enabled)
            chip.clicked.connect(lambda _=False, idx=i: self.video_quality.setCurrentIndex(idx))
            self.chip_grid.addWidget(chip, i // CHIP_COLUMNS, i % CHIP_COLUMNS)
            self._chips.append(chip)
            if animate:
                motion.fade_in(chip, ms=motion.BASE)
        self._sync_chips()

    def _sync_chips(self, *_):
        cur = self.video_quality.currentIndex()
        for i, chip in enumerate(self._chips):
            chip.setChecked(i == cur)

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
        def change():
            self.options_stack.setCurrentIndex(idx)
            # Quality + streams only apply to video downloads.
            self.formats_box.setVisible(idx == 0)

        self._crossfade(change, (self.options_stack, self.formats_box))
        self.mode_changed.emit(idx)

    def _crossfade(self, change, incoming):
        """Run ``change`` while a snapshot of the old look fades out over the
        new content, which fades in underneath."""
        if not self.isVisible() or motion.REDUCED:
            change()
            return
        for old in self.findChildren(QLabel, "KsGhost"):
            old.hide()
            old.deleteLater()
        ghost = QLabel(self)
        ghost.setObjectName("KsGhost")
        ghost.setPixmap(self.grab())
        ghost.setGeometry(self.rect())
        ghost.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        ghost.show()
        old_h = self.height()
        change()
        for w in incoming:
            if w.isVisible():
                motion.fade_in(w, ms=motion.BASE)
        ghost.raise_()
        motion.fade_out(ghost, ms=motion.BASE, finished=ghost.deleteLater)
        # The selector's own height changes with the mode (no quality section
        # for Audio); glide it so whatever sits below doesn't jump.
        new_h = self.sizeHint().height()
        if new_h != old_h:
            def done():
                self.setMinimumHeight(0)
                self.setMaximumHeight(16777215)
            self.setFixedHeight(old_h)
            motion.tween(self, old_h, new_h, lambda v: self.setFixedHeight(round(v)),
                         ms=motion.BASE, curve=motion.EASE_OUT, finished=done,
                         key="_anim_height")

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
        meta = [("Best", "Highest available", "Highest quality the site offers")]
        for q in qualities:
            title, sub, tip = self._quality_parts(q)
            self.video_quality.addItem(self._quality_label(q), q["height"])
            meta.append((title, sub, tip))
        self._quality_meta = meta

        # Default: highest quality up to 1080p, otherwise Best available
        default_index = 0
        for i in range(1, self.video_quality.count()):
            if self.video_quality.itemData(i) <= 1080:
                default_index = i
                break
        self.video_quality.setCurrentIndex(default_index)
        self.video_quality.setEnabled(True)
        self.video_quality.blockSignals(False)
        self._rebuild_chips()
        self._on_video_quality_changed(default_index)

    def _reset_quality_combo(self):
        self.video_quality.blockSignals(True)
        self.video_quality.clear()
        self.video_quality.addItem("Fetch a video first", 0)
        self.video_quality.setCurrentIndex(0)
        self.video_quality.setEnabled(False)
        self.video_quality.blockSignals(False)
        self._quality_meta = [("Fetch a video first", "", "")]
        if hasattr(self, "chip_grid"):
            self._rebuild_chips()

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
    def _quality_parts(q):
        names = {4320: "8K", 2160: "4K", 1440: "QHD", 1080: "Full HD", 720: "HD"}
        height = q["height"]
        fps = q.get("fps", 0)
        title = f"{height}p"
        if fps and fps > 30:
            title += f"{fps}"
        sub = names.get(height, "")
        size = q.get("filesize", 0)
        if size:
            sz = f"~{FormatSelector._format_size(size)}"
            sub = f"{sub}  ·  {sz}" if sub else sz
        return title, sub, FormatSelector._quality_label(q).replace("  ", " ")

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
        self.streams_head.hint.setText(
            f"{fmt['resolution']}  {fmt['ext']}  (id {fmt['format_id']})" if fmt
            else "Optional: pick a specific stream"
        )
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
