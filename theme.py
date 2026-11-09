"""Central theming: palettes, Qt style sheet, QPalette, icons, window chrome.

Usage:
    theme.apply(app, "dark")          # or "light"; re-callable at runtime
    theme.icon("folder")              # QIcon in the current theme colours
    theme.bind_icon(button, "folder") # icon that follows theme switches

Design rules: very slightly rounded corners (3px controls/cards, 2px for
small parts like progress bars, tabs, checkboxes, scrollbar handles), 1px hairline borders, a single red
accent taken from the logo, blue only for informational states.
"""

import os
import sys
import tempfile

from PyQt6.QtCore import QByteArray, QEvent, QObject, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPalette,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QComboBox, QStyledItemDelegate

try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:  # pragma: no cover - QtSvg missing from the build
    QSvgRenderer = None

try:
    from PyQt6 import sip
except Exception:  # pragma: no cover
    import sip  # type: ignore


PALETTES = {
    "dark": {
        "bg": "#0E0E10",
        "panel": "#16161A",
        "raised": "#1F1F24",
        "hover": "#26262C",
        "pressed": "#2E2E35",
        "input": "#111114",
        "border": "#2A2A30",
        "border_strong": "#3A3A42",
        "text": "#EDEDED",
        "text2": "#9A9AA2",
        "text3": "#64646C",
        "accent": "#B80830",
        "accent_hover": "#D01848",
        "accent_pressed": "#990215",
        # Thin accent lines (tab underline, focus border) use the logo's
        # brighter red so they keep 3:1 contrast on the dark panels.
        "accent_line": "#D01848",
        "on_accent": "#FFFFFF",
        "selection": "#3A0F1A",
        "info": "#3D7BFF",
        "success": "#3E9B67",
        "warning": "#D19A2E",
        "danger": "#E5484D",
        "track": "#26262C",
    },
    "light": {
        "bg": "#FAFAFA",
        "panel": "#FFFFFF",
        "raised": "#F4F4F5",
        "hover": "#EDEDEF",
        "pressed": "#E4E4E7",
        "input": "#FFFFFF",
        "border": "#E4E4E7",
        "border_strong": "#D4D4D8",
        "text": "#18181B",
        "text2": "#5B5B64",
        "text3": "#A1A1AA",
        "accent": "#A80020",
        "accent_hover": "#B80830",
        "accent_pressed": "#900010",
        "accent_line": "#A80020",
        "on_accent": "#FFFFFF",
        "selection": "#F8E1E6",
        "info": "#2F6BF0",
        "success": "#2F8A57",
        "warning": "#B7791F",
        "danger": "#D93036",
        "track": "#E9E9EC",
    },
}

_current = "dark"
_bound = []  # (widget, icon name, colour key, size)


def current():
    return _current


def is_dark():
    return _current == "dark"


def color(key):
    return PALETTES[_current][key]


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

def _first_family(*names):
    families = set(QFontDatabase.families())
    for n in names:
        if n in families:
            return n
    return names[-1]


def ui_family():
    return _first_family("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI")


def mono_family():
    return _first_family("Cascadia Mono", "Consolas", "Courier New")


def tabular(font):
    """Ask for tabular (fixed-width) digits where Qt supports it (6.7+)."""
    try:
        font.setFeature(QFont.Tag("tnum"), 1)
    except Exception:
        pass
    return font


# --------------------------------------------------------------------------
# Icons (inline SVG, 24x24 grid, square caps/joins for crisp small glyphs)
# --------------------------------------------------------------------------

_SVG = {
    "sun": '<circle cx="12" cy="12" r="4" fill="none" stroke="{c}" stroke-width="1.8"/>'
           '<path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8'
           'M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" stroke="{c}" stroke-width="1.8" '
           'stroke-linecap="square"/>',
    "moon": '<path d="M19.5 14.6A8 8 0 0 1 9.4 4.5 8 8 0 1 0 19.5 14.6Z" fill="none" '
            'stroke="{c}" stroke-width="1.8" stroke-linejoin="miter"/>',
    "close": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11" stroke="{c}" stroke-width="1.8" '
             'stroke-linecap="square"/>',
    "folder": '<path d="M3.5 5.5h6l2 2h9v11h-17z" fill="none" stroke="{c}" '
              'stroke-width="1.8" stroke-linejoin="miter"/>',
    "download": '<path d="M12 4v11M7 10.5l5 5 5-5M5 19.5h14" fill="none" stroke="{c}" '
                'stroke-width="2" stroke-linecap="square" stroke-linejoin="miter"/>',
    "link": '<path d="M10 14l4-4M8.5 11.5L6 14a3 3 0 0 0 4 4l2.5-2.5M15.5 12.5L18 10a3 3 0 0 0-4-4'
            'l-2.5 2.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="square"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="{c}" stroke-width="2.4" '
             'stroke-linecap="square" stroke-linejoin="miter"/>',
    "chevron_down": '<path d="M6 9.5l6 6 6-6" fill="none" stroke="{c}" stroke-width="2" '
                    'stroke-linecap="square" stroke-linejoin="miter"/>',
    "chevron_up": '<path d="M6 14.5l6-6 6 6" fill="none" stroke="{c}" stroke-width="2" '
                  'stroke-linecap="square" stroke-linejoin="miter"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z" fill="{c}"/>',
    "clear": '<path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13" fill="none" stroke="{c}" '
             'stroke-width="1.8" stroke-linecap="square" stroke-linejoin="miter"/>',
}


# Extra QSS builders and icons registered by other modules (pages/widgets),
# so each can keep its own styles next to its code.
_EXTRA_QSS = []


def register_qss(builder):
    """builder(p) -> QSS string, appended to the global stylesheet."""
    if builder not in _EXTRA_QSS:
        _EXTRA_QSS.append(builder)


def register_icons(icons):
    """Add {name: svg_body} icons; bodies use {c} for the colour."""
    _SVG.update(icons)


def _svg_bytes(name, col):
    body = _SVG[name].format(c=col)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'width="24" height="24">{body}</svg>').encode("utf-8")


def _render(name, col, px, dpr=1.0):
    size = max(1, int(round(px * dpr)))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    if QSvgRenderer is not None:
        r = QSvgRenderer(QByteArray(_svg_bytes(name, col)))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r.render(p, QRectF(0, 0, size, size))
        p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name, color_key="text2", px=16):
    pal = PALETTES[_current]
    col = pal.get(color_key, color_key)
    app = QGuiApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    ic = QIcon()
    for scale in sorted({1.0, dpr, 2.0}):
        ic.addPixmap(_render(name, col, px, scale), QIcon.Mode.Normal)
        ic.addPixmap(_render(name, pal["text3"], px, scale), QIcon.Mode.Disabled)
    return ic


def bind_icon(widget, name, color_key="text2", px=16):
    """Set an icon on a button/action and keep it in sync with the theme."""
    widget.setIcon(icon(name, color_key, px))
    if hasattr(widget, "setIconSize"):
        widget.setIconSize(QSize(px, px))
    _bound.append((widget, name, color_key, px))


def _refresh_icons():
    alive = []
    for w, name, key, px in _bound:
        try:
            if sip.isdeleted(w):
                continue
        except TypeError:
            pass
        try:
            w.setIcon(icon(name, key, px))
        except RuntimeError:
            continue
        alive.append((w, name, key, px))
    _bound[:] = alive


def _asset_dir():
    d = os.path.join(tempfile.gettempdir(), "Keepsake-theme")
    os.makedirs(d, exist_ok=True)
    return d


def _asset(name, col, tag):
    """Write an SVG used by the style sheet (indicators, arrows); return a
    forward-slash path for url()."""
    path = os.path.join(_asset_dir(), f"{name}-{tag}-{col.strip('#')}.svg")
    if not os.path.isfile(path):
        with open(path, "wb") as f:
            f.write(_svg_bytes(name, col))
    return path.replace("\\", "/")


# --------------------------------------------------------------------------
# Style sheet
# --------------------------------------------------------------------------

def build_qss(p):
    check = _asset("check", p["on_accent"], "ind")
    down = _asset("chevron_down", p["text2"], "arrow")
    down_dis = _asset("chevron_down", p["text3"], "arrow")
    up = _asset("chevron_up", p["text2"], "arrow")
    mono = mono_family()
    return f"""
* {{
    outline: none;
}}
QWidget {{
    color: {p['text']};
    font-size: 13px;
    selection-background-color: {p['accent']};
    selection-color: {p['on_accent']};
}}
QMainWindow, QDialog, QMessageBox, #Workspace {{
    background-color: {p['bg']};
}}
QLabel {{
    background: transparent;
}}

/* ---------- structure ---------- */
#Header {{
    background-color: {p['panel']};
    border: none;
    border-bottom: 1px solid {p['border']};
}}
#Footer {{
    background-color: {p['panel']};
    border: none;
    border-top: 1px solid {p['border']};
}}
#SidePanel {{
    background-color: {p['panel']};
    border: none;
}}
#Card {{
    background-color: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 3px;
}}
QSplitter::handle {{
    background-color: {p['border']};
}}
#Hairline {{
    background-color: {p['border']};
    border: none;
}}

/* ---------- typography ---------- */
#AppName {{
    font-size: 14px;
    font-weight: 600;
}}
#Version {{
    color: {p['text3']};
    font-family: "{mono}";
    font-size: 11px;
}}
#SectionLabel {{
    color: {p['text3']};
    font-size: 11px;
    font-weight: 600;
}}
#VideoTitle {{
    font-size: 19px;
    font-weight: 600;
}}
#Muted {{
    color: {p['text2']};
}}
#Faint {{
    color: {p['text3']};
    font-size: 12px;
}}
#StatValue {{
    font-family: "{mono}";
    font-size: 13px;
}}
#Metric {{
    color: {p['text2']};
    font-family: "{mono}";
    font-size: 11px;
}}
#FooterText {{
    color: {p['text2']};
    font-size: 12px;
}}
#FooterValue {{
    color: {p['text']};
    font-size: 12px;
}}
#StatusText {{
    color: {p['text2']};
    font-size: 12px;
}}
#StatusText[state="error"] {{
    color: {p['danger']};
}}
#StatusText[state="ok"] {{
    color: {p['success']};
}}
#StatusText[state="warn"] {{
    color: {p['warning']};
}}
#EmptyTitle {{
    color: {p['text2']};
    font-size: 13px;
    font-weight: 600;
}}
#Thumb {{
    background: transparent;
    border: none;
    color: {p['text3']};
}}
#Dot {{
    background-color: {p['text3']};
    border: none;
}}
#Dot[state="ok"] {{
    background-color: {p['success']};
}}
#Dot[state="warn"] {{
    background-color: {p['warning']};
}}

/* ---------- buttons ---------- */
QPushButton, QToolButton {{
    background-color: {p['raised']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 3px;
    padding: 0px 14px;
    min-height: 30px;
    font-weight: 500;
}}
QPushButton:hover, QToolButton:hover {{
    background-color: {p['hover']};
    border-color: {p['border_strong']};
}}
QPushButton:pressed, QToolButton:pressed {{
    background-color: {p['pressed']};
}}
QPushButton:focus, QToolButton:focus {{
    border-color: {p['text3']};
}}
QPushButton:disabled, QToolButton:disabled {{
    background-color: {p['panel']};
    color: {p['text3']};
    border-color: {p['border']};
}}
QPushButton#Primary, QPushButton#Fetch {{
    background-color: {p['accent']};
    color: {p['on_accent']};
    border: 1px solid {p['accent']};
    font-weight: 600;
}}
QPushButton#Primary:hover, QPushButton#Fetch:hover {{
    background-color: {p['accent_hover']};
    border-color: {p['accent_hover']};
}}
QPushButton#Primary:pressed, QPushButton#Fetch:pressed {{
    background-color: {p['accent_pressed']};
    border-color: {p['accent_pressed']};
}}
QPushButton#Primary:focus, QPushButton#Fetch:focus {{
    border-color: {p['accent_pressed']};
}}
QPushButton#Primary:disabled, QPushButton#Fetch:disabled {{
    background-color: {p['raised']};
    color: {p['text3']};
    border-color: {p['border']};
}}
QPushButton#Fetch {{
    padding: 0px 22px;
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
}}
QPushButton#Fetch, QPushButton#Primary, QLineEdit#UrlInput {{
    min-height: 38px;
}}
QPushButton#IconButton {{
    background-color: transparent;
    border: 1px solid transparent;
    padding: 0px;
    min-height: 0px;
}}
QPushButton#IconButton:hover {{
    background-color: {p['hover']};
    border-color: {p['border']};
}}
QPushButton#IconButton:pressed {{
    background-color: {p['pressed']};
}}
QPushButton#IconButton:focus {{
    border-color: {p['border_strong']};
}}
QPushButton#IconButton[danger="true"]:hover {{
    background-color: {p['selection']};
    border-color: {p['danger']};
}}
QPushButton#LinkButton {{
    background-color: transparent;
    border: none;
    color: {p['text2']};
    padding: 0px 4px;
    min-height: 0px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#LinkButton:hover {{
    color: {p['accent_hover']};
    text-decoration: underline;
}}
QPushButton#LinkButton:pressed {{
    color: {p['accent_pressed']};
}}
QPushButton#LinkButton:focus {{
    color: {p['accent_line']};
}}
QPushButton#LinkButton:disabled {{
    color: {p['text3']};
}}

/* ---------- segmented control ---------- */
#Segmented {{
    background-color: {p['input']};
    border: 1px solid {p['border']};
    border-radius: 2px;
}}
#Segmented QPushButton {{
    background-color: transparent;
    color: {p['text2']};
    border: none;
    border-radius: 0px;
    border-right: 1px solid {p['border']};
    border-bottom: 2px solid transparent;
    padding: 0px 8px;
    min-height: 28px;
    font-weight: 500;
}}
#Segmented QPushButton[first="true"] {{
    border-top-left-radius: 1px;
    border-bottom-left-radius: 1px;
}}
#Segmented QPushButton[last="true"] {{
    border-right: none;
    border-top-right-radius: 1px;
    border-bottom-right-radius: 1px;
}}
#Segmented QPushButton:hover {{
    color: {p['text']};
    background-color: {p['raised']};
}}
#Segmented QPushButton:checked {{
    color: {p['text']};
    background-color: {p['hover']};
    border-bottom: 2px solid {p['accent_line']};
    font-weight: 600;
}}
#Segmented QPushButton:focus {{
    color: {p['text']};
}}
#Segmented[compact="true"] QPushButton {{
    padding: 0px;
    min-height: 26px;
}}

/* ---------- inputs ---------- */
QLineEdit, QSpinBox, QComboBox, QTextBrowser, QPlainTextEdit {{
    background-color: {p['input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 3px;
}}
QLineEdit {{
    padding: 0px 10px;
    min-height: 30px;
}}
QLineEdit#UrlInput {{
    font-size: 14px;
    padding: 0px 12px 0px 6px;
    border-right: none;
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
    border-color: {p['border_strong']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QComboBox:on {{
    border-color: {p['accent_line']};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    color: {p['text3']};
    background-color: {p['panel']};
    border-color: {p['border']};
}}

QComboBox {{
    padding: 0px 10px;
    min-height: 30px;
    combobox-popup: 0;
}}
QComboBox#FooterCombo {{
    min-height: 22px;
    padding: 0px 8px;
    font-size: 12px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
}}
QComboBox::down-arrow {{
    image: url("{down}");
    width: 12px;
    height: 12px;
}}
QComboBox::down-arrow:disabled {{
    image: url("{down_dis}");
}}
QComboBox QAbstractItemView {{
    background-color: {p['raised']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    padding: 4px 0px;
    outline: none;
    selection-background-color: {p['hover']};
    selection-color: {p['text']};
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 0px 10px;
    border: none;
}}
QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}

QSpinBox {{
    border-radius: 2px;
    padding: 0px 6px 0px 10px;
    min-height: 26px;
    font-family: "{mono}";
    font-size: 12px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 18px;
    border: none;
    border-left: 1px solid {p['border']};
    background-color: {p['raised']};
}}
QSpinBox::up-button {{
    subcontrol-position: top right;
    border-bottom: 1px solid {p['border']};
    border-top-right-radius: 2px;
    margin: 1px 1px 0px 0px;
}}
QSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 2px;
    margin: 0px 1px 1px 0px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {p['hover']};
}}
QSpinBox::up-arrow {{
    image: url("{up}");
    width: 8px;
    height: 8px;
}}
QSpinBox::down-arrow {{
    image: url("{down}");
    width: 8px;
    height: 8px;
}}

QCheckBox {{
    spacing: 8px;
    color: {p['text']};
    background: transparent;
}}
QCheckBox:disabled {{
    color: {p['text3']};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {p['border_strong']};
    background-color: {p['input']};
    border-radius: 2px;
}}
QCheckBox::indicator:hover {{
    border-color: {p['text3']};
}}
QCheckBox:focus::indicator {{
    border-color: {p['accent_line']};
}}
QCheckBox::indicator:checked {{
    background-color: {p['accent']};
    border-color: {p['accent']};
    image: url("{check}");
}}
QCheckBox::indicator:checked:hover {{
    background-color: {p['accent_hover']};
    border-color: {p['accent_hover']};
}}
QCheckBox::indicator:disabled {{
    background-color: {p['panel']};
    border-color: {p['border']};
}}

/* ---------- table ---------- */
QTableWidget, QTableView {{
    background-color: {p['input']};
    alternate-background-color: {p['panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 3px;
    gridline-color: {p['border']};
    selection-background-color: {p['selection']};
    selection-color: {p['text']};
    font-size: 12px;
}}
QTableWidget:disabled, QTableView:disabled {{
    color: {p['text3']};
}}
QTableView::item {{
    padding: 0px 8px;
    border: none;
}}
QTableView::item:hover {{
    background-color: {p['raised']};
}}
QTableView::item:selected {{
    background-color: {p['selection']};
    color: {p['text']};
}}
QHeaderView {{
    background-color: transparent;
    border: none;
}}
QHeaderView::section {{
    background-color: {p['input']};
    color: {p['text3']};
    border: none;
    border-bottom: 1px solid {p['border']};
    padding: 0px 8px 0px 11px;
    min-height: 28px;
    font-size: 11px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background-color: {p['input']};
    border: none;
}}

/* ---------- side tabs (underline) ---------- */
#SideHeader {{
    background-color: {p['panel']};
    border: none;
    border-bottom: 1px solid {p['border']};
}}
QTabBar#SideTabs {{
    background: transparent;
}}
QTabBar#SideTabs::tab {{
    background: transparent;
    color: {p['text2']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 0px 2px;
    margin-right: 20px;
    min-height: 44px;
    font-weight: 600;
    font-size: 12px;
}}
QTabBar#SideTabs::tab {{
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
}}
QTabBar#SideTabs::tab:hover {{
    color: {p['text']};
}}
QTabBar#SideTabs::tab:selected {{
    color: {p['text']};
    border-bottom: 2px solid {p['accent_line']};
}}

/* ---------- scroll areas / bars ---------- */
QScrollArea {{
    background: transparent;
    border: none;
}}
#DownloadsContainer, #DownloadsScroll > QWidget {{
    background-color: {p['panel']};
}}
QScrollBar:vertical {{
    background: transparent;
    border: none;
    width: 10px;
    margin: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    border: none;
    height: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {p['border_strong']};
    min-height: 32px;
    margin: 2px 2px 2px 2px;
    border: none;
    border-radius: 2px;
}}
QScrollBar::handle:horizontal {{
    background-color: {p['border_strong']};
    min-width: 32px;
    margin: 2px 2px 2px 2px;
    border: none;
    border-radius: 2px;
}}
QScrollBar::handle:hover {{
    background-color: {p['text3']};
}}
QScrollBar::handle:pressed {{
    background-color: {p['text2']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
    border: none;
    background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* ---------- progress ---------- */
QProgressBar {{
    background-color: {p['track']};
    border: none;
    border-radius: 2px;
    min-height: 4px;
    max-height: 4px;
}}
QProgressBar::chunk {{
    background-color: {p['accent']};
    border-radius: 2px;
}}
QProgressBar[state="done"]::chunk {{
    background-color: {p['success']};
}}
QProgressBar[state="error"]::chunk {{
    background-color: {p['danger']};
}}
QProgressBar[state="cancelled"]::chunk {{
    background-color: {p['text3']};
}}
QProgressBar[state="queued"]::chunk {{
    background-color: {p['info']};
}}

/* ---------- download rows ---------- */
#DownloadItem {{
    background-color: {p['panel']};
    border: none;
    border-bottom: 1px solid {p['border']};
}}
#DownloadItem:hover {{
    background-color: {p['raised']};
}}
#ItemTitle {{
    font-size: 13px;
    font-weight: 600;
}}
#ItemStatus {{
    color: {p['text2']};
    font-size: 12px;
}}
#ItemStatus[state="error"] {{
    color: {p['danger']};
}}
#ItemStatus[state="done"] {{
    color: {p['success']};
}}

/* ---------- history ---------- */
QTextBrowser {{
    background-color: {p['panel']};
    border: none;
    padding: 0px;
}}

/* ---------- tooltips / menus / dialogs ---------- */
QToolTip {{
    background-color: {p['raised']};
    color: {p['text']};
    border: 1px solid {p['border_strong']};
    border-radius: 2px;
    padding: 4px 8px;
    font-size: 12px;
}}
QMenu {{
    background-color: {p['raised']};
    border: 1px solid {p['border_strong']};
    border-radius: 3px;
    padding: 4px 0px;
}}
QMenu::item {{
    padding: 6px 16px;
}}
QMenu::item:selected {{
    background-color: {p['hover']};
}}
QMessageBox QLabel {{
    color: {p['text']};
    font-size: 13px;
}}
QMessageBox QPushButton {{
    min-width: 72px;
}}
""" + "".join(b(p) for b in _EXTRA_QSS)


def build_palette(p):
    pal = QPalette()
    c = QColor
    roles = {
        QPalette.ColorRole.Window: p["bg"],
        QPalette.ColorRole.WindowText: p["text"],
        QPalette.ColorRole.Base: p["input"],
        QPalette.ColorRole.AlternateBase: p["panel"],
        QPalette.ColorRole.Text: p["text"],
        QPalette.ColorRole.Button: p["raised"],
        QPalette.ColorRole.ButtonText: p["text"],
        QPalette.ColorRole.BrightText: p["accent_hover"],
        QPalette.ColorRole.Highlight: p["accent"],
        QPalette.ColorRole.HighlightedText: p["on_accent"],
        QPalette.ColorRole.ToolTipBase: p["raised"],
        QPalette.ColorRole.ToolTipText: p["text"],
        QPalette.ColorRole.PlaceholderText: p["text3"],
        QPalette.ColorRole.Link: p["info"],
        QPalette.ColorRole.LinkVisited: p["info"],
        QPalette.ColorRole.Light: p["border_strong"],
        QPalette.ColorRole.Midlight: p["border"],
        QPalette.ColorRole.Mid: p["border"],
        QPalette.ColorRole.Dark: p["bg"],
        QPalette.ColorRole.Shadow: "#000000",
    }
    for role, value in roles.items():
        pal.setColor(role, c(value))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, c(p["text3"]))
    return pal


# --------------------------------------------------------------------------
# Windows chrome: dark/light title bar, caption colour, small corners
# --------------------------------------------------------------------------

def _is_windows_platform():
    return sys.platform == "win32" and QGuiApplication.platformName() == "windows"


def _colorref(hex_color):
    q = QColor(hex_color)
    return q.red() | (q.green() << 8) | (q.blue() << 16)


def apply_window_chrome(widget):
    """Dark/light title bar matching the header and small window corners
    (Windows 11). Silently does nothing elsewhere."""
    if not _is_windows_platform() or widget is None or not widget.isWindow():
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(widget.winId()))
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ]

        def setattr_int(attr, value):
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        dark = 1 if is_dark() else 0
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (19 on pre-20H1 Windows 10)
        if setattr_int(20, dark) != 0:
            setattr_int(19, dark)
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33: small rounding (3) for real
        # windows to match the 3px controls, none (1) for popups/tooltips.
        popup = (widget.windowFlags() & Qt.WindowType.Popup) == Qt.WindowType.Popup
        setattr_int(33, 1 if popup else 3)
        p = PALETTES[_current]
        if not popup:
            # Caption / caption text / border colours (Windows 11 22000+).
            setattr_int(35, _colorref(p["panel"]))
            setattr_int(36, _colorref(p["text"]))
            setattr_int(34, _colorref(p["border"]))
    except Exception:
        pass


class _ChromeFilter(QObject):
    """Applies window chrome to every top-level window as it is shown
    (main window, message boxes, combo popups, tooltips)."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            try:
                if obj.isWidgetType() and obj.isWindow():
                    apply_window_chrome(obj)
            except Exception:
                pass
        return False


_filter = None


def polish_combo(combo):
    combo.setItemDelegate(QStyledItemDelegate(combo))


def shutdown(app):
    """Drop module-level references to Qt objects before the interpreter
    tears down; otherwise Python may finalise them after QApplication and
    crash (access violation) on exit."""
    global _filter
    _bound.clear()
    if _filter is not None:
        try:
            app.removeEventFilter(_filter)
        except RuntimeError:
            pass
        _filter = None


def apply(app, name):
    """Apply theme ``name`` ('dark' / 'light') to the whole application."""
    global _current, _filter
    _current = name if name in PALETTES else "dark"
    p = PALETTES[_current]
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    base = QFont(ui_family())
    base.setPixelSize(13)
    base.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(tabular(base))
    app.setPalette(build_palette(p))
    app.setStyleSheet(build_qss(p))
    _refresh_icons()
    if _filter is None:
        _filter = _ChromeFilter(app)
        app.installEventFilter(_filter)
    for w in app.topLevelWidgets():
        if w.isVisible():
            apply_window_chrome(w)
