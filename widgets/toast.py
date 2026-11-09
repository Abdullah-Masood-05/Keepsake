"""Small bottom-right notifications (modelled on the Tauri Toasts.tsx)."""

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

import theme
from widgets.common import ElidedLabel, icon_button

_KIND_ICON = {"success": "check_circle", "error": "x_circle",
              "info": "info", "warning": "warning"}
_KIND_COLOR = {"success": "success", "error": "danger",
               "info": "info", "warning": "warning"}
_MARGIN = 16
# Keep clear of the action row (Download button) at the bottom of Home.
_BOTTOM_CLEAR = 88
_GAP = 8
_WIDTH = 340


class Toast(QFrame):
    def __init__(self, kind, text, action_text, action_cb, on_close, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", kind)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(_WIDTH)
        self._kind = kind
        self._on_close = on_close
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 8, 10)
        lay.setSpacing(10)
        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        msg = QLabel(text)
        msg.setObjectName("ToastText")
        msg.setWordWrap(True)
        lay.addWidget(msg, 1)
        if action_text:
            btn = QPushButton(action_text)
            btn.setObjectName("LinkButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def run():
                if action_cb:
                    action_cb()
                self.dismiss()
            btn.clicked.connect(run)
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
        close = icon_button("close", "Dismiss", size=22, icon_px=12)
        close.clicked.connect(self.dismiss)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self.retheme()
        self.adjustSize()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)

    def start(self, ms):
        self._timer.start(ms)

    def dismiss(self):
        if self._on_close:
            cb, self._on_close = self._on_close, None
            cb(self)

    def retheme(self):
        dpr = self.devicePixelRatioF() or 1.0
        ic = theme.icon(_KIND_ICON[self._kind], _KIND_COLOR[self._kind], 18)
        self.icon.setPixmap(ic.pixmap(self.icon.size(), dpr))


class ToastManager(QObject):
    """Stacks toasts in the bottom-right corner of ``host``."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._toasts = []
        host.installEventFilter(self)

    def show(self, text, kind="info", action_text=None, action_cb=None, ms=4000):
        t = Toast(kind, text, action_text, action_cb, self._remove, self._host)
        self._toasts.append(t)
        t.show()
        t.raise_()
        t.start(ms)
        # Keep the stack short.
        while len(self._toasts) > 4:
            self._remove(self._toasts[0])
        self._layout()
        return t

    def _remove(self, t):
        if t in self._toasts:
            self._toasts.remove(t)
            t.hide()
            t.deleteLater()
            self._layout()

    def _layout(self):
        y = self._host.height() - _BOTTOM_CLEAR
        for t in reversed(self._toasts):
            t.adjustSize()
            y -= t.height()
            t.move(self._host.width() - _MARGIN - t.width(), y)
            t.raise_()
            y -= _GAP

    def retheme(self):
        for t in self._toasts:
            t.retheme()

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Type.Resize:
            self._layout()
        return False


def _qss(p):
    return f"""
/* ---------- toasts ---------- */
#Toast {{
    background-color: {p['raised']};
    border: 1px solid {p['border_strong']};
    border-left: 3px solid {p['info']};
    border-radius: 3px;
}}
#Toast[kind="success"] {{ border-left-color: {p['success']}; }}
#Toast[kind="error"] {{ border-left-color: {p['danger']}; }}
#Toast[kind="warning"] {{ border-left-color: {p['warning']}; }}
#ToastText {{
    color: {p['text']};
    font-size: 13px;
}}
"""


theme.register_qss(_qss)
