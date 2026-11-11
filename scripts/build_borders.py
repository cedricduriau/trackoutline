#!/usr/bin/env python3
"""Build trackoutline/data/borders.json from Natural Earth (public domain).

Countries come from the 1:50m admin-0 countries set; the United Kingdom is replaced by its
map subunits (England, Scotland, Wales, Northern Ireland) so they can be drawn separately.
Only exterior rings are kept, simplified with Douglas-Peucker.
"""

import json
import urllib.request
from pathlib import Path

import numpy as np

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
COUNTRIES = BASE + "ne_50m_admin_0_countries.geojson"
SUBUNITS = BASE + "ne_50m_admin_0_map_subunits.geojson"
EPSILON = 0.01  # degrees (~1 km)
OUTPUT = Path(__file__).resolve().parent.parent / "trackoutline" / "data" / "borders.json"


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)["features"]


def simplify(points, epsilon):
    """Iterative Douglas-Peucker on an (n, 2) array."""
    keep = np.zeros(len(points), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        a, b = points[start], points[end]
        segment = points[start + 1 : end]
        ab = b - a
        length = np.linalg.norm(ab)
        if length == 0:
            dist = np.linalg.norm(segment - a, axis=1)
        else:
            dist = np.abs(ab[0] * (segment[:, 1] - a[1]) - ab[1] * (segment[:, 0] - a[0])) / length
        i = int(np.argmax(dist))
        if dist[i] > epsilon:
            idx = start + 1 + i
            keep[idx] = True
            stack += [(start, idx), (idx, end)]
    return points[keep]


def exterior_rings(geometry):
    polygons = (
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    )
    rings = []
    for polygon in polygons:
        ring = simplify(np.array(polygon[0], dtype=float), EPSILON)
        if len(ring) >= 4:
            rings.append(np.round(ring, 3).tolist())
    return rings


def main():
    features = []
    for f in fetch(COUNTRIES):
        props = f["properties"]
        if props["ADM0_A3"] == "GBR":
            continue
        code = props["ISO_A2_EH"]
        if code in ("-99", ""):
            code = props["ADM0_A3"]
        features.append(
            {"code": code, "name": props["NAME"], "rings": exterior_rings(f["geometry"])}
        )
    for f in fetch(SUBUNITS):
        props = f["properties"]
        if props["ADM0_A3"] == "GBR":
            features.append(
                {
                    "code": f"GB-{props['SU_A3']}",
                    "name": props["NAME"],
                    "rings": exterior_rings(f["geometry"]),
                }
            )
    features = [f for f in features if f["rings"]]
    OUTPUT.write_text(json.dumps({"features": features}, separators=(",", ":")))
    print(f"{len(features)} shapes -> {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
