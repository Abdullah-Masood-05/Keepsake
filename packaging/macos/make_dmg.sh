#!/usr/bin/env bash
# Package the .app into a compressed (UDZO) DMG with an /Applications link.
#   packaging/macos/make_dmg.sh <path/to/App.app> <output.dmg>
set -euo pipefail

APP="${1:?usage: make_dmg.sh <App.app> <output.dmg>}"
DMG="${2:?usage: make_dmg.sh <App.app> <output.dmg>}"
VOLNAME="Satchel"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STAGING="$(mktemp -d)/dmg"
mkdir -p "$STAGING" "$(dirname "$DMG")"
# ditto preserves the code signature, symlinks and extended attributes.
ditto "$APP" "$STAGING/$(basename "$APP")"
ln -s /Applications "$STAGING/Applications"
cp "$SCRIPT_DIR/README-macOS.txt" "$STAGING/README-macOS.txt"

rm -f "$DMG"
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
hdiutil imageinfo "$DMG" | grep -q 'UDZO'
hdiutil verify "$DMG"
rm -rf "$(dirname "$STAGING")"
ls -lh "$DMG"
