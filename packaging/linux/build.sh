#!/usr/bin/env bash
# Build the Linux standalone app with Nuitka and stage everything nfpm needs.
#
# Run from the repository root after `uv sync --locked`:
#   packaging/linux/build.sh
#
# Output (all under build/linux/):
#   dist/                      Nuitka standalone folder -> /opt/fetchly
#   icons/<N>x<N>/apps/*.png   hicolor icons
set -euo pipefail

cd "$(dirname "$0")/../.."

APP=fetchly
OUT=build/linux
PYTHON=${PYTHON:-.venv/bin/python}

rm -rf "$OUT"
mkdir -p "$OUT"

# Same trimming flags as build.bat (see docs/NUITKA_BUILD_NOTES.md; there is
# no "styles" Qt plugin family on Linux), but
# --standalone: the packages install a folder, so there is no onefile
# extraction step at every launch.
"$PYTHON" -m nuitka \
    --standalone \
    --lto=no \
    --jobs="$(nproc)" \
    --enable-plugin=pyqt6 \
    --noinclude-custom-mode=yt_dlp.extractor:bytecode \
    --include-package=yt_dlp_ejs \
    --include-package-data=yt_dlp_ejs \
    --nofollow-import-to=unittest,test,pytest,_pytest,doctest,pdb \
    --nofollow-import-to=setuptools,pip,distutils,pkg_resources \
    --noinclude-setuptools-mode=nofollow \
    --python-flag=no_docstrings \
    --include-qt-plugins=sensible,platforms,xcbglintegrations \
    --include-data-files=resources/icons/app.png=resources/icons/app.png \
    --include-data-files=resources/icons/app.ico=resources/icons/app.ico \
    --assume-yes-for-downloads \
    --output-filename="$APP" \
    --output-dir="$OUT/nuitka" \
    --remove-output \
    main.py

mv "$OUT/nuitka/main.dist" "$OUT/dist"
rm -rf "$OUT/nuitka"

# Prune Qt pieces the app never loads and that would otherwise pull in host
# libraries we do not want to depend on (GTK 3, CUPS, Kerberos) or that the
# PyQt6 wheel does not even ship (the EGLFS KMS support libraries).
QT="$OUT/dist/PyQt6/Qt6"
rm -rf \
    "$QT/plugins/egldeviceintegrations" \
    "$QT/plugins/printsupport" \
    "$QT/plugins/tls" \
    "$QT/plugins/platforms/libqeglfs.so" \
    "$QT/plugins/platforms/libqminimalegl.so" \
    "$QT/plugins/platforms/libqvnc.so" \
    "$QT/plugins/platforms/libqvkkhrdisplay.so" \
    "$QT/plugins/platformthemes/libqgtk3.so" \
    "$QT/plugins/imageformats/libqpdf.so" \
    "$OUT/dist/libQt6EglFSDeviceIntegration.so.6" \
    "$OUT/dist/libQt6Network.so.6" \
    "$OUT/dist/libQt6Pdf.so.6" \
    "$OUT/dist/libQt6PrintSupport.so.6"
# Nothing left may still link against what was removed.
stale=0
while IFS= read -r -d '' f; do
    if readelf -d "$f" 2>/dev/null \
            | grep -qE 'NEEDED.*libQt6(EglFSDeviceIntegration|Network|Pdf|PrintSupport)\.so'; then
        echo "error: $f still needs a pruned Qt library" >&2
        stale=1
    fi
done < <(find "$OUT/dist" -type f \( -name '*.so*' -o -name "$APP" \) -print0)
test "$stale" -eq 0

test -x "$OUT/dist/$APP"

"$PYTHON" packaging/linux/make_icons.py resources/icons/app_source.png "$OUT/icons"

echo "Staged in $OUT:"
du -sh "$OUT/dist"
