"""Left navigation sidebar (modelled on the Tauri app's Sidebar.tsx)."""

import os

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

import app_paths
import theme
from widgets import motion
from widgets.common import icon_button

NAV_ITEMS = [("Home", "home"), ("Downloads", "downloads"),
             ("History", "history"), ("Settings", "settings")]
ICON_PX = 18


class NavButton(QPushButton):
    def __init__(self, label, icon_name, parent=None):
        super().__init__("  " + label, parent)
        self.icon_name = icon_name
        self.setObjectName("NavItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setIconSize(QSize(ICON_PX, ICON_PX))
        self.badge = QLabel("", self)
        self.badge.setObjectName("NavBadge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.hide()
        self._badge_n = 0
        self._badge_w = 18

    def set_badge(self, n):
        prev = self._badge_n
        self._badge_n = n
        self.badge.setVisible(n > 0)
        self.badge.setText(str(n) if n < 100 else "99+")
        self.badge.adjustSize()
        self._badge_w = max(18, self.badge.width() + 2)
        self._place_badge()
        if n > prev and self.isVisible():
            self._pop_badge()

    def _badge_rect(self, scale=1.0):
        w, h = self._badge_w, 18
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        cx = self.width() - 12 - w / 2
        cy = self.height() / 2
        return QRect(round(cx - sw / 2), round(cy - sh / 2), sw, sh)

    def _place_badge(self):
        self.badge.setGeometry(self._badge_rect())

    def _pop_badge(self):
        """Scale up from 75% with a slight overshoot."""
        motion.tween(self, 0.75, 1.0,
                     lambda v: self.badge.setGeometry(self._badge_rect(v)),
                     ms=motion.BASE, curve=motion.EASE_SPRING,
                     finished=self._place_badge, key="_anim_badge")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_badge()

    def retheme(self):
        dpr = self.devicePixelRatioF() or 1.0
        size = QSize(ICON_PX, ICON_PX)
        ic = QIcon()
        off = theme.icon(self.icon_name, "text2", ICON_PX).pixmap(size, dpr)
        on = theme.icon(self.icon_name, "accent_line", ICON_PX).pixmap(size, dpr)
        ic.addPixmap(off, QIcon.Mode.Normal, QIcon.State.Off)
        ic.addPixmap(off, QIcon.Mode.Active, QIcon.State.Off)
        ic.addPixmap(on, QIcon.Mode.Normal, QIcon.State.On)
        ic.addPixmap(on, QIcon.Mode.Active, QIcon.State.On)
        self.setIcon(ic)


class Sidebar(QFrame):
    page_requested = pyqtSignal(int)
    theme_toggle_requested = pyqtSignal()

    def __init__(self, app_name, version, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(212)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # --- brand ---
        brand = QFrame()
        brand.setObjectName("SidebarBrand")
        brand.setFixedHeight(64)
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(10)
        logo = QLabel()
        pm = QPixmap(app_paths.resource_path("resources", "icons", "app.png"))
        if not pm.isNull():
            dpr = self.devicePixelRatioF() or 1.0
            pm = pm.scaled(int(28 * dpr), int(28 * dpr),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            logo.setPixmap(pm)
        logo.setFixedSize(28, 28)
        bl.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        name = QLabel(app_name)
        name.setObjectName("AppName")
        ver = QLabel(f"v{version}")
        ver.setObjectName("Version")
        col.addWidget(name)
        col.addWidget(ver)
        bl.addLayout(col)
        bl.addStretch(1)
        lay.addWidget(brand)

        # --- nav ---
        nav = QVBoxLayout()
        nav.setContentsMargins(0, 12, 0, 0)
        nav.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for i, (label, icon_name) in enumerate(NAV_ITEMS):
            b = NavButton(label, icon_name)
            b.setToolTip(f"{label} (Ctrl+{i + 1})")
            self.group.addButton(b, i)
            self.buttons.append(b)
            nav.addWidget(b)
        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.page_requested)
        # Accent bar that slides between items (the buttons' own left border
        # stays transparent and just reserves the space).
        self.indicator = QFrame(self)
        self.indicator.setObjectName("NavIndicator")
        self.indicator.setFixedWidth(3)
        self.indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.indicator.resize(3, 38)
        self.group.idToggled.connect(self._on_toggled)
        lay.addLayout(nav)
        lay.addStretch(1)

        # --- footer: ffmpeg status + theme toggle ---
        foot = QFrame()
        foot.setObjectName("SidebarFoot")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 10, 12, 10)
        fl.setSpacing(8)
        self.ffmpeg_dot = QFrame()
        self.ffmpeg_dot.setObjectName("Dot")
        self.ffmpeg_dot.setFixedSize(6, 6)
        fl.addWidget(self.ffmpeg_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.ffmpeg_label = QLabel("")
        self.ffmpeg_label.setObjectName("FooterText")
        fl.addWidget(self.ffmpeg_label)
        fl.addStretch(1)
        self.theme_btn = icon_button("sun", "Switch theme", size=28, icon_px=16)
        self.theme_btn.clicked.connect(self.theme_toggle_requested)
        fl.addWidget(self.theme_btn)
        lay.addWidget(foot)

        self.retheme()

    def set_page(self, i):
        self.buttons[i].setChecked(True)

    def _target_pos(self):
        b = self.group.checkedButton()
        return b.pos() if b is not None else QPoint(0, 0)

    def _snap_indicator(self):
        self.layout().activate()
        self.indicator.setFixedHeight(self.buttons[0].height())
        self.indicator.move(self._target_pos())
        self.indicator.raise_()

    def _on_toggled(self, _i, checked):
        if not checked:
            return
        if not self.isVisible() or motion.REDUCED:
            self._snap_indicator()
            return
        self.layout().activate()
        motion.animate(self.indicator, b"pos", None, self._target_pos(),
                       ms=motion.BASE, curve=motion.EASE_IN_OUT)

    def showEvent(self, e):
        super().showEvent(e)
        self._snap_indicator()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.isVisible():
            self._snap_indicator()

    def set_badge(self, index, n):
        self.buttons[index].set_badge(n)

    def set_ffmpeg(self, path, tip):
        self.ffmpeg_label.setText("FFmpeg ready" if path else "FFmpeg not found")
        self.ffmpeg_label.setToolTip(tip)
        self.ffmpeg_dot.setProperty("state", "ok" if path else "warn")
        self.ffmpeg_dot.setToolTip(tip)
        st = self.ffmpeg_dot.style()
        st.unpolish(self.ffmpeg_dot)
        st.polish(self.ffmpeg_dot)

    def retheme(self):
        for b in self.buttons:
            b.retheme()
        # Shows the theme you would switch to.
        dark = theme.is_dark()
        self.theme_btn.setIcon(theme.icon("sun" if dark else "moon", "text2", 16))
        self.theme_btn.setToolTip("Switch to light theme" if dark else "Switch to dark theme")


def _qss(p):
    return f"""
/* ---------- sidebar ---------- */
#Sidebar {{
    background-color: {p['panel']};
    border: none;
    border-right: 1px solid {p['border']};
}}
#SidebarBrand, #SidebarFoot {{
    background: transparent;
    border: none;
}}
#SidebarFoot {{
    border-top: 1px solid {p['border']};
}}
QPushButton#NavItem {{
    background-color: transparent;
    color: {p['text2']};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    text-align: left;
    padding: 0px 14px 0px 13px;
    min-height: 38px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#NavItem:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QPushButton#NavItem:pressed {{
    background-color: {p['pressed']};
}}
QPushButton#NavItem:checked {{
    background-color: {p['raised']};
    color: {p['text']};
}}
QFrame#NavIndicator {{
    background-color: {p['accent_line']};
    border: none;
}}
QPushButton#NavItem:focus {{
    background-color: {p['hover']};
}}
QPushButton#NavItem:checked:focus {{
    background-color: {p['raised']};
}}
QLabel#NavBadge {{
    background-color: {p['accent']};
    color: {p['on_accent']};
    border-radius: 2px;
    padding: 0px 5px;
    font-size: 11px;
    font-weight: 600;
}}
"""


theme.register_qss(_qss)
