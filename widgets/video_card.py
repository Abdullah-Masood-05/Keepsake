from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QStackedLayout, QVBoxLayout, QWidget,
)

import theme
from widgets import motion
from widgets.common import ElidedLabel
from widgets.kit import IconLabel, Skeleton, pick_icon, pill

THUMB_W, THUMB_H = 256, 144  # 16:9
THUMB_RADIUS = 3


class _TwoLineLabel(QLabel):
    """Shows at most two lines of text, eliding the second; long words
    (URLs) are broken instead of pushing a clipped third line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = ""

    def setText(self, text):
        self._full = text or ""
        self._relayout()

    def text(self):
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        fm = self.fontMetrics()
        width = max(self.width() - 2, 40)
        text = self._full
        if fm.horizontalAdvance(text) <= width:
            super().setText(text)
            return
        # Longest prefix that fits on line one, broken at a space if one is
        # reasonably close to the end.
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fm.horizontalAdvance(text[:mid]) <= width:
                lo = mid
            else:
                hi = mid - 1
        cut = lo
        space = text.rfind(" ", 0, cut + 1)
        if space > cut * 0.6:
            cut = space
        first = text[:cut].rstrip()
        second = fm.elidedText(text[cut:].lstrip(), Qt.TextElideMode.ElideRight, width)
        super().setText(first + "\n" + second)


class _CardSkeleton(Skeleton):
    """Loading placeholder that mirrors the real card layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(THUMB_H + 32)

    def blocks(self):
        x0 = 16 + THUMB_W + 16
        avail = max(self.width() - x0 - 16, 80)
        r = QRectF
        return [
            (r(16, 16, THUMB_W, THUMB_H), THUMB_RADIUS),
            (r(x0, 16, 56, 20), 3), (r(x0 + 62, 16, 64, 20), 3),
            (r(x0, 46, avail * 0.85, 16), 3), (r(x0, 68, avail * 0.55, 16), 3),
            (r(x0, 96, min(avail, 150), 12), 3), (r(x0, 116, min(avail, 220), 12), 3),
            (r(x0, 132, avail * 0.9, 10), 3), (r(x0, 148, avail * 0.6, 10), 3),
        ]


class VideoCard(QFrame):
    """Thumbnail + badges/title/channel + meta for the fetched video, or a
    calm empty state while nothing is loaded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._image = None
        self._loaded = False
        self._fit_inside = False
        self._duration = ""
        self._setup_ui()
        self.clear()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedLayout()
        outer.addLayout(self.stack)
        self.stack.addWidget(self._build_empty())
        self.stack.addWidget(self._build_info())
        self.skeleton = _CardSkeleton()
        self.stack.addWidget(self.skeleton)

    def _build_empty(self):
        page = QWidget()
        page.setMinimumHeight(THUMB_H + 32)
        lay = QHBoxLayout(page)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile = QFrame()
        tile.setObjectName("KsIconTile")
        tile.setFixedSize(52, 52)
        tl = QHBoxLayout(tile)
        tl.setContentsMargins(0, 0, 0, 0)
        self.empty_icon = IconLabel("link", "text2", 22)
        tl.addWidget(self.empty_icon, 0, Qt.AlignmentFlag.AlignCenter)
        col.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(14)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("KsEmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.empty_title)
        col.addSpacing(4)
        self.empty_sub = QLabel()
        self.empty_sub.setObjectName("Faint")
        self.empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_sub.setWordWrap(True)
        col.addWidget(self.empty_sub)
        lay.addLayout(col, 3)
        lay.addStretch(1)
        return page

    def _build_info(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setObjectName("Thumb")
        self.thumbnail_label.setFixedSize(THUMB_W, THUMB_H)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignTop)

        self.info_box = QWidget()
        info = QVBoxLayout(self.info_box)
        self.info_layout = info
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(0)

        badges = QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(6)
        self.kind_pill = pill("VIDEO", "accent")
        self.site_pill = pill("")
        self.count_pill = pill("")
        for w in (self.kind_pill, self.site_pill, self.count_pill):
            badges.addWidget(w)
        badges.addStretch(1)
        info.addLayout(badges)
        info.addSpacing(10)

        self.title_label = QLabel()
        self.title_label.setObjectName("VideoTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.addWidget(self.title_label)
        info.addSpacing(4)

        self.channel_label = ElidedLabel()
        self.channel_label.setObjectName("KsChannel")
        info.addWidget(self.channel_label)
        info.addSpacing(6)

        self.meta_label = ElidedLabel()
        self.meta_label.setObjectName("KsMeta")
        info.addWidget(self.meta_label)

        info.addStretch(1)

        self.desc_label = _TwoLineLabel()
        self.desc_label.setObjectName("KsDesc")
        self.desc_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info.addWidget(self.desc_label)

        lay.addWidget(self.info_box, 1)
        return page

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
        duration = data.get("duration") or ""
        self._duration = duration if duration not in ("", "0:00", "N/A") else ""
        if data.get("is_playlist"):
            self._duration = ""
        self._render_thumb()

        title = data.get("title") or "Unknown"
        if len(title) > 140:
            title = title[:137] + "..."
        self.title_label.setText(title)
        self.title_label.setToolTip(data.get("title") or "")

        if data.get("is_playlist"):
            kind = "PLAYLIST"
        else:
            kind = "VIDEO" if data.get("has_video", True) else "AUDIO"
        self.kind_pill.setText(kind)
        site = data.get("site") or ""
        self.site_pill.setText(site)
        self.site_pill.setVisible(bool(site))
        count = data.get("entry_count") or 0
        show_count = bool(data.get("is_playlist") and count)
        self.count_pill.setText(f"{count} item{'s' if count != 1 else ''}" if show_count else "")
        self.count_pill.setVisible(show_count)

        channel = data.get("channel") or ""
        if channel == "Unknown":
            channel = ""
        self.channel_label.setText(channel)
        self.channel_label.setVisible(bool(channel))

        date = data.get("upload_date") or ""
        if len(date) == 8 and date.isdigit():
            date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        views = data.get("view_count") or ""
        parts = []
        if views and views != "N/A":
            parts.append(views if "view" in str(views) else f"{views} views")
        if date:
            parts.append(date)
        self.meta_label.setText("  ·  ".join(parts))
        self.meta_label.setVisible(bool(parts))

        desc = " ".join((data.get("description") or "").split())
        self.desc_label.setText(desc)
        self.desc_label.setVisible(bool(desc))
        was_info = self.stack.currentIndex() == 1
        self.stack.setCurrentIndex(1)
        self._reveal(was_info)

    def _settle(self):
        """Stop any running reveal and leave the content fully visible."""
        for w in (self.info_box, self.thumbnail_label):
            anim = getattr(w, "_anim_fade", None)
            if anim is not None:
                anim.stop()
            w.setGraphicsEffect(None)
        anim = getattr(self, "_anim_rise", None)
        if anim is not None:
            anim.stop()
        self.info_layout.setContentsMargins(0, 0, 0, 0)

    def _reveal(self, replacing):
        """Fade the thumbnail and text in, the text rising a few pixels."""
        self._settle()
        if motion.REDUCED or not self.isVisible():
            return
        motion.fade_in(self.thumbnail_label, ms=motion.SLOW)
        motion.fade_in(self.info_box, ms=motion.BASE)
        rise = 4 if replacing else 6
        motion.tween(
            self, float(rise), 0.0,
            lambda v: self.info_layout.setContentsMargins(0, round(v), 0, 0),
            ms=motion.SLOW, curve=motion.EASE_OUT, key="_anim_rise",
            finished=lambda: self.info_layout.setContentsMargins(0, 0, 0, 0),
        )

    def clear(self):
        self._settle()
        self._image = None
        self._loaded = False
        self._duration = ""
        self._render_thumb()
        self.empty_icon.set_icon("link")
        self.empty_title.setText("Paste a link to get started")
        self.empty_sub.setText(
            "Links from YouTube and 1,000+ other sites are supported.\n"
            "Press Enter or Fetch."
        )
        self.stack.setCurrentIndex(0)

    def set_loading(self):
        self.clear()
        self.empty_icon.set_icon(pick_icon("search", "link"))
        self.empty_title.setText("Reading video information...")
        self.empty_sub.setText("This usually takes a few seconds.")
        # A skeleton with a sweeping highlight reads as "working" better
        # than static text; the text stays as the accessible description.
        self.skeleton.setAccessibleName("Reading video information")
        self.stack.setCurrentIndex(2)

    def retheme(self):
        self._render_thumb()
        self.empty_icon.update()

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
        if self._duration:
            self._draw_duration(content, dpr)
        self.thumbnail_label.setPixmap(self._rounded(content, w, h, dpr))

    def _draw_duration(self, pm, dpr):
        """Duration badge in the bottom-right corner of the thumbnail."""
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont(self.font())
        f.setPixelSize(int(round(11 * dpr)))
        f.setWeight(QFont.Weight.DemiBold)
        theme.tabular(f)
        p.setFont(f)
        fm = p.fontMetrics()
        bw = fm.horizontalAdvance(self._duration) + int(12 * dpr)
        bh = fm.height() + int(4 * dpr)
        margin = int(8 * dpr)
        rect = QRectF(pm.width() - bw - margin, pm.height() - bh - margin, bw, bh)
        bg = QColor(theme.color("bg"))
        bg.setAlpha(225)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 3 * dpr, 3 * dpr)
        p.setPen(QColor(theme.color("text")))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self._duration)
        p.end()

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
        p.setBrush(QColor(theme.color("border_strong" if not self._loaded else "border")))
        p.drawRoundedRect(QRectF(cx - s, cy - s * 0.72, 2 * s, 1.44 * s), s * 0.12, s * 0.12)
        p.setBrush(QColor(theme.color("raised")))
        p.drawPolygon(QPolygonF([
            QPointF(cx - s * 0.30, cy - s * 0.38),
            QPointF(cx - s * 0.30, cy + s * 0.38),
            QPointF(cx + s * 0.40, cy),
        ]))
        p.end()
        return pm
