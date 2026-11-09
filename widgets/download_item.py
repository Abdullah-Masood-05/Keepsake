import os
import subprocess
import sys

from PyQt6.QtCore import QRectF, QSize, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)

import theme
from widgets.common import ElidedLabel, icon_button
from widgets.kit import IconLabel, pick_icon, repolish

THUMB_W, THUMB_H = 64, 36


def _format_size(n):
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024:
            return f"{size:.2f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size:.2f}TiB"


class _Thumb(QWidget):
    """Small rounded thumbnail; falls back to a mode icon tile."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_W, THUMB_H)
        self._image = None
        self._icon = "video"

    def set_image(self, image):
        self._image = image
        self.update()

    def set_icon(self, name):
        self._icon = name
        self.update()

    def paintEvent(self, event):
        dpr = self.devicePixelRatioF() or 1.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 3, 3)
        p.fillPath(path, QColor(theme.color("raised")))
        if self._image is not None:
            w, h = int(THUMB_W * dpr), int(THUMB_H * dpr)
            scaled = self._image.scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x, y = (scaled.width() - w) // 2, (scaled.height() - h) // 2
            pm = QPixmap.fromImage(scaled.copy(x, y, w, h))
            pm.setDevicePixelRatio(dpr)
            p.setClipPath(path)
            p.drawPixmap(0, 0, pm)
            p.setClipping(False)
        else:
            name = pick_icon(self._icon, "download")
            ic = theme.icon(name, "text3", 18)
            p.drawPixmap((self.width() - 18) // 2, (self.height() - 18) // 2,
                         ic.pixmap(QSize(18, 18)))
        p.setPen(QColor(theme.color("border")))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 3, 3)
        p.end()


class DownloadItemWidget(QFrame):
    """One row in the downloads list: status icon, title, meta line
    (site . size . speed . ETA), slim progress bar and icon actions."""

    cancel_clicked = pyqtSignal(int)
    close_clicked = pyqtSignal(int)
    retry_clicked = pyqtSignal(int)

    _STATUS_ICON = {
        "": ("download", "text3"),
        "queued": ("download", "text3"),
        "active": ("download", "accent_line"),
        "done": ("check_circle", "success"),
        "error": ("warning", "danger"),
        "cancelled": ("x_circle", "text3"),
    }
    _FALLBACK = {"check_circle": "check", "warning": "close", "x_circle": "close"}

    def __init__(self, download_id, title, out_dir="", parent=None):
        super().__init__(parent)
        self.setObjectName("KsRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.download_id = download_id
        self.out_dir = out_dir
        self.result_path = ""
        self._finished = False
        self._state = ""
        self._site = ""
        self._mode = ""
        self._speed = ""
        self._eta = ""
        self._size = ""
        self._final_meta = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._setup_ui(title)
        self._apply_state("")

    def _setup_ui(self, title):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 12, 12)
        root.setSpacing(12)

        self.status_icon = IconLabel("download", "text3", 18)
        root.addWidget(self.status_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.thumb = _Thumb()
        self.thumb.setVisible(False)
        root.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self.title_label = ElidedLabel(title)
        self.title_label.setObjectName("KsRowTitle")
        self.title_label.setToolTip(title)
        col.addWidget(self.title_label)
        col.addSpacing(2)

        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        self.status_label = ElidedLabel("Waiting")
        self.status_label.setObjectName("KsRowStatus")
        line.addWidget(self.status_label, 0)
        self.meta_label = ElidedLabel("")
        self.meta_label.setObjectName("KsRowMeta")
        line.addWidget(self.meta_label, 1)
        col.addLayout(line)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("KsBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self._bar_gap = 8
        col.addSpacing(self._bar_gap)
        col.addWidget(self.progress_bar)
        root.addLayout(col, 1)

        self.percent_label = QLabel("")
        self.percent_label.setObjectName("KsRowPct")
        self.percent_label.setMinimumWidth(48)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.percent_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.folder_btn = icon_button("folder", "Show in folder")
        self.folder_btn.clicked.connect(self._open_location)
        self.retry_btn = icon_button(pick_icon("retry", "download"), "Retry")
        self.retry_btn.clicked.connect(lambda: self.retry_clicked.emit(self.download_id))
        self.cancel_btn = icon_button("close", "Cancel download", danger=True)
        self.cancel_btn.clicked.connect(self._on_button_clicked)
        self.remove_btn = icon_button("clear", "Remove from list", danger=True)
        self.remove_btn.clicked.connect(lambda: self.close_clicked.emit(self.download_id))
        for b in (self.folder_btn, self.retry_btn, self.cancel_btn, self.remove_btn):
            root.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        self._retry_enabled = False
        self.retry_btn.setVisible(False)
        self.remove_btn.setVisible(False)
        self.folder_btn.setVisible(False)

    # -------------------------------------------------------------- actions

    def _on_button_clicked(self):
        if self._finished:
            self.close_clicked.emit(self.download_id)
        else:
            self.cancel_btn.setEnabled(False)
            self.cancel_clicked.emit(self.download_id)

    def _open_location(self):
        path = self.result_path
        if path and os.path.isfile(path) and sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return
        folder = path if path and os.path.isdir(path) else self.out_dir
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def is_finished(self):
        return self._finished

    # ------------------------------------------------------------- optional

    def set_meta(self, site="", mode="", thumbnail=None):
        """Optional extra info: site name, mode ('video'/'audio'/'thumbnail'
        or any label) and a QImage thumbnail."""
        self._site = site or ""
        self._mode = mode or ""
        icon = {"audio": "music", "thumbnail": "image"}.get(self._mode.lower(), "video")
        self.thumb.set_icon(icon)
        if isinstance(thumbnail, QImage) and not thumbnail.isNull():
            self.thumb.set_image(thumbnail)
        self.thumb.setVisible(thumbnail is not None or bool(self._mode))
        self._refresh_meta()

    def enable_retry(self, enabled=True):
        """Show a retry button on failed/cancelled rows (emits retry_clicked)."""
        self._retry_enabled = bool(enabled)
        self._sync_buttons()

    # --------------------------------------------------------------- state

    def _apply_state(self, state):
        self._state = state
        icon, key = self._STATUS_ICON.get(state, self._STATUS_ICON[""])
        if not icon in theme._SVG:
            icon = self._FALLBACK.get(icon, "download")
        self.status_icon.set_icon(icon, key)
        for w in (self.status_label, self.progress_bar):
            w.setProperty("state", "queued" if (w is self.progress_bar and state == "queued") else state)
            repolish(w)
        self.progress_bar.setVisible(not self._finished)
        self._sync_buttons()

    def _sync_buttons(self):
        fin = self._finished
        self.cancel_btn.setVisible(not fin)
        self.remove_btn.setVisible(fin)
        self.folder_btn.setVisible(fin and self._state == "done")
        self.retry_btn.setVisible(fin and self._retry_enabled and self._state in ("error", "cancelled"))
        self.percent_label.setVisible(not fin or self._state == "done")

    def _meta_parts(self):
        parts = [self._site]
        if self._mode:
            parts.append(self._mode.capitalize() if self._mode.islower() else self._mode)
        if self._finished:
            if self._final_meta:
                parts.append(self._final_meta)
        else:
            parts += [self._size, self._speed, self._eta]
        return [x for x in parts if x]

    def _refresh_meta(self):
        parts = self._meta_parts()
        text = "  ·  ".join(parts)
        self.meta_label.setText(("  ·  " + text) if text else "")

    def _finish(self):
        self._finished = True
        self.cancel_btn.setEnabled(True)
        self._speed = ""
        self._eta = ""

    # --------------------------------------------------------------- updates

    def update_progress(self, percent_str, speed, eta, size=""):
        if self._finished:
            return
        try:
            val = float(percent_str.replace("%", "").strip())
            self.progress_bar.setValue(max(0, min(100, int(round(val)))))
            self.percent_label.setText(f"{val:.0f}%")
        except (ValueError, AttributeError):
            pass
        self._speed = speed if speed and speed != "N/A" else ""
        self._eta = f"ETA {eta}" if eta and eta != "N/A" else ""
        if size and size != "N/A":
            self._size = size
        if self._state != "active":
            self.status_label.setText("Downloading")
            self._apply_state("active")
        self._refresh_meta()

    def set_status(self, text):
        if self._finished:
            return
        self.status_label.setText(text)
        low = text.lower()
        self._apply_state("queued" if low.startswith(("queued", "waiting")) else "active")
        self._refresh_meta()

    def set_complete(self, title, path=""):
        self.result_path = path or ""
        self.progress_bar.setValue(100)
        self.percent_label.setText("100%")
        self.title_label.setText(title)
        self.title_label.setToolTip(title)
        extra = []
        if self.result_path and os.path.isfile(self.result_path):
            # Show what was produced (several rows can share a title) and
            # the real final size rather than the last stream's size.
            ext = os.path.splitext(self.result_path)[1].lstrip(".").upper()
            if ext:
                extra.append(ext)
            extra.append(_format_size(os.path.getsize(self.result_path)))
        elif self._size:
            extra.append(self._size)
        self._final_meta = "  ·  ".join(extra)
        self.status_label.setText("Completed")
        self.status_label.setToolTip(self.result_path)
        self._finish()
        self._apply_state("done")
        self._refresh_meta()

    def set_error(self, message):
        self.percent_label.setText("")
        self._final_meta = ""
        self.status_label.setText(f"Failed: {message}")
        self.status_label.setToolTip(message)
        self._site_only_meta()
        self._finish()
        self._apply_state("error")
        self._refresh_meta()

    def set_cancelled(self):
        self.status_label.setText("Cancelled")
        self.percent_label.setText("")
        self._final_meta = ""
        self._finish()
        self._apply_state("cancelled")
        self._refresh_meta()

    def _site_only_meta(self):
        # An error message is long; keep the meta line out of its way.
        self._site = ""
        self._mode = ""
