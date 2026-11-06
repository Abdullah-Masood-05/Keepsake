import html
import re
import time
from urllib.parse import urlparse

import yt_dlp
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from workers.errors import friendly_error

THUMBNAIL_BUDGET = 15.0  # seconds, total, for all thumbnail attempts
_AUDIO_EXTS = {
    "mp3", "m4a", "aac", "ogg", "oga", "opus", "flac", "wav", "wma", "weba",
    "aiff", "alac", "mka", "ape",
}
_SITE_NAMES = {
    "youtube": "YouTube", "soundcloud": "SoundCloud", "bandcamp": "Bandcamp",
    "vimeo": "Vimeo", "dailymotion": "Dailymotion", "twitch": "Twitch",
    "twitter": "X (Twitter)", "tiktok": "TikTok", "facebook": "Facebook",
    "instagram": "Instagram", "reddit": "Reddit", "bilibili": "Bilibili",
    "niconico": "Niconico", "mixcloud": "Mixcloud", "archive.org": "Internet Archive",
    "ted": "TED", "vk": "VK", "ok": "OK.ru", "imgur": "Imgur", "rumble": "Rumble",
    "odysee": "Odysee", "bbc": "BBC", "cnn": "CNN", "nbc": "NBC", "pbs": "PBS",
    "spotify": "Spotify", "kick": "Kick", "streamable": "Streamable",
}


class _QuietLogger:
    """Swallow yt-dlp output (stdout/stderr may be None in a windowed exe)
    but remember the last error for the UI."""

    def __init__(self):
        self.last_error = ""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.last_error = str(msg)


class FetchWorker(QThread):
    info_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, parent=None, extra_opts=None):
        super().__init__(parent)
        self.url = url
        self.extra_opts = dict(extra_opts or {})

    def run(self):
        logger = _QuietLogger()
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "logger": logger,
                # A private or removed playlist item is skipped instead of
                # failing the whole playlist; a single video that fails
                # returns None and its error is reported below.
                "ignoreerrors": True,
            }
            ydl_opts.update(self.extra_opts)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if info is None:
                self.error_occurred.emit(
                    friendly_error(logger.last_error or "Could not read this link.")
                )
                return

            entries = info.get("entries")
            if entries is not None:
                entries = [e for e in entries if isinstance(e, dict)]
                info["entries"] = entries
                if not entries:
                    self.error_occurred.emit(friendly_error(
                        logger.last_error or "This playlist has no downloadable items."
                    ))
                    return
            is_playlist = bool(entries)

            title = info.get("title") or "Unknown"
            channel = self._pick_channel(info, entries)
            duration = info.get("duration") or 0
            if not duration and entries:
                duration = sum(
                    e.get("duration") or 0 for e in entries
                    if isinstance(e.get("duration"), (int, float))
                )
            description = self._plain_text(info.get("description") or "")
            view_count = info.get("view_count") or 0
            upload_date = info.get("upload_date") or ""

            thumbnail_url = self._pick_thumbnail_url(info)
            # QPixmap must only be created on the GUI thread; hand over a
            # QImage and let the widget convert it.
            thumbnail_image = self._fetch_thumbnail(info)

            formats = []
            seen = set()
            for f in info.get("formats") or []:
                fmt_id = f.get("format_id", "")
                ext = f.get("ext", "")
                vcodec = f.get("vcodec") or "none"
                acodec = f.get("acodec") or "none"
                height = f.get("height")
                fps = f.get("fps")
                filesize = f.get("filesize") or f.get("filesize_approx") or 0
                tbr = f.get("tbr") or 0
                abr = f.get("abr") or 0
                vbr = f.get("vbr") or 0

                if self._is_storyboard(f):
                    continue
                has_video = self._format_has_video(f)
                # acodec None means "unknown", not "absent".
                has_audio = f.get("acodec") != "none"

                if has_video and has_audio:
                    fmt_type = "video+audio"
                elif has_video:
                    # Unknown acodec on a progressive stream: assume it
                    # carries audio unless it is explicitly "none".
                    fmt_type = "video+audio" if f.get("acodec") is None else "video-only"
                elif has_audio:
                    fmt_type = "audio-only"
                else:
                    continue

                if height:
                    key = f"{height}_{fps or 0}_{ext}_{fmt_type}"
                else:
                    key = f"nh_{fmt_id}_{round(tbr)}_{ext}_{fmt_type}"
                if key in seen:
                    continue
                seen.add(key)

                resolution = f"{height}p" if height else "N/A"
                fps_str = f"{int(fps)}" if fps else "N/A"
                size_str = self._format_size(filesize)

                formats.append({
                    "format_id": fmt_id,
                    "ext": ext,
                    "resolution": resolution,
                    "height": height or 0,
                    "fps": fps_str,
                    "vcodec": vcodec if vcodec != "none" else "-",
                    "acodec": acodec if acodec != "none" else "-",
                    "filesize": filesize,
                    "filesize_str": size_str,
                    "tbr": tbr,
                    "abr": abr,
                    "vbr": vbr,
                    "fmt_type": fmt_type,
                })

            formats.sort(key=lambda x: (-x["height"], -x["tbr"]))

            qualities = self._collect_qualities(info)

            duration_str = self._format_duration(duration)
            views_str = f"{view_count:,}" if view_count else "N/A"

            sources = entries if is_playlist else [info]
            has_video = any(self._source_has_video(src) for src in sources)
            preview_only = any(self._is_preview_only(src) for src in sources)

            entry_count = (info.get("playlist_count") or len(entries)) if is_playlist else 0

            result = {
                "title": title,
                "channel": channel,
                "site": self._site_name(info),
                "extractor": info.get("extractor_key") or info.get("extractor") or "",
                "webpage_url": info.get("webpage_url") or self.url,
                "duration": duration_str,
                "duration_seconds": duration,
                "thumbnail_image": thumbnail_image,
                "thumbnail_url": thumbnail_url,
                "description": description[:300],
                "view_count": views_str,
                "upload_date": upload_date,
                "formats": formats,
                "qualities": qualities,
                "is_playlist": is_playlist,
                "entry_count": entry_count,
                "has_video": has_video,
                "preview_only": preview_only,
                "url": self.url,
            }

            self.info_ready.emit(result)

        except yt_dlp.utils.YoutubeDLError as e:
            self.error_occurred.emit(friendly_error(str(e)))
        except Exception as e:
            # Not a yt-dlp error: usually an extractor broken by a site change.
            self.error_occurred.emit(
                "yt-dlp couldn't read this page (the site may have changed; "
                "try updating yt-dlp). "
                f"(Details: {type(e).__name__}: {' '.join(str(e).split())[:200]})"
            )

    # ------------------------------------------------------------ metadata

    @staticmethod
    def _plain_text(text):
        """Some sites (SoundCloud, Bandcamp) return HTML descriptions."""
        if "<" in text or "&" in text:
            text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.I)
            text = html.unescape(re.sub(r"<[^>]+>", "", text))
        return re.sub(r"[ \t\xa0]+", " ", text).strip()

    @staticmethod
    def _pick_channel(info, entries):
        keys = ("uploader", "channel", "creator", "artist", "uploader_id",
                "playlist_uploader", "playlist_channel")
        sources = [info]
        if entries:
            sources.append(entries[0])
        for src in sources:
            for k in keys:
                v = src.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (list, tuple)) and v and isinstance(v[0], str):
                    return ", ".join(v[:3])
        return ""

    @staticmethod
    def _site_name(info):
        raw = info.get("extractor") or info.get("extractor_key") or ""
        base = raw.split(":")[0].strip()
        low = base.lower()
        domain = info.get("webpage_url_domain") or urlparse(
            info.get("webpage_url") or info.get("original_url") or "").netloc
        domain = domain.removeprefix("www.")
        if low in _SITE_NAMES:
            return _SITE_NAMES[low]
        if low in ("generic", "") and domain:
            return domain
        if not base:
            return domain
        return base.title() if base.islower() else base

    @staticmethod
    def _is_storyboard(f):
        return (
            f.get("protocol") == "mhtml"
            or (f.get("ext") or "").lower() == "mhtml"
            or "storyboard" in (f.get("format_note") or "").lower()
        )

    @staticmethod
    def _format_has_video(f):
        """True if the format carries video. vcodec None means unknown."""
        vcodec = f.get("vcodec")
        if vcodec == "none":
            return False
        if vcodec or f.get("height") or f.get("width"):
            return True
        # Codec unknown and no dimensions: decide by container.
        return (f.get("ext") or "").lower() not in _AUDIO_EXTS

    @classmethod
    def _source_has_video(cls, src):
        fmts = [f for f in (src.get("formats") or []) if not cls._is_storyboard(f)]
        if fmts:
            return any(cls._format_has_video(f) for f in fmts)
        if src.get("vcodec") == "none":
            return False
        if src.get("vcodec") or src.get("height"):
            return True
        ext = (src.get("ext") or "").lower()
        if not ext:
            path = urlparse(src.get("url") or "").path
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        return ext not in _AUDIO_EXTS

    @classmethod
    def _is_preview_only(cls, src):
        fmts = [f for f in (src.get("formats") or [])
                if not cls._is_storyboard(f) and not cls._format_has_video(f)]
        return bool(fmts) and all("preview" in str(f.get("format_id", "")).lower() for f in fmts)

    @classmethod
    def _collect_qualities(cls, info):
        """Build the list of video heights actually available.

        Returns a list of dicts sorted by height descending:
        {"height": int, "fps": int, "filesize": int}. For playlists the
        heights of all entries are merged (union); size is omitted there.
        """
        entries = info.get("entries")
        if entries:
            sources = [e for e in entries if isinstance(e, dict)]
            is_playlist = True
        else:
            sources = [info]
            is_playlist = False

        by_height = {}
        for src in sources:
            src_formats = src.get("formats") or []

            best_audio_size = 0
            for f in src_formats:
                if (f.get("acodec") not in (None, "none") and f.get("vcodec") == "none"
                        and not cls._is_storyboard(f)):
                    size = f.get("filesize") or f.get("filesize_approx") or 0
                    best_audio_size = max(best_audio_size, size)

            for f in src_formats:
                height = f.get("height")
                if cls._is_storyboard(f) or not cls._format_has_video(f) or not height:
                    continue

                fps = int(f.get("fps") or 0)
                size = f.get("filesize") or f.get("filesize_approx") or 0
                if size and f.get("acodec") == "none":
                    size += best_audio_size

                entry = by_height.setdefault(height, {"height": height, "fps": 0, "filesize": 0})
                entry["fps"] = max(entry["fps"], fps)
                if not is_playlist:
                    entry["filesize"] = max(entry["filesize"], size)

        return sorted(by_height.values(), key=lambda q: -q["height"])

    @staticmethod
    def _thumbnail_candidates(info):
        """Return [(url, headers)] best-first (jpg/png before webp/avif)."""
        base_headers = dict(info.get("http_headers") or {})
        out, seen = [], set()

        def add(url, extra=None):
            if not url or url in seen or not url.startswith(("http://", "https://")):
                return
            seen.add(url)
            headers = dict(base_headers)
            headers.update(extra or {})
            out.append((url, headers))
            if "/vi_webp/" in url:
                jpg = url.replace("/vi_webp/", "/vi/").rsplit(".", 1)[0] + ".jpg"
                if jpg not in seen:
                    seen.add(jpg)
                    out.append((jpg, headers))

        def ext_rank(url):
            path = urlparse(url).path.lower()
            if path.endswith((".jpg", ".jpeg", ".png")):
                return 0
            if path.endswith((".webp", ".avif")):
                return 2
            return 1

        def from_source(src):
            main = src.get("thumbnail")
            thumbs = [t for t in (src.get("thumbnails") or [])
                      if isinstance(t, dict) and t.get("url")]
            main_hdr = next((t.get("http_headers") for t in thumbs if t["url"] == main), None)
            if main:
                add(main, main_hdr)
            thumbs.sort(key=lambda t: (
                ext_rank(t["url"]),
                -(t.get("preference") or 0),
                -(t.get("width") or 0),
            ))
            for t in thumbs:
                add(t["url"], t.get("http_headers"))

        from_source(info)
        for entry in (info.get("entries") or [])[:3]:
            if isinstance(entry, dict):
                from_source(entry)
        return out

    @classmethod
    def _pick_thumbnail_url(cls, info):
        cands = cls._thumbnail_candidates(info)
        return cands[0][0] if cands else ""

    def _fetch_thumbnail(self, info):
        """Download a thumbnail and return it as a QImage (thread-safe).

        Tries each candidate until one downloads and decodes, within a total
        time budget. Cookies are not sent for thumbnails.
        """
        deadline = time.monotonic() + THUMBNAIL_BUDGET
        for url, headers in self._thumbnail_candidates(info)[:8]:
            remaining = deadline - time.monotonic()
            if remaining <= 0.5:
                break
            try:
                resp = requests.get(url, headers=headers, timeout=min(6, remaining))
                resp.raise_for_status()
                image = QImage()
                if image.loadFromData(resp.content) and not image.isNull():
                    return image
            except Exception:
                continue
        return QImage()

    @staticmethod
    def _format_size(size_bytes):
        if not size_bytes:
            return "N/A"
        units = ["B", "KB", "MB", "GB"]
        size = float(size_bytes)
        for unit in units:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return "0:00"
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
