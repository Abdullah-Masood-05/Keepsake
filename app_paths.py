"""Path helpers that work both from source and from a Nuitka onefile build.

In a Nuitka onefile build ``__file__`` points into a temporary extraction
directory that is wiped on exit, so:
  * bundled data files (icons) are looked up relative to ``__file__``;
  * files shipped *next to* the exe (ffmpeg.exe) are looked up relative to
    the real exe location (``sys.argv[0]`` / ``__compiled__.original_argv0``);
  * user data (config, history) lives in a per-user writable directory.
"""

import os
import sys
import shutil
from pathlib import Path

APP_DIR_NAME = "Fetchly"
# Settings folder used before the app was renamed; migrated once.
_OLD_APP_DIR_NAME = "YouTubeVideoDownloader"

# Directory containing this source file (or the onefile extraction dir).
BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_compiled():
    try:
        __compiled__  # noqa: F821 - injected by Nuitka
        return True
    except NameError:
        return bool(getattr(sys, "frozen", False))


def exe_dir():
    """Directory of the running executable (where the installer puts ffmpeg)."""
    if is_compiled():
        try:
            argv0 = __compiled__.original_argv0  # noqa: F821
        except (NameError, AttributeError):
            argv0 = None
        candidate = argv0 or sys.argv[0] or sys.executable
        # realpath: /usr/bin/<app> is a symlink into /opt/<app> on Linux.
        return os.path.dirname(os.path.realpath(candidate))
    return BUNDLE_DIR


def resource_path(*parts):
    """Path of a bundled data file (e.g. resources/icons/app.png)."""
    return os.path.join(BUNDLE_DIR, *parts)


def user_data_dir():
    """Per-user writable directory, e.g. %APPDATA%\\Fetchly.

    YTDL_CONFIG_DIR overrides it, so test runs don't touch the real settings.
    """
    override = os.environ.get("YTDL_CONFIG_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(Path.home(), "AppData", "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    path = os.path.join(base, APP_DIR_NAME)
    old = os.path.join(base, _OLD_APP_DIR_NAME)
    if not os.path.exists(path) and os.path.isdir(old):
        try:
            shutil.copytree(old, path)
        except OSError:
            pass
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _windows_known_downloads():
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
    folder_id = GUID(
        0x374DE290, 0x123F, 0x4565,
        (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B),
    )
    path_ptr = ctypes.c_wchar_p()
    shell32 = ctypes.windll.shell32
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    hr = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(path_ptr))
    try:
        if hr == 0 and path_ptr.value:
            return path_ptr.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path_ptr)
    return None


def downloads_dir():
    """The user's real Downloads folder."""
    if sys.platform == "win32":
        try:
            path = _windows_known_downloads()
            if path and os.path.isdir(path):
                return os.path.normpath(path)
        except Exception:
            pass
    try:
        from PyQt6.QtCore import QStandardPaths
        path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if path and os.path.isdir(path):
            return os.path.normpath(path)
    except Exception:
        pass
    return os.path.normpath(os.path.join(Path.home(), "Downloads"))


def find_ffmpeg():
    """Return the full path to ffmpeg(.exe), or None.

    Search order: next to the running exe, the project's ffmpeg/ folder (when
    running from source), then PATH.
    """
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    candidates = [
        os.path.join(exe_dir(), name),
        # Nuitka standalone (Linux packages): the dist folder itself.
        os.path.join(BUNDLE_DIR, name),
        os.path.join(exe_dir(), "ffmpeg", name),
        os.path.join(BUNDLE_DIR, "ffmpeg", name),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return shutil.which("ffmpeg")
