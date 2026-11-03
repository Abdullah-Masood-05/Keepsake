"""Build the app icons from the logo artwork.

The artwork (resources/icons/source/logo_artwork.jpg) is a flat JPEG: the mark
on a #101010 square with black corners and no transparency. This script lifts
the circular mark off that background onto transparency and writes:

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

# Swirl ring in the artwork's pixel coordinates (centre x, centre y, radius),
# measured from the 1254 px JPEG; the ring's outer edge is at ~385 px.
DISC = (555, 605, 360)
DISC_COLOR = (20, 18, 22)
SS = 4                         # supersampling factor for smooth edges


def extract_mark(path):
    """Return the mark as RGBA on transparency, cropped to its bounds."""
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

    # The artwork relies on its black background for the gaps between the
    # swirl strands and for contrast behind the pale play button. Keep that as
    # a dark disc tucked just inside the swirl ring, so the mark still reads on
    # light backgrounds.
    w, h = rgb.size
    k = 4
    disc = Image.new("L", (w * k, h * k), 0)
    cx, cy, rad = DISC
    ImageDraw.Draw(disc).ellipse(((cx - rad) * k, (cy - rad) * k, (cx + rad) * k, (cy + rad) * k),
                                 fill=255)
    disc = disc.resize((w, h), Image.LANCZOS)
    backed = Image.new("RGBA", (w, h), DISC_COLOR + (0,))
    backed.putalpha(disc)
    backed = Image.alpha_composite(backed, mark)
    return backed.crop(backed.getchannel("A").getbbox())


def brighten(mark, factor):
    """Lift the deep reds so the swirl doesn't turn into a dark blob when tiny."""
    r, g, b, a = mark.split()
    lift = lambda v: min(255, round(v * factor))
    return Image.merge("RGBA", (r.point(lift), g.point(lift), b.point(lift), a))


def render(size, mark, scale=0.98):
    """The mark centred on a transparent square canvas."""
    S = size * SS
    target = round(S * scale)
    k = target / max(mark.size)
    m = mark.resize((round(mark.width * k), round(mark.height * k)), Image.LANCZOS)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(m, ((S - m.width) // 2, (S - m.height) // 2), m)
    out = canvas.resize((size, size), Image.LANCZOS)
    if size <= 48:
        out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=80, threshold=0))
    return out


def main():
    mark = extract_mark(ARTWORK)

    # macOS and Linux docks add their own spacing; leave a little margin.
    render(1024, mark, scale=0.92).save(os.path.join(ICONS, "app_source.png"), optimize=True)
    render(512, mark).save(os.path.join(ICONS, "app.png"), optimize=True)

    ico_frames = []
    for s in (256, 128, 64, 48, 40, 32, 24, 20, 16):
        m = brighten(mark, 1.35) if s <= 48 else mark
        ico_frames.append(render(s, m))
    ico_frames[0].save(os.path.join(ICONS, "app.ico"), sizes=[f.size for f in ico_frames],
                       append_images=ico_frames[1:])
    print("wrote app_source.png, app.png, app.ico")


if __name__ == "__main__":
    main()
