"""Shared helpers and styles for the pages."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QFrame,
)

import theme
from widgets import motion

PAGE_MAX_W = 900
PAGE_PAD = 32


def centered(inner, max_w=PAGE_MAX_W):
    """Wrap ``inner`` so it grows up to ``max_w`` and stays centred."""
    inner.setMaximumWidth(max_w)
    wrap = QWidget()
    wrap.setObjectName("Workspace")
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addStretch(1)
    lay.addWidget(inner, 100)
    lay.addStretch(1)
    return wrap


def page_header(title, subtitle=""):
    """Returns (layout, title_label, subtitle_label, actions_layout)."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    s = QLabel(subtitle)
    s.setObjectName("PageSub")
    col.addWidget(t)
    col.addWidget(s)
    row.addLayout(col, 1)
    actions = QHBoxLayout()
    actions.setSpacing(8)
    row.addLayout(actions)
    return row, t, s, actions


def page_button(text, icon=None, danger=False):
    b = QPushButton(text)
    b.setObjectName("PageButton")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if danger:
        b.setProperty("danger", True)
    if icon:
        theme.bind_icon(b, icon, "text2", 15)
    return b


def card():
    f = QFrame()
    f.setObjectName("Card")
    return f


def icon_label(name, px=36, key="text3"):
    """QLabel showing a themed icon; call retint() after a theme change."""
    lbl = _IconLabel(name, px, key)
    return lbl


class _IconLabel(QLabel):
    def __init__(self, name, px, key):
        super().__init__()
        self._n, self._px, self._k = name, px, key
        self.setFixedSize(px, px)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.retint()

    def retint(self):
        dpr = self.devicePixelRatioF() or 1.0
        pm = theme.icon(self._n, self._k, self._px).pixmap(
            self.size(), dpr)
        self.setPixmap(pm)


def empty_state(icon, title, text, button_text=None):
    """Returns (widget, icon_label, button)."""
    w = QWidget()
    w.setObjectName("Workspace")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 24, 24, 24)
    lay.setSpacing(8)
    lay.addStretch(1)
    ic = icon_label(icon, 40)
    lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignHCenter)
    lay.addSpacing(4)
    t = QLabel(title)
    t.setObjectName("EmptyHead")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(t)
    s = QLabel(text)
    s.setObjectName("Faint")
    s.setAlignment(Qt.AlignmentFlag.AlignCenter)
    s.setWordWrap(True)
    lay.addWidget(s)
    btn = None
    if button_text:
        lay.addSpacing(8)
        btn = page_button(button_text)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
    lay.addStretch(2)
    return w, ic, btn


def _qss(p):
    return f"""
/* ---------- pages ---------- */
#PageTitle {{
    font-size: 20px;
    font-weight: 600;
}}
#PageSub {{
    color: {p['text3']};
    font-size: 12px;
}}
#EmptyHead {{
    color: {p['text']};
    font-size: 15px;
    font-weight: 600;
}}
#CardTitle {{
    color: {p['text']};
    font-size: 13px;
    font-weight: 600;
}}
#SettingLabel {{
    color: {p['text']};
    font-size: 13px;
}}
#SettingHint {{
    color: {p['text3']};
    font-size: 12px;
}}
#SettingValue {{
    color: {p['text2']};
    font-size: 12px;
}}
#CardDivider {{
    background-color: {p['border']};
    border: none;
}}
QPushButton#PageButton {{
    background-color: {p['panel']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 3px;
    padding: 0px 12px;
    min-height: 28px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#PageButton:hover {{
    background-color: {p['hover']};
}}
QPushButton#PageButton:pressed {{
    background-color: {p['pressed']};
}}
QPushButton#PageButton:focus {{
    border-color: {p['accent_line']};
}}
QPushButton#PageButton:disabled {{
    color: {p['text3']};
    border-color: {p['border']};
    background-color: {p['panel']};
}}
QPushButton#PageButton[danger="true"]:hover {{
    background-color: {p['selection']};
    border-color: {p['danger']};
    color: {p['danger']};
}}
QLineEdit#SearchInput {{
    min-height: 30px;
    padding: 0px 10px 0px 4px;
}}
#HistoryList {{
    background-color: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 3px;
}}
#HistoryRow {{
    background-color: {p['panel']};
    border: none;
    border-bottom: 1px solid {p['border']};
}}
#HistoryRow:hover {{
    background-color: {p['raised']};
}}
#HistoryTitle {{
    font-size: 13px;
    font-weight: 600;
}}
#HistoryMeta {{
    color: {p['text3']};
    font-size: 11px;
}}
#HistoryChip {{
    color: {p['text2']};
    background-color: {p['raised']};
    border: 1px solid {p['border']};
    border-radius: 2px;
    padding: 1px 6px;
    font-size: 11px;
}}
#PageScroll, #PageScroll > QWidget > QWidget {{
    background: transparent;
}}
"""


theme.register_qss(_qss)


class SnapshotOverlay(QWidget):
    """Paints a pixmap of a widget's previous look on top of it, with an
    opacity and x offset we can animate. Cheap: one drawPixmap per frame,
    no graphics effects on the (large) real widgets underneath."""

    def __init__(self, host, pixmap):
        super().__init__(host)
        self.setObjectName("SnapshotOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._pm = pixmap
        self._opacity = 1.0
        self._dx = 0
        self.setGeometry(host.rect())
        self.show()
        self.raise_()

    def set_state(self, opacity, dx=0):
        self._opacity = opacity
        self._dx = dx
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setOpacity(self._opacity)
        p.drawPixmap(int(self._dx), 0, self._pm)


class PageTransition:
    """Crossfade + short slide when a QStackedWidget changes page."""

    SLIDE_IN = 14     # px the new page travels
    SLIDE_OUT = 8     # px the old snapshot drifts the other way

    def __init__(self, stack):
        self.stack = stack
        self._overlay = None
        self._page = None
        self._anim = None

    def finish(self):
        """Snap any running transition to its end state."""
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        if self._overlay is not None:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        if self._page is not None:
            self._page.move(0, 0)
            self._page = None

    def go(self, index):
        stack = self.stack
        self.finish()
        old_index = stack.currentIndex()
        if (index == old_index or not stack.isVisible() or motion.REDUCED
                or stack.currentWidget() is None):
            stack.setCurrentIndex(index)
            return
        snap = stack.currentWidget().grab()
        stack.setCurrentIndex(index)
        new = stack.currentWidget()
        direction = 1 if index > old_index else -1
        overlay = SnapshotOverlay(stack, snap)
        self._overlay, self._page = overlay, new

        def step(t):
            overlay.set_state(1.0 - t, -direction * self.SLIDE_OUT * t)
            new.move(int(direction * self.SLIDE_IN * (1.0 - t)), 0)

        step(0.0)
        self._anim = motion.tween(stack, 0.0, 1.0, step, ms=motion.BASE,
                                  finished=self._done, key="_anim_page")

    def _done(self):
        self._anim = None
        self.finish()
