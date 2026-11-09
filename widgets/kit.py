"""Shared building blocks for the refreshed video card / format picker /
download rows: pills, a theme-aware icon label, and their styles.

All colours come from ``theme.PALETTES``; nothing here hard-codes a hex.
"""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

import theme

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


class IconLabel(QWidget):
    """Draws a themed icon fresh on every paint, so it follows theme switches
    without needing an explicit retheme call."""

    def __init__(self, name, color_key="text2", px=16, parent=None):
        super().__init__(parent)
        self._name = name
        self._key = color_key
        self._px = px
        self.setFixedSize(px, px)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_icon(self, name, color_key=None):
        self._name = name
        if color_key:
            self._key = color_key
        self.update()

    def sizeHint(self):
        return QSize(self._px, self._px)

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
        self.chevron.set_icon("chevron_up" if value else "chevron_down")
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
