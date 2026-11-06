"""Turn raw yt-dlp / network error strings into short, actionable messages."""
import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_REPORT_RE = re.compile(r"[;.]?\s*(?:please\s+)?report this issue on.*$", re.IGNORECASE | re.DOTALL)
_ERROR_PREFIX_RE = re.compile(r"^(?:ERROR:\s*)+", re.IGNORECASE)
# "[youtube] dQw4w9WgXcQ: " / "[Vimeo] 12345: " / "[generic] Extracting URL: ..."
_EXTRACTOR_PREFIX_RE = re.compile(r"^(?:\[[^\]]+\]\s*[^\s:]*:\s*)+")

COOKIE_HINT = (
    'Try choosing your browser under "Cookies" at the bottom of the window '
    "(Firefox works best on Windows)."
)


def clean_error(msg):
    """Strip ANSI codes and the 'ERROR:' / '[extractor] id:' prefixes."""
    msg = _ANSI_RE.sub("", msg or "").strip()
    if "ERROR:" in msg:
        msg = msg.split("ERROR:")[-1].strip()
    msg = _ERROR_PREFIX_RE.sub("", msg)
    msg = _EXTRACTOR_PREFIX_RE.sub("", msg).strip()
    msg = _REPORT_RE.sub("", msg).strip(" ;,")
    return msg or "Unknown error"


def _short(detail, limit=300):
    detail = " ".join(detail.split())
    return detail if len(detail) <= limit else detail[: limit - 3] + "..."


def friendly_error(msg):
    """Return a user-facing message; the technical detail is kept after it."""
    detail = clean_error(msg)
    low = detail.lower()

    def has(*needles):
        return any(n in low for n in needles)

    text = None

    if has("unsupported url"):
        text = ("This site or link isn't supported by yt-dlp. Check that the "
                "URL points to a video or audio page, not a homepage or search page.")
    elif has("drm protected", "drm-protected", "drm:"):
        text = "This video is DRM protected and can't be downloaded."
    elif has("age-restricted", "age restricted", "confirm your age", "age verification"):
        text = ("This video is age restricted and needs a logged-in account. "
                + COOKIE_HINT)
    elif has("not a bot", "not a robot"):
        text = ("The site wants you to prove you're not a bot. " + COOKIE_HINT)
    elif has("password"):
        text = ("This video is password protected, which isn't supported yet.")
    elif has("cloudflare", "anti-bot", "captcha"):
        text = ("The site blocked the request with an anti-bot check. " + COOKIE_HINT)
    elif has("ip address is blocked", "ip is blocked", "your ip"):
        text = ("The site is blocking your IP address. A different network or VPN may help.")
    elif has("cannot parse data", "unable to extract", "unable to parse"):
        text = ("Couldn't read this page. It may need a login, or the site changed "
                "and yt-dlp needs updating. " + COOKIE_HINT)
    elif has("not available in your country", "geo restrict", "geo-restrict",
             "geo-block", "blocked it in your country", "available in your country",
             "not made this video available in your country"):
        text = ("This video isn't available in your country. A VPN may help.")
    elif has("private video", "this video is private", "is private"):
        text = ("This video is private. If your account can view it, "
                + COOKIE_HINT[0].lower() + COOKIE_HINT[1:])
    elif has("video unavailable", "this video is unavailable", "video has been removed",
             "has been removed", "been deleted", "no longer available",
             "account associated with this video has been terminated"):
        text = "This video is unavailable (removed, deleted or private)."
    elif has("login required", "log in", "login", "sign in", "--cookies",
             "cookies-from-browser", "registered users", "only available for",
             "members-only", "members only", "premium", "rate-limit", "rate limit",
             "authentication", "need to be logged", "requires authentication"):
        text = ("This content needs you to be logged in, or the site is "
                "rate-limiting anonymous access. " + COOKIE_HINT)
    elif has("requested format is not available", "requested format not available"):
        text = ("The selected quality isn't available for this video. "
                "Pick another quality or use Best.")
    elif has("http error 429", "too many requests"):
        text = ("The site is rate-limiting you (HTTP 429). Wait a few minutes and "
                "try again. " + COOKIE_HINT)
    elif has("http error 403", "forbidden"):
        text = ("The site refused access (HTTP 403). The video may be restricted "
                "or need a login. " + COOKIE_HINT)
    elif has("http error 404", "404: not found", "not found (404)"):
        text = "Not found (HTTP 404). The link may be wrong or the video was removed."
    elif has("getaddrinfo", "name or service not known", "nodename nor servname",
             "temporary failure in name resolution", "failed to resolve",
             "network is unreachable", "connection refused", "connection reset",
             "connection aborted", "connectionreset", "10054", "10060", "10061", "remote end closed", "no route to host"):
        text = "Couldn't reach the site. Check your internet connection and try again."
    elif has("timed out", "timeout"):
        text = "The connection timed out. Check your internet connection and try again."
    elif has("ssl:", "sslerror", "ssl error", "certificate verify"):
        text = ("A secure connection (SSL) to the site failed. Check your "
                "connection, system clock, or any proxy/antivirus interfering.")
    elif has("ffmpeg") and has("not found", "not installed"):
        text = ("FFmpeg is required for this download (merging/converting) but was "
                "not found. Place ffmpeg.exe next to the application or install it on PATH.")
    elif has("no video formats found", "no formats found",
             "no video could be found", "no media found"):
        text = ("No downloadable video was found on this page. "
                "If the video requires a login, " + COOKIE_HINT[0].lower() + COOKIE_HINT[1:])

    if text is None:
        return detail
    if _short(detail).lower() in text.lower():
        return text
    return f"{text} (Details: {_short(detail)})"
