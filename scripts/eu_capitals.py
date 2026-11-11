"""EU capitals (without Nicosia) plus London as a closed tour, for the README previews."""

import math

CAPITALS = {
    "Amsterdam": (52.3676, 4.9041),
    "Athens": (37.9838, 23.7275),
    "Berlin": (52.5200, 13.4050),
    "Bratislava": (48.1486, 17.1077),
    "Brussels": (50.8503, 4.3517),
    "Bucharest": (44.4268, 26.1025),
    "Budapest": (47.4979, 19.0402),
    "Copenhagen": (55.6761, 12.5683),
    "Dublin": (53.3498, -6.2603),
    "Helsinki": (60.1699, 24.9384),
    "Lisbon": (38.7223, -9.1393),
    "Ljubljana": (46.0569, 14.5058),
    "London": (51.5074, -0.1278),
    "Luxembourg": (49.6116, 6.1319),
    "Madrid": (40.4168, -3.7038),
    "Paris": (48.8566, 2.3522),
    "Prague": (50.0755, 14.4378),
    "Riga": (56.9496, 24.1052),
    "Rome": (41.9028, 12.4964),
    "Sofia": (42.6977, 23.3219),
    "Stockholm": (59.3293, 18.0686),
    "Tallinn": (59.4370, 24.7536),
    "Valletta": (35.8989, 14.5146),
    "Vienna": (48.2082, 16.3738),
    "Vilnius": (54.6872, 25.2797),
    "Warsaw": (52.2297, 21.0122),
    "Zagreb": (45.8150, 15.9819),
}

BORDER_CODES = [
    "AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB",
]  # fmt: skip


def _dist(a, b):
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[1] - b[1]) * math.cos(lat), a[0] - b[0])


def tour():
    """Nearest-neighbour tour refined with 2-opt, so the loop does not cross itself."""
    left = sorted(CAPITALS)
    order = [left.pop(0)]
    while left:
        last = CAPITALS[order[-1]]
        nearest = min(left, key=lambda name: _dist(last, CAPITALS[name]))
        left.remove(nearest)
        order.append(nearest)

    improved = True
    while improved:
        improved = False
        for i in range(1, len(order) - 1):
            for j in range(i + 1, len(order)):
                a, b = CAPITALS[order[i - 1]], CAPITALS[order[i]]
                c, d = CAPITALS[order[j]], CAPITALS[order[(j + 1) % len(order)]]
                if _dist(a, c) + _dist(b, d) < _dist(a, b) + _dist(c, d) - 1e-9:
                    order[i : j + 1] = reversed(order[i : j + 1])
                    improved = True
    return order


def url():
    points = "/".join(f"{CAPITALS[name][0]},{CAPITALS[name][1]}" for name in tour())
    return f"https://www.google.com/maps/dir/{points}"


if __name__ == "__main__":
    print(url())
