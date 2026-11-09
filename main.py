import gc
import html
import os
import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextBrowser, QScrollArea, QFrame,
    QFileDialog, QMessageBox, QSizePolicy, QSplitter, QCheckBox, QSpinBox,
    QTabBar, QStackedWidget, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap

import app_paths
import config_manager
import theme
from download_manager import DownloadManager
from workers.fetch_worker import FetchWorker
from widgets.common import ElidedLabel, Segmented, icon_button, section_label
from widgets.video_card import VideoCard
from widgets.download_item import DownloadItemWidget
from widgets.format_selector import FormatSelector
from widgets.supported_sites_dialog import SupportedSitesDialog

APP_TITLE = "Satchel"
VERSION = "2.1.1"
APP_USER_MODEL_ID = "AbdullahMasood.Satchel"

# Audio containers whose cover art yt-dlp can embed without mutagen.
_EMBED_THUMB_AUDIO = {"mp3", "m4a"}

# Browsers yt-dlp can read cookies from (label, yt-dlp name). Cookies let
# sites that need a sign-in (private, age-restricted, members-only) work.
_COOKIE_BROWSERS = [("Off", ""), ("Firefox", "firefox"), ("Chrome", "chrome"),
                    ("Edge", "edge"), ("Brave", "brave"), ("Opera", "opera"),
                    ("Vivaldi", "vivaldi"), ("Chromium", "chromium")]
if sys.platform == "darwin":
    _COOKIE_BROWSERS.insert(2, ("Safari", "safari"))


def _app_icon():
    # PNG loads without any image plugin; the ICO adds crisp small sizes
    # when Qt's ico plugin is available.
    icon = QIcon()
    for name in ("app.png", "app.ico"):
        path = app_paths.resource_path("resources", "icons", name)
        if os.path.isfile(path):
            icon.addFile(path)
    return icon


def _set_windows_app_id():
    """Give the process its own taskbar identity so Windows shows our icon
    instead of the python.exe one."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1080, 700)
        self.resize(1240, 800)

        self.config = config_manager.load()
        self.theme = self.config.get("theme", "dark")
        if self.theme not in theme.PALETTES:
            self.theme = "dark"
        self.out_dir = self.config.get("last_folder") or app_paths.downloads_dir()
        self.ffmpeg_path = app_paths.find_ffmpeg()

        self.fetch_worker = None
        self.download_widgets = {}
        self.current_video_info = None

        self.dl_manager = DownloadManager(self)
        self.dl_manager.set_max_concurrent(self.config.get("max_concurrent_downloads", 3))
        self.dl_manager.download_added.connect(self._on_download_added)
        self.dl_manager.download_progress.connect(self._on_download_progress)
        self.dl_manager.download_status.connect(self._on_download_status)
        self.dl_manager.download_complete.connect(self._on_download_complete)
        self.dl_manager.download_error.connect(self._on_download_error)
        self.dl_manager.download_cancelled.connect(self._on_download_cancelled)

        self._pending_out_dir = ""
        self._setup_ui()
        self._apply_theme()
        self._update_ffmpeg_status()
        self._update_output_label()
        self._update_downloads_empty()

    # ================================================================== UI

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("Workspace")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._create_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._create_workspace())
        splitter.addWidget(self._create_side_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([840, 400])
        root.addWidget(splitter, 1)

        root.addWidget(self._create_footer())

    def _create_header(self):
        bar = QFrame()
        bar.setObjectName("Header")
        bar.setFixedHeight(48)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        logo = QLabel()
        logo_path = app_paths.resource_path("resources", "icons", "app.png")
        pm = QPixmap(logo_path)
        if not pm.isNull():
            dpr = self.devicePixelRatioF() or 1.0
            pm = pm.scaled(
                int(24 * dpr), int(24 * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pm.setDevicePixelRatio(dpr)
            logo.setPixmap(pm)
        logo.setFixedSize(24, 24)
        lay.addWidget(logo)
        lay.addSpacing(10)

        name = QLabel(APP_TITLE)
        name.setObjectName("AppName")
        lay.addWidget(name)
        lay.addSpacing(8)
        version = QLabel(f"v{VERSION}")
        version.setObjectName("Version")
        lay.addWidget(version, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addStretch(1)

        theme_lbl = section_label("Theme")
        lay.addWidget(theme_lbl)
        lay.addSpacing(10)
        self.theme_switch = Segmented(["", ""], compact=True, button_width=32)
        dark_btn, light_btn = self.theme_switch.buttons
        theme.bind_icon(dark_btn, "moon", "text2", 14)
        theme.bind_icon(light_btn, "sun", "text2", 14)
        dark_btn.setToolTip("Dark theme")
        light_btn.setToolTip("Light theme")
        self.theme_switch.set_index(0 if self.theme == "dark" else 1)
        self.theme_switch.group.idToggled.connect(self._on_theme_toggled)
        lay.addWidget(self.theme_switch)
        return bar

    def _create_workspace(self):
        page = QWidget()
        page.setObjectName("Workspace")
        page.setMinimumWidth(640)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # --- URL bar: input with the Fetch button attached -------------
        url_row = QHBoxLayout()
        url_row.setContentsMargins(0, 0, 0, 0)
        url_row.setSpacing(0)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("Paste a video, playlist or audio link (YouTube and 1,000+ other sites)")
        self.url_input.setFixedHeight(40)
        self._url_action = self.url_input.addAction(
            theme.icon("link", "text3"), QLineEdit.ActionPosition.LeadingPosition
        )
        # Square clear action instead of Fusion's round clear button.
        self._clear_action = self.url_input.addAction(
            theme.icon("close", "text3"), QLineEdit.ActionPosition.TrailingPosition
        )
        self._clear_action.setToolTip("Clear")
        self._clear_action.setVisible(False)
        self._clear_action.triggered.connect(self.url_input.clear)
        self.url_input.textChanged.connect(
            lambda t: self._clear_action.setVisible(bool(t))
        )
        self.url_input.returnPressed.connect(self._fetch_video_info)
        url_row.addWidget(self.url_input, 1)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.setObjectName("Fetch")
        self.fetch_btn.setFixedHeight(40)
        self.fetch_btn.setMinimumWidth(104)
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.clicked.connect(self._fetch_video_info)
        url_row.addWidget(self.fetch_btn)
        lay.addLayout(url_row)

        # --- Video card --------------------------------------------------
        self.video_card = VideoCard()
        lay.addWidget(self.video_card)

        # --- Output options + stream table -------------------------------
        fmt_card = QFrame()
        fmt_card.setObjectName("Card")
        fmt_lay = QVBoxLayout(fmt_card)
        fmt_lay.setContentsMargins(16, 16, 16, 16)
        self.format_selector = FormatSelector()
        self.format_selector.apply_preferences(self.config)
        self.format_selector.format_selected.connect(self._on_format_selected)
        self.format_selector.mode_changed.connect(self._update_download_button)
        fmt_lay.addWidget(self.format_selector)
        lay.addWidget(fmt_card, 1)

        # --- Action row ----------------------------------------------------
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(16)
        self.embed_thumb_check = QCheckBox("Embed thumbnail as cover art")
        self.embed_thumb_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.embed_thumb_check.setChecked(self.config.get("embed_thumbnail", True))
        actions.addWidget(self.embed_thumb_check)

        self.status_label = ElidedLabel("Ready", mode=Qt.TextElideMode.ElideRight)
        self.status_label.setObjectName("StatusText")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        actions.addWidget(self.status_label, 1)

        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("Primary")
        self.download_btn.setFixedHeight(40)
        self.download_btn.setMinimumWidth(168)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.bind_icon(self.download_btn, "download", "on_accent", 16)
        self.download_btn.clicked.connect(self._start_download)
        actions.addWidget(self.download_btn)
        lay.addLayout(actions)

        self._update_download_button()
        return page

    def _create_side_panel(self):
        panel = QFrame()
        panel.setObjectName("SidePanel")
        panel.setMinimumWidth(340)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header: underline tabs on the left, "clear finished" on the right.
        head = QFrame()
        head.setObjectName("SideHeader")
        head.setFixedHeight(48)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(16, 0, 12, 0)
        hl.setSpacing(0)
        self.side_tabbar = QTabBar()
        self.side_tabbar.setObjectName("SideTabs")
        self.side_tabbar.setDrawBase(False)
        self.side_tabbar.setExpanding(False)
        self.side_tabbar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.side_tabbar.addTab("DOWNLOADS")
        self.side_tabbar.addTab("HISTORY")
        hl.addWidget(self.side_tabbar, 0, Qt.AlignmentFlag.AlignBottom)
        hl.addStretch(1)
        self.clear_btn = icon_button("clear", "Clear finished downloads")
        self.clear_btn.clicked.connect(self._clear_finished)
        hl.addWidget(self.clear_btn)
        lay.addWidget(head)

        self.side_stack = QStackedWidget()

        # Downloads tab
        dl_page = QWidget()
        dl_lay = QVBoxLayout(dl_page)
        dl_lay.setContentsMargins(0, 0, 0, 0)
        dl_lay.setSpacing(0)

        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setObjectName("DownloadsScroll")
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.downloads_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.downloads_container = QWidget()
        self.downloads_container.setObjectName("DownloadsContainer")
        self.downloads_layout = QVBoxLayout(self.downloads_container)
        self.downloads_layout.setContentsMargins(0, 0, 0, 0)
        self.downloads_layout.setSpacing(0)

        self.downloads_empty = QWidget()
        el = QVBoxLayout(self.downloads_empty)
        el.setContentsMargins(24, 48, 24, 24)
        el.setSpacing(6)
        t = QLabel("No downloads yet")
        t.setObjectName("EmptyTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(t)
        s = QLabel("Fetch a video, choose a quality and press Download.\n"
                   "Progress shows up here.")
        s.setObjectName("Faint")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setWordWrap(True)
        el.addWidget(s)
        self.downloads_layout.addWidget(self.downloads_empty)
        self.downloads_layout.addStretch(1)
        self.downloads_scroll.setWidget(self.downloads_container)
        dl_lay.addWidget(self.downloads_scroll, 1)

        # History tab
        self.history_browser = QTextBrowser()
        self.history_browser.setOpenExternalLinks(True)
        self.history_browser.setFrameShape(QFrame.Shape.NoFrame)

        self.side_stack.addWidget(dl_page)
        self.side_stack.addWidget(self.history_browser)
        self.side_tabbar.currentChanged.connect(self._on_side_tab_changed)

        lay.addWidget(self.side_stack, 1)
        return panel

    def _create_footer(self):
        bar = QFrame()
        bar.setObjectName("Footer")
        bar.setFixedHeight(32)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)

        lay.addWidget(section_label("Save to"))
        self.output_label = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle)
        self.output_label.setObjectName("FooterValue")
        self.output_label.setMaximumWidth(520)
        lay.addWidget(self.output_label)
        lay.addSpacing(4)
        change = QPushButton("Change")
        change.setObjectName("LinkButton")
        change.setCursor(Qt.CursorShape.PointingHandCursor)
        change.clicked.connect(self._browse_folder)
        lay.addWidget(change)
        open_btn = icon_button("folder", "Open output folder", size=24, icon_px=14)
        open_btn.clicked.connect(self._open_output_folder)
        lay.addWidget(open_btn)

        lay.addSpacing(12)
        sites_btn = QPushButton("Supported sites")
        sites_btn.setObjectName("LinkButton")
        sites_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sites_btn.setToolTip("Every site yt-dlp can download from")
        sites_btn.clicked.connect(self._show_supported_sites)
        lay.addWidget(sites_btn)

        lay.addStretch(1)

        lay.addWidget(section_label("Cookies"))
        self.cookies_combo = QComboBox()
        self.cookies_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.polish_combo(self.cookies_combo)
        self.cookies_combo.setObjectName("FooterCombo")
        self.cookies_combo.setFixedSize(104, 24)
        for label, name in _COOKIE_BROWSERS:
            self.cookies_combo.addItem(label, name)
        self.cookies_combo.setToolTip(
            "Use your browser's sign-in for sites that need an account\n"
            "(private, age-restricted or members-only content).\n"
            "Firefox works best on Windows: Chromium browsers encrypt their\n"
            "cookies and must be closed while fetching."
        )
        idx = self.cookies_combo.findData(self.config.get("cookies_browser", ""))
        self.cookies_combo.setCurrentIndex(max(0, idx))
        self.cookies_combo.currentIndexChanged.connect(self._on_cookies_changed)
        lay.addWidget(self.cookies_combo)
        lay.addSpacing(16)

        lay.addWidget(section_label("Parallel"))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setFixedSize(56, 24)
        self.concurrent_spin.setToolTip("Maximum simultaneous downloads")
        self.concurrent_spin.setValue(self.config.get("max_concurrent_downloads", 3))
        self.concurrent_spin.valueChanged.connect(
            lambda v: self.dl_manager.set_max_concurrent(v)
        )
        lay.addWidget(self.concurrent_spin)
        lay.addSpacing(16)

        self.ffmpeg_dot = QFrame()
        self.ffmpeg_dot.setObjectName("Dot")
        self.ffmpeg_dot.setFixedSize(6, 6)
        lay.addWidget(self.ffmpeg_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.ffmpeg_status_label = QLabel("")
        self.ffmpeg_status_label.setObjectName("FooterText")
        lay.addWidget(self.ffmpeg_status_label)
        return bar

    # =============================================================== theme

    def _on_theme_toggled(self, idx, checked):
        if not checked:
            return
        name = "dark" if idx == 0 else "light"
        if name == self.theme:
            return
        self.theme = name
        self.config["theme"] = name
        config_manager.save(self.config)
        self._apply_theme()

    def _apply_theme(self):
        app = QApplication.instance()
        theme.apply(app, self.theme)
        self._url_action.setIcon(theme.icon("link", "text3"))
        self._clear_action.setIcon(theme.icon("close", "text3"))
        self.video_card.retheme()
        self._refresh_history()
        theme.apply_window_chrome(self)

    def showEvent(self, event):
        super().showEvent(event)
        theme.apply_window_chrome(self)

    # ============================================================== status

    def _set_status(self, text, state=""):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        _repolish(self.status_label)

    def _update_ffmpeg_status(self):
        if self.ffmpeg_path:
            self.ffmpeg_status_label.setText("FFmpeg ready")
            self.ffmpeg_status_label.setToolTip(self.ffmpeg_path)
            self.ffmpeg_dot.setProperty("state", "ok")
            self.ffmpeg_dot.setToolTip(self.ffmpeg_path)
        else:
            self.ffmpeg_status_label.setText("FFmpeg not found")
            tip = ("Merging video+audio and audio conversion need FFmpeg.\n"
                   "Place ffmpeg.exe next to the application or add it to PATH.")
            self.ffmpeg_status_label.setToolTip(tip)
            self.ffmpeg_dot.setProperty("state", "warn")
            self.ffmpeg_dot.setToolTip(tip)
        _repolish(self.ffmpeg_dot)

    def _update_output_label(self):
        self.output_label.setText(os.path.normpath(self.out_dir))
        self.output_label.setToolTip(os.path.normpath(self.out_dir))

    def _update_download_button(self, *_):
        mode = self.format_selector.get_mode()
        self.download_btn.setText(
            ("Download video", "Download audio", "Save thumbnail")[mode]
        )
        self.embed_thumb_check.setEnabled(mode != 2)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.out_dir or app_paths.downloads_dir()
        )
        if folder:
            self.out_dir = os.path.normpath(folder)
            self.config["last_folder"] = self.out_dir
            config_manager.save(self.config)
            self._update_output_label()

    def _show_supported_sites(self):
        SupportedSitesDialog(self).exec()

    def _on_cookies_changed(self, _index):
        self.config["cookies_browser"] = self.cookies_combo.currentData() or ""
        config_manager.save(self.config)

    def _cookie_opts(self):
        browser = self.cookies_combo.currentData() or ""
        return {"cookiesfrombrowser": (browser,)} if browser else {}

    def _open_output_folder(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if os.path.isdir(self.out_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_dir))

    # =============================================================== fetch

    def _fetch_video_info(self):
        # Enter in the URL box bypasses the disabled Fetch button; never
        # replace (and garbage-collect) a QThread that is still running.
        if self.fetch_worker is not None and self.fetch_worker.isRunning():
            return

        url = self.url_input.text().strip()
        if not url:
            self.url_input.setFocus()
            self._set_status("Paste a URL first", "error")
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching")
        self._set_status("Fetching link information...")
        self.video_card.set_loading()
        self.format_selector.clear()

        self.current_video_info = None
        self.fetch_worker = FetchWorker(url, self, extra_opts=self._cookie_opts())
        self.fetch_worker.info_ready.connect(self._on_info_ready)
        self.fetch_worker.error_occurred.connect(self._on_fetch_error)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.start()

    def _on_info_ready(self, data):
        self.current_video_info = data
        self.video_card.set_info(data)
        self.format_selector.set_formats(
            data.get("formats", []), data.get("qualities"),
            generic_fallback=bool(data.get("is_playlist")),
            has_video=data.get("has_video", True),
        )
        title = data.get("title") or "Unknown"
        if data.get("is_playlist"):
            kind = "Playlist"
        else:
            kind = "Video" if data.get("has_video", True) else "Audio"
        if data.get("preview_only"):
            self._set_status(
                f"{kind} loaded: {title}. Only a short preview is available "
                "(the full track may need a sign-in, see Cookies)", "warn"
            )
            return
        self._set_status(f"{kind} loaded: {title}", "ok")

    def _on_fetch_error(self, message):
        self.video_card.clear()
        self._set_status(f"Error: {message}", "error")
        QMessageBox.warning(self, "Fetch Error", message)

    def _on_fetch_finished(self):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch")

    def _on_format_selected(self, fmt):
        self._set_status(
            f"Stream {fmt['format_id']}: {fmt['resolution']} {fmt['ext']} ({fmt['fmt_type']})"
        )

    # ============================================================ download

    def _start_download(self):
        if not self.current_video_info:
            self._set_status("Fetch a video first", "error")
            self.url_input.setFocus()
            return

        # Re-detect in case ffmpeg was installed while the app was open.
        self.ffmpeg_path = app_paths.find_ffmpeg()
        self._update_ffmpeg_status()

        mode = self.format_selector.get_mode()
        url = self.current_video_info["url"]

        out_dir = self.out_dir or app_paths.downloads_dir()
        out_dir = os.path.expandvars(os.path.expanduser(out_dir))
        if not os.path.isabs(out_dir):
            QMessageBox.warning(
                self, "Invalid Folder",
                f"Please choose a full output folder path.\n\n{out_dir}",
            )
            return
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(
                self, "Invalid Folder", f"Cannot use output folder:\n{out_dir}\n\n{e}"
            )
            return
        self.out_dir = out_dir
        self._update_output_label()

        if mode == 0:
            self._start_video_download(url, out_dir)
        elif mode == 1:
            self._start_audio_download(url, out_dir)
        elif mode == 2:
            self._start_thumbnail_download(url, out_dir)

    def _base_opts(self, out_dir, template):
        # Use "paths" instead of joining into outtmpl so a folder name that
        # contains "%" is not treated as a template field.
        opts = {
            "outtmpl": template,
            "paths": {"home": out_dir},
            "noplaylist": False,
            "windowsfilenames": True,
            # Some sites use the whole post text as the title.
            "trim_file_name": 180,
        }
        opts.update(self._cookie_opts())
        if self.ffmpeg_path:
            opts["ffmpeg_location"] = self.ffmpeg_path
        return opts

    def _ffmpeg_missing(self, what, fallback):
        """Explain that ffmpeg is missing. Returns True to use the fallback."""
        reply = QMessageBox.warning(
            self,
            "FFmpeg Not Found",
            f"FFmpeg is required to {what}, but it was not found.\n\n"
            "Place ffmpeg.exe next to the application (or in its ffmpeg folder) "
            "or install FFmpeg on PATH, then try again.\n\n"
            f"Download {fallback} instead?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _queue_download(self, url, ydl_opts):
        self._save_config()
        self._pending_out_dir = ydl_opts.get("paths", {}).get("home", self.out_dir)
        self.dl_manager.add_download(
            url, ydl_opts, self.current_video_info.get("title") or "Unknown"
        )
        self.side_tabbar.setCurrentIndex(0)

    def _start_video_download(self, url, out_dir):
        selected_fmt = self.format_selector.get_selected_format()
        video_opts = self.format_selector.get_video_options()
        h264 = video_opts.get("force_h264", False)
        max_height = video_opts.get("max_height", 0)

        ydl_opts = self._base_opts(out_dir, "%(title)s.%(ext)s")
        ydl_opts["merge_output_format"] = "mp4"

        if selected_fmt and selected_fmt.get("fmt_type") == "video+audio":
            fmt_str = selected_fmt["format_id"]
        elif selected_fmt and selected_fmt.get("fmt_type") == "video-only":
            audio = "bestaudio[ext=m4a]/bestaudio" if h264 else "bestaudio"
            fmt_str = f"{selected_fmt['format_id']}+{audio}/best"
        elif selected_fmt and selected_fmt.get("fmt_type") == "audio-only":
            fmt_str = selected_fmt["format_id"]
        else:
            h = f"[height<={max_height}]" if max_height else ""
            fmt_str = f"bestvideo{h}+bestaudio/best{h}/best"
            if h264:
                # Resolution first, codec second: YouTube only serves H.264 up
                # to 1080p, so filtering on avc1 would silently cap 4K/1440p
                # downloads. Sorting picks the highest allowed resolution and
                # only prefers H.264/AAC among streams of that resolution.
                ydl_opts["format_sort"] = ["res", "fps", "vcodec:h264", "acodec:aac"]

        embed = self.embed_thumb_check.isChecked()
        if selected_fmt and selected_fmt.get("fmt_type") == "audio-only":
            # A raw audio stream: no merge, keep its own container.
            ydl_opts.pop("merge_output_format", None)
            embed = embed and selected_fmt.get("ext") in _EMBED_THUMB_AUDIO
        if not self.ffmpeg_path:
            embed = False
            if "+" in fmt_str:
                if not self._ffmpeg_missing(
                    "merge separate video and audio streams",
                    "the best single-file format (usually lower quality)",
                ):
                    return
                fmt_str = f"best[height<={max_height}]/best" if max_height else "best"
        ydl_opts["format"] = fmt_str

        if embed:
            ydl_opts["writethumbnail"] = True
            ydl_opts["postprocessors"] = [
                {"key": "EmbedThumbnail", "already_have_thumbnail": False}
            ]

        self._queue_download(url, ydl_opts)

    def _start_audio_download(self, url, out_dir):
        audio_opts = self.format_selector.get_audio_options()
        audio_fmt = audio_opts.get("format", "mp3")
        bitrate = audio_opts.get("bitrate", "192")

        ydl_opts = self._base_opts(out_dir, "%(title)s.%(ext)s")

        if not self.ffmpeg_path:
            if not self._ffmpeg_missing(
                f"convert audio to {audio_fmt.upper()}",
                "the original audio stream (M4A/WebM, no conversion)",
            ):
                return
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            self._queue_download(url, ydl_opts)
            return

        ydl_opts["format"] = "bestaudio/best"
        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_fmt,
                "preferredquality": bitrate,
            }
        ]
        if self.embed_thumb_check.isChecked() and audio_fmt in _EMBED_THUMB_AUDIO:
            ydl_opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
        ydl_opts["postprocessors"] = postprocessors

        self._queue_download(url, ydl_opts)

    def _start_thumbnail_download(self, url, out_dir):
        ydl_opts = self._base_opts(out_dir, "%(title)s_thumb.%(ext)s")
        ydl_opts["skip_download"] = True
        ydl_opts["writethumbnail"] = True

        choice = self.format_selector.get_thumbnail_options().get("format", "")
        target = {"PNG": "png", "JPG": "jpg"}.get(choice)
        if target:
            if self.ffmpeg_path:
                ydl_opts["postprocessors"] = [
                    {"key": "FFmpegThumbnailsConvertor", "format": target, "when": "before_dl"}
                ]
            elif not self._ffmpeg_missing(
                f"convert the thumbnail to {choice}", "the original thumbnail (WebP/JPG)"
            ):
                return

        self._queue_download(url, ydl_opts)

    def _save_config(self):
        self.config["last_folder"] = self.out_dir
        self.config["theme"] = self.theme
        self.format_selector.store_preferences(self.config)
        self.config["max_concurrent_downloads"] = self.concurrent_spin.value()
        self.config["embed_thumbnail"] = self.embed_thumb_check.isChecked()
        config_manager.save(self.config)

    # ======================================================= download list

    def _update_downloads_empty(self):
        self.downloads_empty.setVisible(not self.download_widgets)
        has_finished = any(w.is_finished() for w in self.download_widgets.values())
        self.clear_btn.setEnabled(has_finished)
        active = sum(1 for w in self.download_widgets.values() if not w.is_finished())
        self.side_tabbar.setTabText(0, f"DOWNLOADS  {active}" if active else "DOWNLOADS")

    def _on_download_added(self, dl_id, title):
        widget = DownloadItemWidget(dl_id, title, self._pending_out_dir or self.out_dir)
        widget.cancel_clicked.connect(self.dl_manager.cancel_download)
        widget.close_clicked.connect(self._remove_download_widget)
        # Newest first, below nothing: index 0 is the (hidden) empty state.
        self.downloads_layout.insertWidget(1, widget)
        self.download_widgets[dl_id] = widget
        self._update_downloads_empty()

    def _on_download_progress(self, dl_id, percent, speed, eta, size):
        w = self.download_widgets.get(dl_id)
        if w:
            w.update_progress(percent, speed, eta, size)

    def _on_download_status(self, dl_id, text):
        w = self.download_widgets.get(dl_id)
        if w:
            w.set_status(text)

    def _on_download_complete(self, dl_id, title, path):
        w = self.download_widgets.get(dl_id)
        if w:
            w.set_complete(title, path)
        self._set_status(f"Completed: {title}", "ok")
        self._update_downloads_empty()
        self._refresh_history()

    def _on_download_error(self, dl_id, message):
        w = self.download_widgets.get(dl_id)
        if w:
            w.set_error(message)
        self._set_status(f"Download failed: {message}", "error")
        self._update_downloads_empty()

    def _on_download_cancelled(self, dl_id):
        w = self.download_widgets.get(dl_id)
        if w:
            w.set_cancelled()
        self._update_downloads_empty()

    def _remove_download_widget(self, dl_id):
        w = self.download_widgets.pop(dl_id, None)
        if w:
            self.downloads_layout.removeWidget(w)
            w.deleteLater()
        self._update_downloads_empty()

    def _clear_finished(self):
        for dl_id, w in list(self.download_widgets.items()):
            if w.is_finished():
                self._remove_download_widget(dl_id)

    # ============================================================= history

    def _on_side_tab_changed(self, idx):
        self.side_stack.setCurrentIndex(idx)
        self.clear_btn.setVisible(idx == 0)
        if idx == 1:
            self._refresh_history()

    def _refresh_history(self):
        """Render the history log (newest first) with theme colours."""
        content = self.dl_manager.get_history()
        entries = []
        for block in content.split("-" * 80):
            lines = [l.rstrip() for l in block.strip().splitlines() if l.strip()]
            if not lines:
                continue
            head = lines[0]
            ts, title = "", head
            if head.startswith("[") and "]" in head:
                ts, title = head[1:head.index("]")], head[head.index("]") + 1:].strip()
            url = fmt = ""
            for l in lines[1:]:
                l = l.strip()
                if l.startswith("URL:"):
                    url = l[4:].strip()
                elif l.startswith("Format:"):
                    fmt = l[7:].strip()
            entries.append((ts, title, url, fmt))
        entries.reverse()

        c = theme.color
        if not entries:
            body = (f'<div style="color:{c("text2")}; font-weight:600; '
                    f'text-align:center; margin-top:48px;">No history yet</div>'
                    f'<div style="color:{c("text3")}; font-size:12px; text-align:center; '
                    f'margin-top:6px;">Completed downloads are listed here.</div>')
        else:
            mono = theme.mono_family()
            rows = []
            for ts, title, url, fmt in entries[:300]:
                rows.append(
                    f'<table width="100%" cellspacing="0" cellpadding="0" '
                    f'style="margin:0 0 0 0;"><tr><td style="padding:12px 16px 12px 16px; '
                    f'border-bottom:1px solid {c("border")};">'
                    f'<div style="color:{c("text")}; font-weight:600;">{html.escape(title)}</div>'
                    f'<div style="color:{c("text3")}; font-family:\'{mono}\'; font-size:11px; '
                    f'margin-top:4px;">{html.escape(ts)}</div>'
                    f'<div style="font-size:12px; margin-top:4px;">'
                    f'<a style="color:{c("text2")}; text-decoration:none;" '
                    f'href="{html.escape(url, quote=True)}">{html.escape(url)}</a></div>'
                    f'</td></tr></table>'
                )
            body = "".join(rows)
        self.history_browser.setHtml(f'<body style="margin:0;">{body}</body>')

    # =============================================================== close

    def closeEvent(self, event):
        if self.dl_manager.has_pending():
            reply = QMessageBox.question(
                self,
                "Downloads in Progress",
                "Downloads are still running. Cancel them and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.dl_manager.cancel_all()
        if self.fetch_worker is not None and self.fetch_worker.isRunning():
            self.fetch_worker.wait(3000)
        self._save_config()
        event.accept()


def main():
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(_app_icon())
    window = MainWindow()
    window.setWindowIcon(app.windowIcon())
    window.show()
    rc = app.exec()
    # Destroy Qt objects in a defined order (window, then the application)
    # instead of leaving it to interpreter shutdown, which could crash with
    # an access violation on exit.
    theme.shutdown(app)
    del window
    gc.collect()
    del app
    gc.collect()
    sys.exit(rc)


if __name__ == "__main__":
    main()
