import pytest

from trackoutline import cli

URL = "https://x/maps/dir/50,4/51,6/52,4"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("auto", True), ("AUTO", True), ("BE,FR", ["BE", "FR"])],
)
def test_parse_borders(value, expected):
    assert cli.parse_borders(value) == expected


def test_main_writes_output(tmp_path, capsys):
    out = tmp_path / "t.svg"
    assert cli.main([URL, "-o", str(out), "--markers", "--borders", "BE"]) == 0
    assert out.exists()
    assert "3 waypoints" in capsys.readouterr().out


def test_main_reports_errors_without_traceback(tmp_path, capsys):
    assert cli.main([URL, "-o", str(tmp_path / "t.png"), "--smoothing", "2"]) == 1
    assert "error: smoothing must be between 0 and 1" in capsys.readouterr().err
