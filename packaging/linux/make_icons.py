"""Render the hicolor theme icons for the Linux packages.

Usage: python make_icons.py <source.png> <output-dir>
Writes <output-dir>/<N>x<N>/apps/keepsake.png for each size.
"""

import sys
from pathlib import Path

from PIL import Image

SIZES = (48, 64, 128, 256, 512)
NAME = "keepsake.png"


def main():
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    with Image.open(source) as img:
        img = img.convert("RGBA")
        for size in SIZES:
            target = out / f"{size}x{size}" / "apps" / NAME
            target.parent.mkdir(parents=True, exist_ok=True)
            img.resize((size, size), Image.LANCZOS).save(target, optimize=True)
            print(target)


if __name__ == "__main__":
    main()
