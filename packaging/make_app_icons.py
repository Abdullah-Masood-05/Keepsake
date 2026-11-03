"""Build the app icons from the logo artwork.

The artwork (resources/icons/source/logo_artwork.jpg) is a flat JPEG: the mark
on a #101010 tile with black corners and no transparency. This script lifts
the mark off that background, centres it on a freshly drawn tile and writes:

  resources/icons/app_source.png  1024 px master (Linux hicolor, macOS icns)
  resources/icons/app.png         512 px (window icon, header logo)
  resources/icons/app.ico         16-256 px (Windows exe, installer)

Usage: python packaging/make_app_icons.py   (needs Pillow)
"""

import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "resources", "icons")
ARTWORK = os.path.join(ICONS, "source", "logo_artwork.jpg")

# Tile colours: a near-black that sits just above the app's dark surfaces, so
# the icon reads on dark taskbars and on light ones.
TILE_TOP = (34, 30, 36)
TILE_BOTTOM = (12, 11, 14)
GLOW = (214, 30, 72)           # the mark's crimson
SS = 4                         # supersampling factor for smooth edges


def extract_mark(path):
    """Return the mark as RGBA with a clean alpha, cropped to its bounds."""
    rgb = Image.open(path).convert("RGB")
    r, g, b = rgb.split()
    brightest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    # Background is 15-17; the darkest part of the mark is ~140. Ramp between
    # the two so anti-aliased edges keep their softness and JPEG noise drops.
    lo, hi = 30, 90
    alpha = brightest.point(
        lambda v: 0 if v <= lo else 255 if v >= hi else int((v - lo) * 255 / (hi - lo))
    )
    mark = rgb.convert("RGBA")
    mark.putalpha(alpha)
    return mark.crop(alpha.getbbox())


def vertical_gradient(size, top, bottom):
    w, h = size
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return grad.resize((w, h))


def render(size, mark, inset, radius, mark_scale, shadow, glow):
    """Render the icon at `size` px.

    inset/radius are fractions of `size`; mark_scale is the mark's largest
    side as a fraction of the tile.
    """
    S = size * SS
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pad = round(S * inset)
    tile_box = (pad, pad, S - pad, S - pad)
    tile_w = tile_box[2] - tile_box[0]
    rad = round(S * radius)

    tile_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(tile_box, rad, fill=255)

    if shadow:
        sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        sh_mask = tile_mask.filter(ImageFilter.GaussianBlur(S * 0.018))
        sh_mask = ImageChops.offset(sh_mask, 0, round(S * 0.012))
        sh.putalpha(sh_mask.point(lambda v: v * 0.45))
        canvas = Image.alpha_composite(canvas, sh)

    tile = vertical_gradient((S, S), TILE_TOP, TILE_BOTTOM).convert("RGBA")

    if glow:
        # Faint crimson bloom behind the swirl for depth.
        bloom = Image.new("L", (S, S), 0)
        c, rr = S / 2, tile_w * 0.30
        ImageDraw.Draw(bloom).ellipse((c - rr, c - rr, c + rr, c + rr), fill=255)
        bloom = bloom.filter(ImageFilter.GaussianBlur(tile_w * 0.16)).point(lambda v: v * 0.22)
        tile = Image.composite(Image.new("RGBA", (S, S), GLOW + (255,)), tile, bloom)

    # Hairline highlight along the top edge of the tile.
    stroke = max(1, round(S * 0.004))
    edge = Image.new("L", (S, S), 0)
    ImageDraw.Draw(edge).rounded_rectangle(tile_box, rad, outline=255, width=stroke)
    fade = vertical_gradient((S, S), (60, 60, 60), (8, 8, 8)).convert("L")
    tile = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), tile,
                           ImageChops.multiply(edge, fade))

    tile.putalpha(tile_mask)
    canvas = Image.alpha_composite(canvas, tile)

    # Mark, centred on the tile by its bounding box.
    target = round(tile_w * mark_scale)
    scale = target / max(mark.size)
    m = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    x = (S - m.width) // 2
    y = (S - m.height) // 2
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    layer.paste(m, (x, y), m)
    canvas = Image.alpha_composite(canvas, layer)

    return canvas.resize((size, size), Image.LANCZOS)


def main():
    mark = extract_mark(ARTWORK)

    # The mark is the icon: keep the tile margin thin and let the artwork fill it.
    master = render(1024, mark, inset=0.02, radius=0.20, mark_scale=0.88,
                    shadow=False, glow=True)
    master.save(os.path.join(ICONS, "app_source.png"), optimize=True)
    master.resize((512, 512), Image.LANCZOS).save(os.path.join(ICONS, "app.png"), optimize=True)

    # Windows: small sizes drop the glow and push the mark to the tile edge so it
    # stays legible in Explorer and the taskbar.
    ico_frames = []
    for s in (256, 128, 64, 48, 32, 24, 16):
        small = s <= 32
        ico_frames.append(render(
            s, mark,
            inset=0.0 if small else 0.02,
            radius=0.20,
            mark_scale=0.94 if small else 0.88,
            shadow=False,
            glow=not small,
        ))
    ico_frames[0].save(os.path.join(ICONS, "app.ico"), sizes=[f.size for f in ico_frames],
                       append_images=ico_frames[1:])
    print("wrote app_source.png, app.png, app.ico")


if __name__ == "__main__":
    main()
