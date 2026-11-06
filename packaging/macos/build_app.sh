#!/usr/bin/env bash
# Build "Fetchly.app" with PyInstaller (onedir .app bundle),
# bundle ffmpeg/ffprobe next to the main binary and ad-hoc sign the bundle.
#
# Nuitka is not used on macOS: it does not support PyQt6 there (the resulting
# app crashes in QtCore during startup).
#
# Run from the repository root after `uv sync --locked` and
# `uv pip install pyinstaller` (PyInstaller is intentionally not a project dep):
#   packaging/macos/build_app.sh <version> [ffmpeg-dir]
# Output: build_macos/Fetchly.app
set -euo pipefail

VERSION="${1:?usage: build_app.sh <version> [ffmpeg-dir]}"
FFMPEG_DIR="${2:-ffmpeg}"
APP_NAME="Fetchly"
BUNDLE_ID="com.abdullahmasood.fetchly"
OUT="build_macos"
ICNS="$OUT/app.icns"
PYTHON="${PYTHON:-.venv/bin/python}"
ROOT="$(pwd)"  # PyInstaller resolves relative paths against --specpath

mkdir -p "$OUT"
[ -f "$ICNS" ] || packaging/macos/make_icns.sh resources/icons/app_source.png "$ICNS"
rm -rf "$OUT/$APP_NAME.app" "$OUT/$APP_NAME" "$OUT/pyi-work"

# yt_dlp imports extractors lazily, so collect all of its submodules.
"$PYTHON" -m PyInstaller \
  --noconfirm --clean \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ROOT/$ICNS" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --target-arch arm64 \
  --add-data "$ROOT/resources/icons/app.png:resources/icons" \
  --add-data "$ROOT/resources/icons/app.ico:resources/icons" \
  --collect-submodules yt_dlp \
  --collect-data yt_dlp \
  --collect-all yt_dlp_ejs \
  --collect-all curl_cffi \
  --collect-data certifi \
  --exclude-module tkinter \
  --exclude-module nuitka \
  --distpath "$OUT" \
  --workpath "$OUT/pyi-work" \
  --specpath "$OUT" \
  main.py

APP="$OUT/$APP_NAME.app"
[ -d "$APP" ] || { echo "ERROR: $APP not produced" >&2; ls -la "$OUT"; exit 1; }
rm -rf "$OUT/$APP_NAME" "$OUT/pyi-work"   # onedir staging copy, not needed

PLIST="$APP/Contents/Info.plist"
pb() { /usr/libexec/PlistBuddy -c "$1" "$PLIST"; }
for kv in "CFBundleShortVersionString:$VERSION" "CFBundleVersion:$VERSION" \
          "CFBundleDisplayName:$APP_NAME" "LSMinimumSystemVersion:11.0" \
          "NSHumanReadableCopyright:Copyright (c) 2026 Abdullah Masood. GPL-3.0."; do
  key="${kv%%:*}"; val="${kv#*:}"
  pb "Set :$key $val" 2>/dev/null || pb "Add :$key string $val"
done
pb "Set :NSHighResolutionCapable true" 2>/dev/null || pb "Add :NSHighResolutionCapable bool true"

MACOS_DIR="$APP/Contents/MacOS"
EXE="$(pb 'Print :CFBundleExecutable')"
[ -x "$MACOS_DIR/$EXE" ] || { echo "ERROR: main binary $MACOS_DIR/$EXE missing" >&2; exit 1; }

# Bundle ffmpeg + ffprobe next to the main binary (app_paths.exe_dir()).
for tool in ffmpeg ffprobe; do
  [ -f "$FFMPEG_DIR/$tool" ] || { echo "ERROR: $FFMPEG_DIR/$tool not found" >&2; exit 1; }
  cp "$FFMPEG_DIR/$tool" "$MACOS_DIR/$tool"
  chmod 755 "$MACOS_DIR/$tool"
done

# Re-seal the bundle (Info.plist edits and ffmpeg invalidated the signature).
xattr -cr "$APP"
codesign --force --deep -s - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo ">> built $APP"
pb 'Print'
du -sh "$APP"
