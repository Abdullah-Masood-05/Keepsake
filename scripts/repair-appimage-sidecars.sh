#!/usr/bin/env bash
# Puts the pristine sidecars back into each AppImage built by `tauri build`.
#
# Why: linuxdeploy (used by Tauri's AppImage bundler) runs patchelf on every ELF file in
# usr/bin and adds RUNPATH=$ORIGIN/../lib. NO_STRIP stops the stripping but not this. On a
# static-pie binary such as keepsake-qjs (quickjs-ng) the rewritten dynamic section makes it
# segfault on start, so yt-dlp's JavaScript runtime is broken in the AppImage only. The deb
# and rpm ship the untouched files and work.
#
# What: extract the AppImage, copy src-tauri/binaries/<name>-<triple> over every sidecar that
# differs, then rebuild it from its own runtime (the bytes before --appimage-offset) and a new
# squashfs with the same compression. Nothing is downloaded.
#
# Usage: bash scripts/repair-appimage-sidecars.sh [bundle dir] [target triple]
# Needs: jq, squashfs-tools (mksquashfs, unsquashfs), cmp.
set -euo pipefail

B="${1:-src-tauri/target/release/bundle}"
TRIPLE="${2:-x86_64-unknown-linux-gnu}"
CONF="${KEEPSAKE_CONF:-src-tauri/tauri.conf.json}"
SRC="${KEEPSAKE_SIDECAR_DIR:-src-tauri/binaries}"

mapfile -t NAMES < <(jq -r '.bundle.externalBin[] | split("/") | last' "$CONF")
[ "${#NAMES[@]}" -gt 0 ] || { echo "::error::no bundle.externalBin entries in $CONF"; exit 1; }

shopt -s nullglob
apps=("$B"/appimage/*.AppImage)
[ "${#apps[@]}" -gt 0 ] || { echo "::error::no .AppImage in $B/appimage"; exit 1; }

for app in "${apps[@]}"; do
  abs="$(cd "$(dirname "$app")" && pwd)/$(basename "$app")"
  work="$(mktemp -d)"
  echo "=== $app"
  chmod +x "$abs"
  (cd "$work" && "$abs" --appimage-extract > /dev/null)
  root="$work/squashfs-root"

  restored=0
  for n in "${NAMES[@]}"; do
    f="$root/usr/bin/$n"
    src="$SRC/$n-$TRIPLE"
    [ -f "$f" ] || { echo "::error::$n missing from $(basename "$app")"; exit 1; }
    [ -f "$src" ] || { echo "::error::reference $src not found (fetch-binaries.sh not run?)"; exit 1; }
    if ! cmp -s "$f" "$src"; then
      install -m 755 "$src" "$f"
      echo "restored usr/bin/$n (linuxdeploy had rewritten it)"
      restored=1
    fi
  done

  if [ "$restored" = 1 ]; then
    offset="$("$abs" --appimage-offset)"
    comp="$(unsquashfs -s -o "$offset" "$abs" | awk '/^Compression/ {print $2; exit}')"
    head -c "$offset" "$abs" > "$work/runtime"
    mksquashfs "$root" "$work/fs.squashfs" -root-owned -noappend -quiet -comp "${comp:-gzip}"
    cat "$work/runtime" "$work/fs.squashfs" > "$abs.new"
    chmod 755 "$abs.new"
    mv "$abs.new" "$abs"
    echo "repacked $(basename "$app") ($comp)"
  else
    echo "sidecars already pristine, nothing to do"
  fi
  rm -rf "$work"
done
