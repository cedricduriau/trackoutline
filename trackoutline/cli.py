"""Command line interface."""

import argparse
import sys

from trackoutline.api import TrackOutlineError, create_outline


def build_parser():
    parser = argparse.ArgumentParser(
        prog="trackoutline",
        description="Turn a Google Maps directions link into a minimalist track outline.",
    )
    parser.add_argument("url", help="Google Maps directions link (quote it)")
    parser.add_argument("-o", "--output", default="track.png", help="output file: .png or .svg")
    parser.add_argument("-c", "--color", default="#111111", help="line color")
    parser.add_argument("--bg", default="white", help="background color, or 'none' for transparent")
    parser.add_argument("-w", "--width", type=float, default=6, help="line width in points")
    parser.add_argument("--size", type=float, default=8, help="image size in inches (square)")
    parser.add_argument("--dpi", type=int, default=300, help="PNG resolution")
    parser.add_argument("--markers", action="store_true", help="draw waypoint dots")
    parser.add_argument("--marker-color", default=None)
    parser.add_argument("--open", action="store_true", help="don't close the loop")
    parser.add_argument(
        "--borders",
        nargs="?",
        const="auto",
        default=None,
        metavar="CODES",
        help="draw country borders: 'auto' (every country in view) or comma-separated "
        "ISO codes, e.g. BE,FR,GB-SCT (GB = all UK nations)",
    )
    parser.add_argument("--border-color", default="#bbbbbb")
    parser.add_argument("--border-width", type=float, default=1.5)
    parser.add_argument("--border-alpha", type=float, default=1.0)
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.0,
        help="0 (through every waypoint) to 1 (very abstract); closed loops only",
    )
    return parser


def parse_borders(value):
    """Map the --borders argument to create_outline's borders parameter."""
    if value is None:
        return None
    if value.lower() == "auto":
        return True
    return value.split(",")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        count = create_outline(
            args.url,
            output=args.output,
            closed=not args.open,
            smoothing=args.smoothing,
            borders=parse_borders(args.borders),
            on_geocode=lambda name: print(f"geocoding: {name}", file=sys.stderr),
            color=args.color,
            background=args.bg,
            width=args.width,
            size=args.size,
            dpi=args.dpi,
            markers=args.markers,
            marker_color=args.marker_color,
            border_color=args.border_color,
            border_width=args.border_width,
            border_alpha=args.border_alpha,
        )
    except TrackOutlineError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print(f"{count} waypoints -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
