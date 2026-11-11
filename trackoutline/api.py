"""Library API: Google Maps link -> waypoints -> smooth closed curve -> PNG/SVG."""

import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, unquote_plus

import matplotlib
import numpy as np
from matplotlib.figure import Figure

from trackoutline import borders as border_data

SUPPORTED_FORMATS = (".png", ".svg")
SVG_HASH_SALT = "trackoutline"  # stable element ids -> reproducible SVGs
SAMPLES_PER_SEGMENT = 60
SMOOTHING_SAMPLES = 2000
VIEW_PADDING = 0.08  # fraction of the route span added around it
MAX_SMOOTHING_SIGMA = 0.08  # smoothing=1 -> gaussian sigma of 8% of the loop length
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_INTERVAL = 1.1  # seconds, per the Nominatim usage policy

_last_geocode_time = 0.0


class TrackOutlineError(Exception):
    """Raised when a link cannot be turned into an outline."""


def resolve_url(url):
    """Follow redirects for short links (maps.app.goo.gl, goo.gl)."""
    if not re.search(r"goo\.gl|g\.co", url):
        return url
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.geturl()
    except OSError as err:
        raise TrackOutlineError(f"Could not resolve short link: {err}") from err


def parse_dms(segment):
    """Parse a segment like 61°00'43.0"N 17°08'50.3"E into (lat, lon), or None."""
    matches = re.findall(r"(\d+)\D+(\d+)\D+(\d+(?:\.\d+)?)\D*([NSEW])", segment)
    if len(matches) != 2:
        return None
    values = {}
    for deg, minutes, seconds, hemisphere in matches:
        value = float(deg) + float(minutes) / 60 + float(seconds) / 3600
        values[hemisphere] = -value if hemisphere in "SW" else value
    lat = values.get("N", values.get("S"))
    lon = values.get("E", values.get("W"))
    if lat is None or lon is None:
        return None
    return lat, lon


def geocode(name):
    """Resolve a place name to (lat, lon) via Nominatim.

    Falls back to progressively coarser queries by dropping leading address parts.
    """
    global _last_geocode_time
    parts = [p.strip() for p in name.split(",") if p.strip()]
    for i in range(len(parts)):
        wait = NOMINATIM_INTERVAL - (time.time() - _last_geocode_time)
        if wait > 0:
            time.sleep(wait)
        _last_geocode_time = time.time()
        url = f"{NOMINATIM_URL}?format=json&limit=1&q={quote(', '.join(parts[i:]))}"
        req = urllib.request.Request(url, headers={"User-Agent": "trackoutline/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                results = json.load(resp)
        except (OSError, ValueError) as err:
            raise TrackOutlineError(f"Geocoding failed for {name!r}: {err}") from err
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    raise TrackOutlineError(f"Could not geocode: {name}")


def parse_waypoints(url, on_geocode=None):
    """Return [(lat, lon), ...] from a Google Maps /dir/ URL.

    on_geocode, if given, is called with each place name before it is geocoded.
    """
    # Exact coordinates embedded in the data param: !1d<lon>!2d<lat>
    points = [
        (float(lat), float(lon))
        for lon, lat in re.findall(r"!1d(-?\d+(?:\.\d+)?)!2d(-?\d+(?:\.\d+)?)", unquote(url))
    ]
    if len(points) >= 3:
        return _drop_closing_point(points)

    if "/dir/" not in url:
        raise TrackOutlineError("Not a Google Maps directions link (expected /dir/ in the URL).")

    points = []
    cache = {}
    path = re.split(r"/@|/data=|\?", url.split("/dir/", 1)[1])[0]
    # Split before decoding, so an encoded slash (%2F) stays inside its place name.
    for raw_segment in path.split("/"):
        segment = unquote_plus(raw_segment).strip()
        if not segment:
            continue
        latlon = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", segment)
        if latlon:
            points.append((float(latlon.group(1)), float(latlon.group(2))))
        elif parse_dms(segment):
            points.append(parse_dms(segment))
        else:
            if segment not in cache:
                if on_geocode:
                    on_geocode(segment)
                cache[segment] = geocode(segment)
            points.append(cache[segment])
    return _drop_closing_point(points)


def _drop_closing_point(points):
    """A route returning to its start is already closed; drop the duplicate."""
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        raise TrackOutlineError("Need at least 3 distinct waypoints.")
    return points


def projector(points):
    """Return a function projecting (lat, lon) arrays to a local plane centered on points.

    Equirectangular projection: x east, y north, in radians-equivalent units.
    """
    arr = np.array(points)
    lat0, lon0 = arr[:, 0].mean(), arr[:, 1].mean()
    cos_lat0 = np.cos(np.radians(lat0))

    def to_plane(latlon):
        latlon = np.asarray(latlon)
        x = np.radians(latlon[:, 1] - lon0) * cos_lat0
        y = np.radians(latlon[:, 0] - lat0)
        return np.column_stack([x, y])

    return to_plane


def project(points):
    """Project (lat, lon) points to the local plane centered on their mean."""
    return projector(points)(points)


def catmull_rom(points, closed=True, alpha=0.5):
    """Centripetal Catmull-Rom spline through all points."""
    n = len(points)

    def at(i):
        return points[i % n] if closed else points[min(max(i, 0), n - 1)]

    curve = []
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
        if not closed:  # reflect phantom end points so tangents stay sane
            if i == 0:
                p0 = 2 * p1 - p2
            if i == n - 2:
                p3 = 2 * p2 - p1
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-12) ** alpha
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-12) ** alpha
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-12) ** alpha
        t = np.linspace(t1, t2, SAMPLES_PER_SEGMENT, endpoint=False)[:, None]
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        curve.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    curve.append((points[0] if closed else points[-1])[None, :])
    return np.vstack(curve)


def view_bounds(curve):
    """Return (lo, hi) of the visible area: the curve's bounds plus padding."""
    lo, hi = curve.min(0), curve.max(0)
    pad = (hi - lo).max() * VIEW_PADDING
    return lo - pad, hi + pad


def render(
    curve,
    points,
    output,
    color="#111111",
    background="white",
    width=6,
    size=8,
    dpi=300,
    markers=False,
    marker_color=None,
    border_rings=(),
    border_color="#bbbbbb",
    border_width=1.5,
    border_alpha=1.0,
):
    """Draw the curve (and optionally waypoint markers and border rings) to a PNG or SVG file.

    The format follows the output extension. dpi only affects PNG.
    """
    transparent = background == "none"
    fig = Figure(figsize=(size, size), dpi=dpi)
    ax = fig.subplots()
    if not transparent:
        fig.patch.set_facecolor(background)
        ax.set_facecolor(background)
    for ring in border_rings:
        ax.plot(
            ring[:, 0],
            ring[:, 1],
            color=border_color,
            linewidth=border_width,
            alpha=border_alpha,
            solid_joinstyle="round",
        )
    ax.plot(
        curve[:, 0],
        curve[:, 1],
        color=color,
        linewidth=width,
        solid_capstyle="round",
        solid_joinstyle="round",
        zorder=2,
    )
    if markers:
        ax.scatter(
            points[:, 0],
            points[:, 1],
            s=width * 12,
            color=marker_color or color,
            zorder=3,
            edgecolors="none" if transparent else background,
            linewidths=width / 3,
        )
    ax.set_aspect("equal")
    ax.axis("off")
    lo, hi = view_bounds(curve)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    with matplotlib.rc_context({"svg.hashsalt": SVG_HASH_SALT}):
        fig.savefig(
            output,
            transparent=transparent,
            bbox_inches="tight",
            pad_inches=0.2,
            facecolor="none" if transparent else background,
            metadata={"Date": None} if Path(output).suffix.lower() == ".svg" else None,
        )


def resample(curve, count=SMOOTHING_SAMPLES):
    """Resample a polyline to evenly spaced points along its arc length."""
    dist = np.r_[0, np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))]
    targets = np.linspace(0, dist[-1], count, endpoint=False)
    return np.column_stack([np.interp(targets, dist, curve[:, axis]) for axis in (0, 1)])


def smooth_closed(curve, smoothing):
    """Gaussian-smooth a closed curve; smoothing is 0..1 (fraction of MAX_SMOOTHING_SIGMA).

    Returns a closed curve (first point repeated at the end).
    """
    points = resample(curve)
    n = len(points)
    sigma = smoothing * MAX_SMOOTHING_SIGMA * n
    kernel = np.exp(-2 * (np.pi * np.fft.fftfreq(n) * sigma) ** 2)
    smoothed = np.fft.ifft(np.fft.fft(points, axis=0) * kernel[:, None], axis=0).real
    return np.vstack([smoothed, smoothed[:1]])


def snap_to_curve(points, curve):
    """Move each point to the nearest point on the curve."""
    nearest = np.argmin(np.linalg.norm(curve[None] - points[:, None], axis=2), axis=1)
    return curve[nearest]


def border_rings_for(to_plane, base_curve, smoothing, codes):
    """Build projected, cropped and smoothed border rings around a route."""
    try:
        shapes = border_data.select_shapes(codes)
    except ValueError as err:
        raise TrackOutlineError(str(err)) from err
    loop_length = np.linalg.norm(np.diff(base_curve, axis=0), axis=1).sum()
    sigma = min(smoothing, border_data.BORDER_MAX_SMOOTHING) * MAX_SMOOTHING_SIGMA * loop_length
    step = loop_length / SMOOTHING_SAMPLES
    return border_data.prepare_rings(shapes, to_plane, view_bounds(base_curve), sigma, step)


def create_outline(
    url,
    output="track.png",
    closed=True,
    smoothing=0.0,
    borders=None,
    on_geocode=None,
    **style,
):
    """Create a track outline (PNG or SVG) from a Google Maps link.

    smoothing is 0..1: 0 passes through every waypoint, higher values give a
    more abstract curve (closed loops only; markers snap onto the curve).
    borders draws country borders under the route: True for every country in view, or
    a list of ISO codes such as ["BE", "FR", "GB-SCT"] ("GB" selects all UK nations).
    Borders are smoothed along with the route, capped at a level that keeps them readable.
    style accepts the keyword arguments of render (color, background, width,
    size, dpi, markers, marker_color, border_color, border_width, border_alpha).
    Returns the number of waypoints used.
    """
    if Path(output).suffix.lower() not in SUPPORTED_FORMATS:
        raise TrackOutlineError(f"Output must end in {' or '.join(SUPPORTED_FORMATS)}.")
    if not Path(output).resolve().parent.is_dir():
        raise TrackOutlineError(f"Output directory does not exist: {Path(output).parent}")
    if not 0 <= smoothing <= 1:
        raise TrackOutlineError("smoothing must be between 0 and 1.")
    if smoothing > 0 and not closed:
        raise TrackOutlineError("smoothing is only supported for closed loops.")
    latlon = parse_waypoints(resolve_url(url), on_geocode=on_geocode)
    to_plane = projector(latlon)
    points = to_plane(latlon)
    curve = catmull_rom(points, closed=closed)
    marker_points = points
    border_rings = []
    if borders:
        codes = None if borders is True else borders
        border_rings = border_rings_for(to_plane, curve, smoothing, codes)
    if smoothing > 0:
        curve = smooth_closed(curve, smoothing)
        marker_points = snap_to_curve(points, curve)
    try:
        render(curve, marker_points, output, border_rings=border_rings, **style)
    except OSError as err:
        raise TrackOutlineError(f"Could not write {output}: {err}") from err
    return len(points)
