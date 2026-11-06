from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

import theme
from widgets.common import ElidedLabel, section_label

THUMB_W, THUMB_H = 256, 144  # 16:9
THUMB_RADIUS = 3


class VideoCard(QFrame):
    """Thumbnail + title/channel + stats for the fetched video."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._image = None
        self._loaded = False
        self._fit_inside = False
        self._setup_ui()
        self.clear()

    def _setup_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setObjectName("Thumb")
        self.thumbnail_label.setFixedSize(THUMB_W, THUMB_H)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(0)

        self.kind_label = section_label("Video")
        info.addWidget(self.kind_label)
        info.addSpacing(6)

        self.title_label = QLabel()
        self.title_label.setObjectName("VideoTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.addWidget(self.title_label)
        info.addSpacing(4)

        self.channel_label = ElidedLabel()
        self.channel_label.setObjectName("Muted")
        info.addWidget(self.channel_label)

        info.addStretch(1)

        # Stats: small caps label above a tabular value.
        self.stats = QWidget()
        grid = QGridLayout(self.stats)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(32)
        grid.setVerticalSpacing(4)
        self.duration_label = QLabel()
        self.views_label = QLabel()
        self.date_label = QLabel()
        for col, (name, value) in enumerate((
            ("Duration", self.duration_label),
            ("Views", self.views_label),
            ("Uploaded", self.date_label),
        )):
            value.setObjectName("StatValue")
            grid.addWidget(section_label(name), 0, col)
            grid.addWidget(value, 1, col)
        grid.setColumnStretch(3, 1)
        info.addWidget(self.stats)
        info.addSpacing(12)

        self.desc_label = ElidedLabel()
        self.desc_label.setObjectName("Faint")
        info.addWidget(self.desc_label)

        lay.addLayout(info, 1)

    # ------------------------------------------------------------------ data

    def set_info(self, data):
        # The fetch worker hands over a QImage; the QPixmap is created here,
        # on the GUI thread (creating it in a worker thread is unsupported).
        image = data.get("thumbnail_image")
        self._image = image if isinstance(image, QImage) and not image.isNull() else None
        self._loaded = True
        # Audio-only sources usually ship square album art: letterbox it
        # instead of cropping.
        self._fit_inside = data.get("has_video") is False
        self._render_thumb()

        title = data.get("title") or "Unknown"
        if len(title) > 140:
            title = title[:137] + "..."
        self.title_label.setText(title)
        self.title_label.setToolTip(data.get("title") or "")
        parts = []
        if data.get("is_playlist"):
            parts.append("PLAYLIST")
        else:
            parts.append("VIDEO" if data.get("has_video", True) else "AUDIO")
        site = data.get("site") or ""
        if site:
            parts.append(site.upper())
        count = data.get("entry_count") or 0
        if data.get("is_playlist") and count:
            parts.append(f"{count} ITEM{'S' if count != 1 else ''}")
        self.kind_label.setText(" · ".join(parts))
        channel = data.get("channel") or ""
        if channel == "Unknown":
            channel = ""
        self.channel_label.setText(channel)
        self.channel_label.setVisible(bool(channel))

        date = data.get("upload_date") or ""
        if len(date) == 8 and date.isdigit():
            date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        views = data.get("view_count") or ""
        duration = data.get("duration") or ""
        self.duration_label.setText(duration if duration not in ("", "0:00", "N/A") else "-")
        self.views_label.setText(views if views and views != "N/A" else "-")
        self.date_label.setText(date or "-")
        self.stats.setVisible(True)

        desc = " ".join((data.get("description") or "").split())
        self.desc_label.setText(desc)
        self.desc_label.setVisible(bool(desc))

    def clear(self):
        self._image = None
        self._loaded = False
        self._render_thumb()
        self.kind_label.setText("NO VIDEO")
        self.title_label.setText("Paste a link to get started")
        self.title_label.setToolTip("")
        self.channel_label.setVisible(True)
        self.channel_label.setText(
            "Links from YouTube and 1,000+ other sites are supported. "
            "Press Enter or Fetch."
        )
        self.duration_label.setText("-")
        self.views_label.setText("-")
        self.date_label.setText("-")
        self.stats.setVisible(False)
        self.desc_label.setText("")
        self.desc_label.setVisible(False)

    def set_loading(self):
        self.clear()
        self.kind_label.setText("FETCHING")
        self.title_label.setText("Reading video information...")
        self.channel_label.setText("")
        self.channel_label.setVisible(True)

    def retheme(self):
        self._render_thumb()

    # ------------------------------------------------------------ thumbnail

    def _render_thumb(self):
        dpr = self.devicePixelRatioF() or 1.0
        w, h = int(round(THUMB_W * dpr)), int(round(THUMB_H * dpr))
        if self._image is not None:
            if self._fit_inside:
                # Album art etc.: letterbox inside the frame, no cropping.
                scaled = self._image.scaled(
                    w, h, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                content = QPixmap(w, h)
                content.fill(QColor(theme.color("raised")))
                painter = QPainter(content)
                painter.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
                painter.end()
            else:
                # Fill the 16:9 frame exactly (crop letterboxing / 4:3 sources).
                scaled = self._image.scaled(
                    w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (scaled.width() - w) // 2
                y = (scaled.height() - h) // 2
                content = QPixmap.fromImage(scaled.copy(QRect(x, y, w, h)))
        else:
            content = self._placeholder(w, h)
        self.thumbnail_label.setPixmap(self._rounded(content, w, h, dpr))

    @staticmethod
    def _rounded(content, w, h, dpr):
        """Clip ``content`` to a 3px rounded rect and add a 1px hairline."""
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = THUMB_RADIUS * dpr
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.setClipPath(path)
        p.drawPixmap(0, 0, content)
        p.setClipping(False)
        pen = QPen(QColor(theme.color("border")))
        pen.setWidthF(dpr)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        half = dpr / 2
        p.drawRoundedRect(QRectF(half, half, w - dpr, h - dpr), r - half, r - half)
        p.end()
        pm.setDevicePixelRatio(dpr)
        return pm

    def _placeholder(self, w, h):
        pm = QPixmap(w, h)
        pm.fill(QColor(theme.color("raised")))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        s = h * 0.18
        cx, cy = w / 2, h / 2
        # Slightly rounded tile with a play triangle, echoing the logo.
        tile = QColor(theme.color("border_strong" if not self._loaded else "border"))
        p.setBrush(tile)
        p.drawRoundedRect(QRectF(cx - s, cy - s * 0.72, 2 * s, 1.44 * s), s * 0.12, s * 0.12)
        p.setBrush(QColor(theme.color("raised")))
        tri = QPolygonF([
            QPointF(cx - s * 0.30, cy - s * 0.38),
            QPointF(cx - s * 0.30, cy + s * 0.38),
            QPointF(cx + s * 0.40, cy),
        ])
        p.drawPolygon(tri)
        p.end()
        return pm
