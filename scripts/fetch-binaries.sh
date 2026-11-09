#!/usr/bin/env bash
# Downloads the yt-dlp, ffmpeg and ffprobe sidecars into src-tauri/binaries with the
# target-triple names Tauri expects (externalBin), and checks SHA-256 against
# scripts/binaries.lock.json.
#
#   bash scripts/fetch-binaries.sh [triple]      # default x86_64-unknown-linux-gnu
#
# Needs: curl, tar (with xz), sha256sum, python3 (only to read the JSON lock file).
# A lock entry with a sha256 must match, or the script fails. An empty sha256 prints the
# computed hash and continues. The ffmpeg URL is BtbN "latest" and is not pinned yet:
# copy the hash printed by the first CI run into binaries.lock.json to pin it.
set -euo pipefail

TRIPLE="${1:-x86_64-unknown-linux-gnu}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
LOCK="$HERE/binaries.lock.json"
BIN="$ROOT/src-tauri/binaries"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$BIN"

# lock <tool> <field>  ->  prints lock[tool].linux[field]
lock() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["linux"][sys.argv[3]])' "$LOCK" "$1" "$2"
}

# fetch <tool> <dest>
fetch() {
  local url want got
  url="$(lock "$1" url)"
  want="$(lock "$1" sha256 | tr 'A-F' 'a-f' | tr -d '[:space:]')"
  echo "Downloading $1 from $url"
  curl -fsSL --retry 3 -o "$2" "$url"
  got="$(sha256sum "$2" | cut -d' ' -f1)"
  if [ -z "$want" ]; then
    echo "WARNING: $1 has no pinned sha256 in binaries.lock.json. Computed sha256: $got"
  elif [ "$got" != "$want" ]; then
    echo "SHA-256 mismatch for $1. Expected $want, got $got" >&2
    exit 1
  else
    echo "$1 sha256 OK ($got)"
  fi
}

fetch yt-dlp "$BIN/yt-dlp-$TRIPLE"

fetch ffmpeg "$TMP/ffmpeg.tar.xz"
mkdir -p "$TMP/x"
tar -xJf "$TMP/ffmpeg.tar.xz" -C "$TMP/x"
for tool in ffmpeg ffprobe; do
  src="$(find "$TMP/x" -type f -name "$tool" | head -n1)"
  [ -n "$src" ] || { echo "$tool not found in the ffmpeg archive" >&2; exit 1; }
  cp "$src" "$BIN/$tool-$TRIPLE"
done

chmod +x "$BIN/yt-dlp-$TRIPLE" "$BIN/ffmpeg-$TRIPLE" "$BIN/ffprobe-$TRIPLE"
ls -la "$BIN"
