"""Shared building blocks for the refreshed video card / format picker /
download rows: pills, a theme-aware icon label, and their styles.

All colours come from ``theme.PALETTES``; nothing here hard-codes a hex.
"""

from PyQt6.QtCore import QElapsedTimer, QPointF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

import theme
from widgets import motion

try:  # icons registered by another module; optional at import time
    import widgets.icons  # noqa: F401
except Exception:  # pragma: no cover
    pass


def has_icon(name):
    return name in theme._SVG


def pick_icon(name, fallback):
    """``name`` if registered, else ``fallback`` (icons land in parallel)."""
    return name if has_icon(name) else fallback


_pix_cache = {}


def mix(a, b, t):
    """Blend two palette colour keys (or hex strings) by ``t`` in 0..1."""
    pal = theme.PALETTES[theme.current()]
    ca = QColor(a) if isinstance(a, QColor) else QColor(pal.get(a, a))
    cb = QColor(b) if isinstance(b, QColor) else QColor(pal.get(b, b))
    t = max(0.0, min(1.0, t))
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
        round(ca.alpha() + (cb.alpha() - ca.alpha()) * t),
    )


class Ticker(QTimer):
    """Looping 0..1 phase callback (default ~30fps, cheap for many rows).
    Owned by its widget so it dies with it; callers start/stop it."""

    def __init__(self, owner, on_phase, period=1500, interval=33):
        super().__init__(owner)
        self.setInterval(interval)
        self._period = period
        self._clock = QElapsedTimer()
        self._on_phase = on_phase
        self.timeout.connect(self._tick)

    def start(self):
        self._clock.start()
        super().start()

    def _tick(self):
        self._on_phase((self._clock.elapsed() % self._period) / self._period)


class IconLabel(QWidget):
    """Draws a themed icon fresh on every paint, so it follows theme switches
    without needing an explicit retheme call."""

    def __init__(self, name, color_key="text2", px=16, parent=None):
        super().__init__(parent)
        self._name = name
        self._key = color_key
        self._px = px
        self._angle = 0.0
        self._scale = 1.0
        self._alpha = 1.0
        self.setFixedSize(px, px)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_icon(self, name, color_key=None):
        self._name = name
        if color_key:
            self._key = color_key
        self.update()

    def sizeHint(self):
        return QSize(self._px, self._px)

    def set_angle(self, deg):
        self._angle = float(deg)
        self.update()

    def set_scale(self, scale, alpha=None):
        self._scale = float(scale)
        if alpha is not None:
            self._alpha = max(0.0, min(1.0, float(alpha)))
        self.update()

    def paintEvent(self, event):
        name = self._name if has_icon(self._name) else None
        if not name:
            return
        dpr = self.devicePixelRatioF() or 1.0
        col = theme.PALETTES[theme.current()].get(self._key, self._key)
        key = (name, col, self._px, dpr)
        pm = _pix_cache.get(key)
        if pm is None:
            pm = theme._render(name, col, self._px, dpr)
            _pix_cache[key] = pm
        p = QPainter(self)
        if self._angle or self._scale != 1.0 or self._alpha != 1.0:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setOpacity(self._alpha)
            c = QPointF(self._px / 2, self._px / 2)
            p.translate(c)
            p.rotate(self._angle)
            p.scale(self._scale, self._scale)
            p.translate(-c)
        p.drawPixmap(0, 0, pm)
        p.end()


def pill(text, tone=""):
    """Small rounded label: tone in '', 'accent', 'info', 'success', 'warning'."""
    lbl = QLabel(text)
    lbl.setObjectName("KsPill")
    lbl.setProperty("tone", tone)
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lbl


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


class Skeleton(QWidget):
    """Placeholder blocks with a soft highlight band sweeping across them.
    Subclasses return ``[(QRectF, radius), ...]`` from ``blocks()``. The
    sweep only runs while the widget is visible."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._ticker = Ticker(self, self._set_phase, period=1600, interval=16)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def blocks(self):
        return []

    def _set_phase(self, v):
        self._phase = v
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not motion.REDUCED:
            self._ticker.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._ticker.stop()

    def paintEvent(self, event):
        path = QPainterPath()
        for rect, radius in self.blocks():
            path.addRoundedRect(rect, radius, radius)
        base, hi = QColor(theme.color("raised")), QColor(theme.color("pressed"))
        # The band travels from just off the left edge to just off the right.
        band = max(160.0, self.width() * 0.35)
        x = -band + self._phase * (self.width() + band)
        grad = QLinearGradient(x, 0, x + band, 0)
        grad.setColorAt(0.0, base)
        grad.setColorAt(0.5, hi)
        grad.setColorAt(1.0, base)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base if motion.REDUCED else grad)
        p.drawPath(path)
        p.end()


class Disclosure(QFrame):
    """Clickable header row with a chevron, a title and a right-aligned hint."""

    toggled = pyqtSignal(bool)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("KsDisclosure")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)
        self.chevron = IconLabel("chevron_down", "text2", 14)
        lay.addWidget(self.chevron)
        self.title = QLabel(title)
        self.title.setObjectName("KsDisclosureTitle")
        lay.addWidget(self.title)
        lay.addStretch(1)
        self.hint = QLabel("")
        self.hint.setObjectName("Faint")
        lay.addWidget(self.hint)
        self.setFixedHeight(34)

    def is_open(self):
        return self._open

    def set_open(self, value):
        value = bool(value)
        if value == self._open:
            return
        self._open = value
        end = 180.0 if value else 0.0  # chevron_down turned upside down
        if self.isVisible() and not motion.REDUCED:
            motion.tween(self.chevron, self.chevron._angle, end, self.chevron.set_angle,
                         ms=motion.BASE, curve=motion.EASE_OUT, key="_anim_angle")
        else:
            self.chevron.set_angle(end)
        self.toggled.emit(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_open(not self._open)
        super().mousePressEvent(event)


def build_qss(p):
    return f"""
/* ---------- kit: pills, disclosure, rows, icon tile ---------- */
QLabel#KsPill {{
    background-color: {p['raised']};
    color: {p['text2']};
    border: 1px solid {p['border']};
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#KsPill[tone="accent"] {{
    background-color: {p['selection']};
    color: {p['accent_line']};
    border: 1px solid {p['selection']};
}}
QLabel#KsPill[tone="info"] {{
    color: {p['info']};
}}
QLabel#KsPill[tone="success"] {{
    color: {p['success']};
}}
QLabel#KsPill[tone="warning"] {{
    color: {p['warning']};
}}
QFrame#KsDisclosure {{
    background-color: {p['raised']};
    border: 1px solid {p['border']};
    border-radius: 3px;
}}
QFrame#KsDisclosure:hover {{
    background-color: {p['hover']};
}}
QLabel#KsDisclosureTitle {{
    color: {p['text']};
    font-weight: 600;
    background: transparent;
}}
QFrame#KsDisclosure QLabel {{
    background: transparent;
}}
QFrame#KsIconTile {{
    background-color: {p['raised']};
    border: 1px solid {p['border']};
    border-radius: 4px;
}}
QLabel#KsEmptyTitle {{
    color: {p['text']};
    font-size: 15px;
    font-weight: 600;
}}
QLabel#KsMeta {{
    color: {p['text2']};
    font-size: 12px;
}}
QLabel#KsDesc {{
    color: {p['text3']};
    font-size: 12px;
}}
QLabel#KsChannel {{
    color: {p['text2']};
    font-size: 13px;
}}
QFrame#KsRow {{
    background-color: {p['panel']};
    border: none;
    border-bottom: 1px solid {p['border']};
}}
QFrame#KsRow:hover {{
    background-color: {p['raised']};
}}
QLabel#KsRowTitle {{
    font-size: 13px;
    font-weight: 600;
}}
QLabel#KsRowStatus {{
    color: {p['text2']};
    font-size: 12px;
}}
QLabel#KsRowStatus[state="active"] {{
    color: {p['accent_line']};
}}
QLabel#KsRowStatus[state="done"] {{
    color: {p['success']};
}}
QLabel#KsRowStatus[state="error"] {{
    color: {p['danger']};
}}
QLabel#KsRowStatus[state="cancelled"] {{
    color: {p['text3']};
}}
QLabel#KsRowMeta {{
    color: {p['text3']};
    font-size: 12px;
}}
QLabel#KsRowPct {{
    color: {p['text']};
    font-family: "{theme.mono_family()}";
    font-size: 13px;
    font-weight: 600;
}}
QProgressBar#KsBar {{
    background-color: {p['track']};
    border: none;
    border-radius: 2px;
    min-height: 3px;
    max-height: 3px;
}}
QProgressBar#KsBar::chunk {{
    background-color: {p['accent']};
    border-radius: 2px;
}}
QProgressBar#KsBar[state="queued"]::chunk {{
    background-color: {p['text3']};
}}
"""


theme.register_qss(build_qss)
