"""Extra icons ported from the Tauri/React rewrite (rust-tauri/src/components/ui/Icon.tsx).

Importing this module registers the icons with theme.register_icons(), so they
can be used anywhere via theme.icon(name, color_key, px) / theme.bind_icon().
Same body format as theme._SVG: 24x24 viewBox, {c} is the colour placeholder,
1.8 stroke, square caps and miter joins.
"""

import theme

_STROKE = 'fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="square" stroke-linejoin="miter"'


def _p(d):
    return f'<path d="{d}" {_STROKE}/>'


def _circle(cx, cy, r):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" {_STROKE}/>'


def _dot(cx, cy, r=1.2):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{{c}}"/>'


ICONS = {
    "home": _p("M3.5 11 12 3.5l8.5 7.5M5.5 9.8v10.7h4.5v-6h4v6h4.5V9.8"),
    "downloads": _p("M12 3.5v11M7.5 10l4.5 4.5 4.5-4.5M3.5 13.5v7h17v-7"),
    "history": _p("M3 12a9 9 0 1 0 2.6-6.3L3 8.5M3 3.5v5h5M12 7.5V12l3 2"),
    "library": _p("M4 4h6v16H4zM14 4l6 1.5-3.5 15L11 19"),
    "settings": _p(
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1"
        "a7.6 7.6 0 0 0-2-1.2L14.5 3h-5l-.4 2.6a7.6 7.6 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6"
        "a7.4 7.4 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7.6 7.6 0 0 0 2 1.2l.4 2.6h5l.4-2.6"
        "a7.6 7.6 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z"
    ),
    "heart": _p(
        "M12 20s-7.5-4.6-9.2-9.3C1.7 7.6 3.8 4.5 7 4.5c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3"
        " 3.2 0 5.3 3.1 4.2 6.2C19.5 15.4 12 20 12 20z"
    ),
    "globe": _circle(12, 12, 9)
    + _p("M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18"),
    "cookie": _circle(12, 12, 9) + _dot(8.5, 9.5) + _dot(14.5, 13.5) + _dot(9.5, 15.5),
    "info": _circle(12, 12, 9) + _p("M12 11v6") + _dot(12, 7.8, 1.1),
    "retry": _p(
        "M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"
    ),
    "external": _p("M11 5.5H4.5v14h14v-6.5M14 4.5h5.5V10M19.5 4.5l-8.5 8.5"),
    "search": _circle(11, 11, 7) + _p("M20 20l-4.3-4.3"),
    "pause": _p("M8.5 5.5v13M15.5 5.5v13").replace('stroke-width="1.8"', 'stroke-width="2.2"'),
    "x_circle": _circle(12, 12, 9) + _p("M9 9l6 6M15 9l-6 6"),
    "check_circle": _circle(12, 12, 9) + _p("M8 12.5l2.8 2.8L16 9.5"),
    "warning": _p("M12 3.5 21.5 20h-19z") + _p("M12 10v4.5") + _dot(12, 17.2, 1.1),
    "music": _p("M9 18V6l10-2v12M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM19 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z"),
    "video": _p("M3 6.5h13v11H3zM16 10l5-3v10l-5-3"),
    "image": _p("M3 5h18v14H3zM3 16l5-5 4 4 3-3 6 6M15 9.5a1.5 1.5 0 1 0 0-.01"),
    "plus": _p("M12 5v14M5 12h14"),
    "sidebar_collapse": _p("M3.5 4.5h17v15h-17zM9.5 4.5v15M16 10l-2.5 2 2.5 2"),
}

theme.register_icons(ICONS)
