import os
import subprocess
import sys

from PyQt6.QtCore import QEasingCurve, QRectF, QSize, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QDesktopServices, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)

import math

import theme
from widgets import motion
from widgets.common import ElidedLabel, icon_button
from widgets.kit import IconLabel, Ticker, pick_icon, repolish

THUMB_W, THUMB_H = 64, 36
BAR_H = 3
BAR_GAP = 8
BAR_MAX = 1000  # internal resolution: sub-percent steps keep the fill smooth


class _Bar(QProgressBar):
    """Slim progress bar (styled by the KsBar QSS) that can also show a moving
    highlight while the real progress is unknown or being post-processed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._phase = 0.0
        # ~30fps and only while busy and visible: cheap with many rows.
        self._ticker = Ticker(self, self._set_phase, period=1300, interval=33)

    def set_busy(self, busy):
        busy = bool(busy) and not motion.REDUCED
        if busy == self._busy:
            return
        self._busy = busy
        if busy and self.isVisible():
            self._ticker.start()
        else:
            self._ticker.stop()
        self.update()

    def _set_phase(self, v):
        self._phase = v
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._busy:
            self._ticker.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._ticker.stop()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._busy:
            return
        w, h = self.width(), self.height()
        filled = w * (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        # Ease the band across so it lingers at neither end.
        t = 0.5 - 0.5 * math.cos(self._phase * 2 * math.pi)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, filled if filled > 1 else w, h), 2, 2)
        p.setClipPath(clip)
        if filled > 1:
            # Post-processing: a soft light glides over the finished fill.
            band = max(40.0, filled * 0.4)
            x = -band + t * (filled + band)
            col = QColor(theme.color("text"))
            col.setAlpha(90)
        else:
            # Waiting to start: an accent segment glides along the track.
            band = max(48.0, w * 0.3)
            x = -band + t * (w + band)
            col = QColor(theme.color("accent"))
        clear = QColor(col)
        clear.setAlpha(0)
        grad = QLinearGradient(x, 0, x + band, 0)
        grad.setColorAt(0.0, clear)
        grad.setColorAt(0.5, col)
        grad.setColorAt(1.0, clear)
        p.fillRect(QRectF(0, 0, w, h), grad)
        p.end()


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

        # The bar sits in a host that owns the gap above it, so the whole
        # strip can collapse smoothly once the row is finished.
        self.bar_host = QWidget()
        self.bar_host.setFixedHeight(BAR_GAP + BAR_H)
        host = QVBoxLayout(self.bar_host)
        host.setContentsMargins(0, BAR_GAP, 0, 0)
        host.setSpacing(0)
        self.progress_bar = _Bar()
        self.progress_bar.setObjectName("KsBar")
        self.progress_bar.setRange(0, BAR_MAX)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(BAR_H)
        host.addWidget(self.progress_bar, 0, Qt.AlignmentFlag.AlignTop)
        col.addWidget(self.bar_host)
        root.addLayout(col, 1)
        self._root = root
        self._target = 0  # latest requested fill, 0..BAR_MAX; never decreases

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
        if not self._finished:
            self.bar_host.setVisible(True)
            self.bar_host.setFixedHeight(BAR_GAP + BAR_H)
        self._sync_buttons()

    def _set_busy(self, busy):
        self.progress_bar.set_busy(busy and not self._finished)

    def _glide_to(self, units):
        """Move the fill to ``units`` (0..BAR_MAX) without ever going back."""
        units = max(self._target, min(BAR_MAX, int(round(units))))
        self._target = units
        bar = self.progress_bar
        cur = bar.value()
        if units == cur:
            return
        if not self.isVisible() or motion.REDUCED or units - cur < 4:
            anim = getattr(self, "_anim_glide", None)
            if anim is not None:
                anim.stop()
            bar.setValue(units)
            return
        motion.tween(self, cur, units, lambda v: bar.setValue(int(v)),
                     ms=motion.BASE, curve=motion.EASE_OUT, key="_anim_glide")

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
            self._glide_to(max(0.0, min(100.0, val)) * (BAR_MAX / 100))
            self._set_busy(False)
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
        queued = low.startswith(("queued", "waiting"))
        self._apply_state("queued" if queued else "active")
        # "Starting", "Processing", "Merging"...: no percent to show, so keep
        # the bar visibly alive.
        self._set_busy(not queued)
        self._refresh_meta()

    def set_complete(self, title, path=""):
        self.result_path = path or ""
        self._set_busy(False)
        self._glide_to(BAR_MAX)
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
        self._settle_row(pop=True, delay=motion.BASE)

    def set_error(self, message):
        self.percent_label.setText("")
        self._final_meta = ""
        self.status_label.setText(f"Failed: {message}")
        self.status_label.setToolTip(message)
        self._site_only_meta()
        self._finish()
        self._apply_state("error")
        self._refresh_meta()
        self._settle_row(pop=True, shake=True)
        if self.isVisible():
            motion.fade_in(self.status_label, ms=motion.BASE)

    def set_cancelled(self):
        self.status_label.setText("Cancelled")
        self.percent_label.setText("")
        self._final_meta = ""
        self._finish()
        self._apply_state("cancelled")
        self._refresh_meta()
        self._settle_row()

    # ------------------------------------------------------------ finishing

    def _settle_row(self, pop=False, shake=False, delay=0):
        """Collapse the bar strip, then (optionally) pop the status icon and
        nudge the row. Does nothing fancy when the row isn't on screen."""
        self._set_busy(False)
        if not self.isVisible() or motion.REDUCED:
            self.bar_host.setVisible(False)
            return
        if pop:
            self._pop_icon()
        if shake:
            self._shake()
        # Let a final glide to 100% be seen before the bar goes away.
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._collapse_bar)
        timer.start(delay)

    def _collapse_bar(self):
        host = self.bar_host
        if not self._finished:
            return

        def done():
            host.setVisible(False)
            host.setFixedHeight(BAR_GAP + BAR_H)

        motion.tween(self, host.height(), 0, lambda v: host.setFixedHeight(max(0, round(v))),
                     ms=motion.BASE, curve=motion.EASE_IN_OUT, finished=done,
                     key="_anim_collapse")

    def _pop_icon(self):
        icon = self.status_icon
        motion.tween(
            self, 0.4, 1.0, lambda v: icon.set_scale(v, alpha=v * 2),
            ms=motion.BASE + 60, curve=motion.EASE_SPRING,
            finished=lambda: icon.set_scale(1.0, alpha=1.0), key="_anim_pop",
        )

    def _shake(self):
        """One quick damped left-right wobble of the row's contents."""
        def on_value(t):
            dx = round(3 * math.sin(t * 4 * math.pi) * (1 - t))
            self._root.setContentsMargins(16 + dx, 12, 12 - dx, 12)

        motion.tween(self, 0.0, 1.0, on_value, ms=motion.BASE + 60,
                     curve=QEasingCurve.Type.Linear,
                     finished=lambda: self._root.setContentsMargins(16, 12, 12, 12),
                     key="_anim_shake")

    def _site_only_meta(self):
        # An error message is long; keep the meta line out of its way.
        self._site = ""
        self._mode = ""
