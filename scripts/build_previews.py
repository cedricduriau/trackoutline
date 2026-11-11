#!/usr/bin/env python3
"""Regenerate the README preview images in docs/previews (SVG)."""

import sys
from pathlib import Path

from trackoutline import create_outline

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eu_capitals import BORDER_CODES, url  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "previews"

RED = "#e10600"
YELLOW = "#ffd400"
DARK = "#111111"

PREVIEWS = {
    "default": {},
    "color-markers": {"color": RED, "markers": True},
    "dark": {"color": YELLOW, "background": DARK, "markers": True},
    "smoothing-0": {"color": RED, "smoothing": 0.0},
    "smoothing-01": {"color": RED, "smoothing": 0.1},
    "smoothing-03": {"color": RED, "smoothing": 0.3},
    "borders": {"color": RED, "markers": True, "smoothing": 0.03, "borders": BORDER_CODES},
    "borders-dark": {
        "color": YELLOW,
        "background": DARK,
        "border_color": "#555555",
        "smoothing": 0.03,
        "borders": BORDER_CODES,
    },
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    route = url()
    for name, options in PREVIEWS.items():
        options = {"color": "black", "width": 3, **options}
        create_outline(route, output=str(OUT / f"{name}.svg"), **options)
        print(name)


if __name__ == "__main__":
    main()
