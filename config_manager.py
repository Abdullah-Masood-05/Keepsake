import os
import json
import tempfile

import app_paths

CONFIG_DIR = app_paths.user_data_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "download_history.log")

# Files written by older versions next to the script / in the working dir.
_LEGACY_CONFIG_NAME = "downloader_config.json"
_LEGACY_HISTORY_NAME = "download_history.log"

DEFAULTS = {
    "last_folder": "",
    "theme": "dark",
    "default_resolution": "1080",
    "h264_enabled": True,
    "download_mode": "video",
    "audio_format": "mp3",
    "audio_bitrate": "192",
    "embed_thumbnail": True,
    "max_concurrent_downloads": 3,
    "cookies_browser": "",
}


def _legacy_paths(name):
    seen = []
    for d in (app_paths.exe_dir(), app_paths.BUNDLE_DIR, os.getcwd()):
        p = os.path.abspath(os.path.join(d, name))
        if p not in seen:
            seen.append(p)
    return seen


def _migrate_legacy():
    """Copy settings/history from the old per-app-dir files, once."""
    if not os.path.exists(CONFIG_FILE):
        for p in _legacy_paths(_LEGACY_CONFIG_NAME):
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # The old default output folder was effectively "current
                    # directory"; don't carry a stale folder over, the new
                    # default is the user's Downloads folder.
                    data.pop("last_folder", None)
                    save({**DEFAULTS, **data})
                except Exception:
                    pass
                break
    if not os.path.exists(HISTORY_FILE):
        for p in _legacy_paths(_LEGACY_HISTORY_NAME):
            if os.path.isfile(p) and os.path.abspath(p) != os.path.abspath(HISTORY_FILE):
                try:
                    with open(p, "r", encoding="utf-8") as src:
                        content = src.read()
                    with open(HISTORY_FILE, "w", encoding="utf-8") as dst:
                        dst.write(content)
                except Exception:
                    pass
                break


def _in_temp_dir(path):
    temp = os.path.realpath(tempfile.gettempdir())
    try:
        return os.path.commonpath([os.path.realpath(path), temp]) == temp
    except ValueError:
        # Different drives.
        return False


def _valid_folder(path):
    # A folder inside %TEMP% is never a sensible place to keep downloads;
    # fall back to the Downloads folder instead.
    return (bool(path) and os.path.isabs(path) and os.path.isdir(path)
            and not _in_temp_dir(path))


def load():
    _migrate_legacy()
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config.update(data)
        except Exception:
            pass
    if not _valid_folder(config.get("last_folder")):
        config["last_folder"] = app_paths.downloads_dir()
    return config


def save(config):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp, CONFIG_FILE)
    except Exception as e:
        print(f"Error saving config: {e}")
