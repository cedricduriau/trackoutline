import subprocess
import sys

import matplotlib.image as mpimg
import numpy as np
import pytest

from trackoutline import api, borders

URL = "https://x/maps/dir/50,4/51,6/52,4/51,2/50,4"


def test_closed_spline_passes_through_every_point_and_closes():
    points = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    curve = api.catmull_rom(points, closed=True)
    assert np.allclose(curve[0], curve[-1])
    for point in points:
        assert np.linalg.norm(curve - point, axis=1).min() < 1e-9


def test_smoothing_keeps_curve_closed_and_shrinks_it():
    points = np.array([[0.0, 0.0], [1.0, 0.2], [1.0, 1.0], [0.0, 1.0]])
    curve = api.catmull_rom(points)
    smoothed = api.smooth_closed(curve, 0.5)
    assert np.allclose(smoothed[0], smoothed[-1])
    assert np.ptp(smoothed, axis=0).max() < np.ptp(curve, axis=0).max()


def test_png_output_and_transparent_background(tmp_path):
    out = tmp_path / "t.png"
    assert api.create_outline(URL, output=str(out), background="none") == 4
    image = mpimg.imread(out)
    assert image.shape[2] == 4
    assert image[0, 0, 3] == 0


def test_svg_output_is_reproducible(tmp_path):
    first, second = tmp_path / "a.svg", tmp_path / "b.svg"
    api.create_outline(URL, output=str(first), markers=True, smoothing=0.2)
    api.create_outline(URL, output=str(second), markers=True, smoothing=0.2)
    assert first.read_bytes() == second.read_bytes()


def test_importing_the_library_leaves_pyplot_alone():
    code = "import sys, trackoutline; assert 'matplotlib.pyplot' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_gb_selects_all_uk_nations():
    codes = {shape["code"] for shape in borders.select_shapes(["GB"])}
    assert codes == {"GB-ENG", "GB-SCT", "GB-WLS", "GB-NIR"}


def test_unknown_border_code():
    with pytest.raises(ValueError, match="XX"):
        borders.select_shapes(["BE", "XX"])


def test_borders_render(tmp_path):
    out = tmp_path / "b.svg"
    api.create_outline(URL, output=str(out), borders=["GB", "FR"], smoothing=0.1)
    assert out.stat().st_size > 1000
