import os
import re
import time
import yt_dlp
from PyQt6.QtCore import QThread, pyqtSignal

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# What yt-dlp leaves behind for an output "name.ext": separate streams
# (name.f137.mp4), merge output (name.temp.mp4), partial and state files
# (.part, .part-Frag3, .ytdl) and thumbnails written for embedding.
_LEFTOVER_SUFFIX_RE = re.compile(
    r"^(\.f[\w-]+)?(\.temp)?\.\w+(\.part(-Frag\d+)?|\.ytdl)?$"
)
_STREAM_SUFFIX_RE = re.compile(r"(\.f[\w-]+)?(\.temp)?\.\w+$")


class DownloadCancelled(yt_dlp.utils.DownloadCancelled):
    """Raised from hooks; yt-dlp re-raises this even with ignoreerrors."""


class _Logger:
    """Route yt-dlp output away from stdout/stderr (which can be None in a
    windowed exe) and remember the last error for the UI."""

    def __init__(self):
        self.last_error = ""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.last_error = _ANSI_RE.sub("", str(msg))


def _clean(text, default="N/A"):
    if not text:
        return default
    return _ANSI_RE.sub("", str(text)).strip() or default


class DownloadWorker(QThread):
    progress_updated = pyqtSignal(str, str, str, str)  # percent, speed, eta, size
    status_updated = pyqtSignal(str)
    download_complete = pyqtSignal(str, str)  # title, final file/folder path
    download_error = pyqtSignal(str)
    download_cancelled = pyqtSignal()

    def __init__(self, url, options, download_id, parent=None):
        super().__init__(parent)
        self.url = url
        self.options = options
        self.download_id = download_id
        self._cancel_flag = False
        self.last_filepath = ""
        # Files written for items that haven't finished yet (removed on cancel)
        # and final files of items that did finish (always kept).
        self._started = 0.0
        self._pending = set()
        self._finished = set()
        # Sentinel (not None): a single video reports item None, which must
        # still trigger the first "Downloading" status.
        self._last_item = object()

    def run(self):
        logger = _Logger()
        self._started = time.time()
        try:
            self.status_updated.emit("Starting")

            def progress_hook(d):
                for key in ("filename", "tmpfilename"):
                    if d.get(key):
                        self._pending.add(os.path.abspath(d[key]))
                if self._cancel_flag:
                    raise DownloadCancelled("Download cancelled by user")

                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    done = d.get("downloaded_bytes") or 0
                    if total:
                        percent = f"{min(done * 100.0 / total, 100.0):.1f}%"
                    else:
                        percent = _clean(d.get("_percent_str"), "0%")
                    speed = _clean(d.get("_speed_str"))
                    eta = _clean(d.get("_eta_str"))
                    size = _clean(
                        d.get("_total_bytes_str") or d.get("_total_bytes_estimate_str")
                    )
                    info = d.get("info_dict") or {}
                    idx, count = info.get("playlist_index"), info.get("n_entries")
                    item = (idx, count) if idx and count else None
                    if item != self._last_item:
                        self._last_item = item
                        self.status_updated.emit(
                            f"Downloading item {idx} of {count}" if item else "Downloading"
                        )
                    self.progress_updated.emit(percent, speed, eta, size)
                elif d["status"] == "finished":
                    if d.get("filename"):
                        self.last_filepath = d["filename"]
                    filename = os.path.basename(d.get("filename") or "Unknown")
                    self.status_updated.emit(f"Processing {filename}")

            def postprocessor_hook(d):
                if self._cancel_flag:
                    raise DownloadCancelled("Download cancelled by user")
                if d.get("status") == "started":
                    self.status_updated.emit(f"Post-processing ({d.get('postprocessor', '')})")
                elif d.get("status") == "finished":
                    path = (d.get("info_dict") or {}).get("filepath")
                    if path:
                        self.last_filepath = path
                    if path and d.get("postprocessor") == "MoveFiles":
                        # The last step for an item: it's complete. yt-dlp has
                        # already removed its intermediate files.
                        self._finished.add(os.path.abspath(path))
                        self._pending.clear()

            opts = self.options.copy()
            opts["progress_hooks"] = [progress_hook]
            opts["postprocessor_hooks"] = [postprocessor_hook]
            opts["logger"] = logger
            opts.setdefault("noprogress", True)
            # Keep going if a single playlist item fails, but report it.
            opts.setdefault("ignoreerrors", "only_download")

            # Leaving the context closes yt-dlp's file handles, so partial files
            # can be deleted afterwards (Windows refuses to delete open files).
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=True)

            if self._cancel_flag:
                self._remove_partial_files()
                self.download_cancelled.emit()
                return

            if info is None:
                self.download_error.emit(
                    self._friendly_error(logger.last_error or "Failed to extract info")
                )
                return

            if info.get("_type") == "playlist" or "entries" in info:
                entries = [e for e in (info.get("entries") or [])]
                ok = sum(1 for e in entries if e)
                failed = len(entries) - ok
                title = f"Playlist: {info.get('title') or 'Unknown'} ({ok} videos)"
                if failed:
                    title += f", {failed} failed"
                if ok == 0 and entries:
                    self.download_error.emit(
                        self._friendly_error(logger.last_error or "All playlist items failed")
                    )
                    return
                first = next((e for e in entries if e), None) or {}
                path = self._entry_path(first)
                if path:
                    self.last_filepath = os.path.dirname(path)
            else:
                title = info.get("title") or "Unknown"
                self.last_filepath = self._entry_path(info) or self.last_filepath

            self.download_complete.emit(title, self.last_filepath or "")

        except Exception as e:
            if self._cancel_flag or isinstance(e, DownloadCancelled):
                self._remove_partial_files()
                self.download_cancelled.emit()
            else:
                self.download_error.emit(self._friendly_error(str(e) or logger.last_error))

    def _remove_partial_files(self):
        """Delete what the cancelled item left behind.

        Only files that belong to an unfinished item's output name and were
        written after this download started are removed, so an older file
        with the same title or a finished playlist item is never touched.
        """
        bases = {}
        for path in self._pending:
            name = os.path.basename(path)
            for tail in (".part", ".ytdl"):
                if name.endswith(tail):
                    name = name[: -len(tail)]
            name = re.sub(r"\.part-Frag\d+$", "", name)
            stem = _STREAM_SUFFIX_RE.sub("", name)
            if stem:
                bases.setdefault(os.path.dirname(path), set()).add(stem)

        cutoff = self._started - 2
        for folder, stems in bases.items():
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            for name in names:
                path = os.path.abspath(os.path.join(folder, name))
                if path in self._finished:
                    continue
                if not any(name.startswith(s) and _LEFTOVER_SUFFIX_RE.match(name[len(s):])
                           for s in stems):
                    continue
                try:
                    if os.path.getmtime(path) < cutoff:
                        continue
                except OSError:
                    continue
                for attempt in range(5):
                    try:
                        os.remove(path)
                        break
                    except FileNotFoundError:
                        break
                    except OSError:
                        # Still held open for a moment (e.g. by ffmpeg).
                        time.sleep(0.3 * (attempt + 1))

    @staticmethod
    def _entry_path(info):
        downloads = info.get("requested_downloads") or []
        for d in reversed(downloads):
            path = d.get("filepath") or d.get("filename")
            if path and os.path.exists(path):
                return path
        # Thumbnail-only (skip_download): the media path above is never
        # written; the saved (possibly converted) image is in "thumbnails".
        for t in reversed(info.get("thumbnails") or []):
            path = t.get("filepath")
            if path and os.path.exists(path):
                return path
        path = info.get("filepath") or ""
        return path if path and os.path.exists(path) else ""

    @staticmethod
    def _friendly_error(error_msg):
        error_msg = _ANSI_RE.sub("", error_msg or "Unknown error")
        if "ERROR:" in error_msg:
            error_msg = error_msg.split("ERROR:")[-1].strip()
        low = error_msg.lower()
        if "ffmpeg" in low and ("not found" in low or "not installed" in low):
            error_msg = (
                "FFmpeg is required for this download (merging/converting) "
                "but was not found. Place ffmpeg.exe next to the application "
                "or install it on PATH. Details: " + error_msg
            )
        return error_msg

    def cancel(self):
        self._cancel_flag = True
