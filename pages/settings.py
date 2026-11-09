"""Settings page: grouped cards (downloads, sites, appearance, about)."""

from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

import theme
from pages.common import PAGE_MAX_W, PAGE_PAD, card, centered, page_button, page_header
from widgets.common import ElidedLabel, Segmented

GITHUB_URL = "https://github.com/Abdullah-Masood-05/Keepsake"


def _ytdlp_version():
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "unknown"


class _Group(QWidget):
    """A titled card holding rows separated by hairlines."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        head = QLabel(title.upper())
        head.setObjectName("SectionLabel")
        outer.addWidget(head)
        self.frame = card()
        self.body = QVBoxLayout(self.frame)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        outer.addWidget(self.frame)
        self._n = 0

    def add_row(self, label, hint="", control=None, controls=None):
        if self._n:
            line = QFrame()
            line.setObjectName("CardDivider")
            line.setFixedHeight(1)
            self.body.addWidget(line)
        self._n += 1
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(16)
        col = QVBoxLayout()
        col.setSpacing(2)
        l = QLabel(label)
        l.setObjectName("SettingLabel")
        col.addWidget(l)
        if hint:
            h = QLabel(hint)
            h.setObjectName("SettingHint")
            h.setWordWrap(True)
            col.addWidget(h)
        lay.addLayout(col, 1)
        for c in ([control] if control is not None else []) + list(controls or []):
            lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
        self.body.addWidget(row)
        return row


class SettingsPage(QWidget):
    change_folder = pyqtSignal()
    open_folder = pyqtSignal()
    show_sites = pyqtSignal()

    def __init__(self, config, cookie_browsers, version, parent=None):
        super().__init__(parent)
        self.setObjectName("Workspace")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(PAGE_PAD, 28, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setObjectName("Workspace")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, PAGE_PAD, 24)
        lay.setSpacing(20)
        head, _t, _s, _a = page_header("Settings", "Preferences are saved automatically")
        lay.addLayout(head)

        # --- Downloads ---------------------------------------------------
        g = _Group("Downloads")
        self.output_label = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle)
        self.output_label.setObjectName("SettingValue")
        self.output_label.setMaximumWidth(300)
        change = page_button("Change")
        change.clicked.connect(self.change_folder)
        open_btn = page_button("Open", "folder")
        open_btn.clicked.connect(self.open_folder)
        g.add_row("Save location", "Where finished downloads are written",
                  controls=[self.output_label, change, open_btn])
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setFixedSize(72, 30)
        self.concurrent_spin.setToolTip("Maximum simultaneous downloads")
        self.concurrent_spin.setValue(config.get("max_concurrent_downloads", 3))
        g.add_row("Parallel downloads", "How many downloads run at the same time",
                  self.concurrent_spin)
        lay.addWidget(g)

        # --- Sites & sign-in ---------------------------------------------
        g = _Group("Sites and sign-in")
        self.cookies_combo = QComboBox()
        self.cookies_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.polish_combo(self.cookies_combo)
        self.cookies_combo.setFixedSize(140, 30)
        for label, name in cookie_browsers:
            self.cookies_combo.addItem(label, name)
        self.cookies_combo.setToolTip(
            "Use your browser's sign-in for sites that need an account\n"
            "(private, age-restricted or members-only content).\n"
            "Firefox works best on Windows: Chromium browsers encrypt their\n"
            "cookies and must be closed while fetching."
        )
        idx = self.cookies_combo.findData(config.get("cookies_browser", ""))
        self.cookies_combo.setCurrentIndex(max(0, idx))
        g.add_row("Cookies from browser",
                  "Use your browser's sign-in for private, age-restricted or "
                  "members-only content. Firefox works best on Windows; Chromium "
                  "browsers must be closed while fetching.",
                  self.cookies_combo)
        sites = page_button("Supported sites", "globe")
        sites.setToolTip("Every site yt-dlp can download from")
        sites.clicked.connect(self.show_sites)
        g.add_row("Supported sites", "Every site yt-dlp can download from", sites)
        lay.addWidget(g)

        # --- Appearance --------------------------------------------------
        g = _Group("Appearance")
        self.theme_seg = Segmented(["Dark", "Light"], button_width=84)
        self.theme_seg.set_index(0 if theme.current() == "dark" else 1)
        g.add_row("Theme", "Dark or light interface", self.theme_seg)
        lay.addWidget(g)

        # --- About -------------------------------------------------------
        g = _Group("About")
        ver = QLabel(f"v{version}")
        ver.setObjectName("SettingValue")
        g.add_row("Keepsake", "Download videos, audio and thumbnails from 1,000+ sites",
                  ver)
        self.ffmpeg_dot = QFrame()
        self.ffmpeg_dot.setObjectName("Dot")
        self.ffmpeg_dot.setFixedSize(6, 6)
        self.ffmpeg_value = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle)
        self.ffmpeg_value.setObjectName("SettingValue")
        self.ffmpeg_value.setMaximumWidth(340)
        self.ffmpeg_row = g.add_row("FFmpeg", "Needed to merge streams and convert audio",
                                    controls=[self.ffmpeg_dot, self.ffmpeg_value])
        yt = QLabel(_ytdlp_version())
        yt.setObjectName("SettingValue")
        g.add_row("yt-dlp", "Extraction engine", yt)
        gh = page_button("GitHub", "external")
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        g.add_row("Source code", GITHUB_URL, gh)
        lay.addWidget(g)
        lay.addStretch(1)

        scroll.setWidget(centered(inner, PAGE_MAX_W + PAGE_PAD))
        outer.addWidget(scroll, 1)

    def set_ffmpeg(self, path, tip):
        self.ffmpeg_value.setText(path or "Not found")
        self.ffmpeg_value.setToolTip(tip)
        self.ffmpeg_dot.setProperty("state", "ok" if path else "warn")
        st = self.ffmpeg_dot.style()
        st.unpolish(self.ffmpeg_dot)
        st.polish(self.ffmpeg_dot)

    def retheme(self):
        pass
