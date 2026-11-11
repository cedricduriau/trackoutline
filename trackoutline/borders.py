"""Country border data (Natural Earth, public domain) and drawing helpers."""

import json
from functools import lru_cache
from importlib import resources

import numpy as np

# Borders stay recognizable only up to this smoothing level, however abstract the route gets.
BORDER_MAX_SMOOTHING = 0.3
MIN_RING_SAMPLES = 128
MAX_RING_SAMPLES = 4000


@lru_cache(maxsize=1)
def load_shapes():
    """Return [{"code", "name", "rings": [[[lon, lat], ...], ...]}, ...]."""
    text = resources.files("trackoutline").joinpath("data/borders.json").read_text()
    return json.loads(text)["features"]


def select_shapes(codes=None):
    """Pick shapes by ISO code (e.g. BE, FR, GB-SCT); "GB" selects all UK nations.

    None selects everything. Raises ValueError for unknown codes.
    """
    shapes = load_shapes()
    if codes is None:
        return shapes
    wanted = {code.strip().upper() for code in codes if code.strip()}
    if "GB" in wanted:
        wanted |= {s["code"] for s in shapes if s["code"].startswith("GB-")}
    unknown = wanted - {s["code"] for s in shapes} - {"GB"}
    if unknown:
        raise ValueError(f"Unknown border code(s): {', '.join(sorted(unknown))}")
    return [s for s in shapes if s["code"] in wanted]


def smooth_ring(ring, sigma, step):
    """Gaussian-smooth a closed ring with an absolute sigma (plane units).

    Returns None when the ring is too small to survive at this smoothing level.
    """
    dist = np.r_[0, np.cumsum(np.linalg.norm(np.diff(ring, axis=0), axis=1))]
    perimeter = dist[-1]
    if perimeter < 4 * sigma:
        return None
    count = int(np.clip(perimeter / step, MIN_RING_SAMPLES, MAX_RING_SAMPLES))
    targets = np.linspace(0, perimeter, count, endpoint=False)
    points = np.column_stack([np.interp(targets, dist, ring[:, axis]) for axis in (0, 1)])
    kernel = np.exp(-2 * (np.pi * np.fft.fftfreq(count) * sigma / (perimeter / count)) ** 2)
    smoothed = np.fft.ifft(np.fft.fft(points, axis=0) * kernel[:, None], axis=0).real
    return np.vstack([smoothed, smoothed[:1]])


def prepare_rings(shapes, to_plane, bounds, sigma, step):
    """Project shape rings to the plane, crop them to bounds and smooth them.

    to_plane maps an (n, 2) array of (lat, lon) to plane coordinates; bounds is
    (lo, hi) of the visible area; sigma and step are the smoothing width and resampling
    step in plane units (sigma 0 leaves the rings untouched).
    """
    lo, hi = bounds
    rings = []
    for shape in shapes:
        for ring in shape["rings"]:
            xy = to_plane(np.array(ring)[:, ::-1])
            if (xy.max(0) < lo).any() or (xy.min(0) > hi).any():
                continue
            if sigma > 0:
                xy = smooth_ring(xy, sigma, step)
            if xy is not None:
                rings.append(xy)
    return rings
