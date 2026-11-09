import gc
import os
import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QFileDialog, QMessageBox,
    QStackedWidget,
)
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut

import app_paths
import config_manager
import theme
try:  # extra icons (home, settings, ...)
    import widgets.icons  # noqa: F401
except ImportError:
    pass
from download_manager import DownloadManager
from workers.fetch_worker import FetchWorker
from widgets.download_item import DownloadItemWidget
from widgets.sidebar import Sidebar
from widgets.toast import ToastManager
from widgets.supported_sites_dialog import SupportedSitesDialog
from pages.home import HomePage
from pages.downloads import DownloadsPage
from pages.history import HistoryPage, parse_history
from pages.settings import SettingsPage
from pages.common import PageTransition, SnapshotOverlay
from widgets import motion

APP_TITLE = "Keepsake"
VERSION = "2.1.1"

PAGE_HOME, PAGE_DOWNLOADS, PAGE_HISTORY, PAGE_SETTINGS = range(4)
APP_USER_MODEL_ID = "AbdullahMasood.Keepsake"

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
        self.setMinimumSize(960, 660)
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
        self._pending_job = None
        self._jobs = {}
        self._setup_ui()
        self._apply_theme()
        self._update_ffmpeg_status()
        self._update_output_label()
        self._update_downloads_empty()
        self._refresh_history()

    # ================================================================== UI

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("Workspace")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(APP_TITLE, VERSION)
        self.sidebar.page_requested.connect(self._go_page)
        self.sidebar.theme_toggle_requested.connect(self._toggle_theme)
        root.addWidget(self.sidebar)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("Workspace")
        self._page_transition = PageTransition(self.page_stack)
        self._theme_overlay = None
        root.addWidget(self.page_stack, 1)

        # --- Home -------------------------------------------------------
        self.home_page = HomePage(self.config)
        self.url_input = self.home_page.url_input
        self.fetch_btn = self.home_page.fetch_btn
        self.video_card = self.home_page.video_card
        self.format_selector = self.home_page.format_selector
        self.embed_thumb_check = self.home_page.embed_thumb_check
        self.status_label = self.home_page.status_label
        self.download_btn = self.home_page.download_btn
        self.home_page.fetch_requested.connect(self._fetch_video_info)
        self.home_page.download_requested.connect(self._start_download)
        self.format_selector.format_selected.connect(self._on_format_selected)
        self.format_selector.mode_changed.connect(self._update_download_button)
        self._update_download_button()

        # --- Downloads ----------------------------------------------------
        self.downloads_page = DownloadsPage()
        self.downloads_page.go_home.connect(lambda: self._go_page(PAGE_HOME))
        self.downloads_page.clear_finished.connect(self._clear_finished)
        self.downloads_page.cancel_all.connect(self._cancel_active)

        # --- History ------------------------------------------------------
        self.history_page = HistoryPage()

        # --- Settings -----------------------------------------------------
        self.settings_page = SettingsPage(self.config, _COOKIE_BROWSERS, VERSION)
        self.output_label = self.settings_page.output_label
        self.cookies_combo = self.settings_page.cookies_combo
        self.concurrent_spin = self.settings_page.concurrent_spin
        self.settings_page.change_folder.connect(self._browse_folder)
        self.settings_page.open_folder.connect(self._open_output_folder)
        self.settings_page.show_sites.connect(self._show_supported_sites)
        self.cookies_combo.currentIndexChanged.connect(self._on_cookies_changed)
        self.concurrent_spin.valueChanged.connect(
            lambda v: self.dl_manager.set_max_concurrent(v)
        )
        self.settings_page.theme_seg.set_index(0 if self.theme == "dark" else 1)
        self.settings_page.theme_seg.group.idToggled.connect(self._on_theme_toggled)

        for page in (self.home_page, self.downloads_page,
                     self.history_page, self.settings_page):
            self.page_stack.addWidget(page)

        self.toasts = ToastManager(central)

        for i in range(4):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            sc.activated.connect(lambda i=i: self._go_page(i))

    def _go_page(self, index):
        self._page_transition.go(index)
        self.sidebar.set_page(index)
        if index == PAGE_HISTORY:
            self._refresh_history()

    def _toast(self, text, kind="info", action_text=None, action_cb=None):
        self.toasts.show(text, kind, action_text, action_cb)


    # =============================================================== theme

    def _on_theme_toggled(self, idx, checked):
        if checked:
            self._set_theme("dark" if idx == 0 else "light")

    def _toggle_theme(self):
        self._set_theme("light" if self.theme == "dark" else "dark")

    def _set_theme(self, name):
        if name == self.theme:
            return
        self.theme = name
        self.config["theme"] = name
        config_manager.save(self.config)
        # Crossfade: snapshot the old look, restyle underneath, fade it out.
        central = self.centralWidget()
        self._page_transition.finish()
        if self._theme_overlay is not None:
            self._theme_overlay.deleteLater()
            self._theme_overlay = None
        overlay = None
        if self.isVisible() and not motion.REDUCED:
            overlay = SnapshotOverlay(central, central.grab())
            self._theme_overlay = overlay
        self._apply_theme()
        if overlay is not None:
            def done():
                if self._theme_overlay is overlay:
                    self._theme_overlay = None
                overlay.hide()
                overlay.deleteLater()
            motion.tween(central, 1.0, 0.0, overlay.set_state, ms=motion.BASE,
                         curve=motion.EASE_IN_OUT, finished=done, key="_anim_theme")

    def _apply_theme(self):
        app = QApplication.instance()
        theme.apply(app, self.theme)
        seg = self.settings_page.theme_seg
        seg.group.blockSignals(True)
        seg.set_index(0 if self.theme == "dark" else 1)
        seg.group.blockSignals(False)
        self.sidebar.retheme()
        for page in (self.home_page, self.downloads_page,
                     self.history_page, self.settings_page):
            page.retheme()
        self.toasts.retheme()
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
            tip = self.ffmpeg_path
        else:
            tip = ("Merging video+audio and audio conversion need FFmpeg.\n"
                   "Place ffmpeg.exe next to the application or add it to PATH.")
        self.sidebar.set_ffmpeg(self.ffmpeg_path, tip)
        self.settings_page.set_ffmpeg(self.ffmpeg_path, tip)

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
        self._open_folder(self.out_dir)

    def _open_folder(self, folder):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

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
        info = self.current_video_info or {}
        meta = {
            "site": info.get("site", ""),
            "mode": ("video", "audio", "thumbnail")[self.format_selector.get_mode()],
            "thumbnail": info.get("thumbnail_image"),
        }
        self._queue_with_meta(url, ydl_opts, info.get("title") or "Unknown", meta)

    def _queue_with_meta(self, url, ydl_opts, title, meta):
        self._pending_job = (url, ydl_opts, title, meta)
        self.dl_manager.add_download(url, ydl_opts, title)
        self._pending_job = None

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
        total = len(self.download_widgets)
        finished = sum(1 for w in self.download_widgets.values() if w.is_finished())
        active = total - finished
        self.downloads_page.update_state(total, active, finished)
        self.sidebar.set_badge(PAGE_DOWNLOADS, active)

    def _on_download_added(self, dl_id, title):
        widget = DownloadItemWidget(dl_id, title, self._pending_out_dir or self.out_dir)
        widget.cancel_clicked.connect(self.dl_manager.cancel_download)
        widget.close_clicked.connect(self._remove_download_widget)
        job = self._pending_job
        if job:
            self._jobs[dl_id] = job
            meta = job[3]
            widget.set_meta(meta.get("site", ""), meta.get("mode", ""), meta.get("thumbnail"))
            widget.enable_retry(True)
            widget.retry_clicked.connect(self._retry_download)
        self.downloads_page.add_widget(widget)
        self.download_widgets[dl_id] = widget
        self._update_downloads_empty()
        self._toast("Added to downloads", "info")

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
        folder = (w.out_dir if w else "") or self.out_dir
        self._toast(f"Download complete: {title}", "success",
                    "Open folder", lambda: self._open_folder(folder))

    def _on_download_error(self, dl_id, message):
        w = self.download_widgets.get(dl_id)
        if w:
            w.set_error(message)
        self._set_status(f"Download failed: {message}", "error")
        self._toast(f"Download failed: {message}", "error")
        self._update_downloads_empty()

    def _on_download_cancelled(self, dl_id):
        w = self.download_widgets.get(dl_id)
        if w:
            w.set_cancelled()
        self._update_downloads_empty()

    def _remove_download_widget(self, dl_id):
        w = self.download_widgets.pop(dl_id, None)
        self._jobs.pop(dl_id, None)
        if w:
            self.downloads_page.remove_widget(w)
        self._update_downloads_empty()

    def _clear_finished(self):
        for dl_id, w in list(self.download_widgets.items()):
            if w.is_finished():
                self._remove_download_widget(dl_id)

    # ============================================================= history

    def _retry_download(self, dl_id):
        job = self._jobs.get(dl_id)
        if not job:
            return
        url, opts, title, meta = job
        self._remove_download_widget(dl_id)
        self._pending_out_dir = opts.get("paths", {}).get("home", self.out_dir)
        self._queue_with_meta(url, opts, title, meta)

    def _cancel_active(self):
        for dl_id, w in list(self.download_widgets.items()):
            if not w.is_finished():
                self.dl_manager.cancel_download(dl_id)

    def _refresh_history(self):
        """Fill the history page from the log (newest first)."""
        self.history_page.set_entries(parse_history(self.dl_manager.get_history()))

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
