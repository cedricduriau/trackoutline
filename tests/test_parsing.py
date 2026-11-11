import pytest

from trackoutline import TrackOutlineError, api


@pytest.fixture
def geocoded(monkeypatch):
    """Replace Nominatim with a stub and record the names it was asked for."""
    names = []

    def fake(name):
        names.append(name)
        return 50.0 + len(names), 4.0

    monkeypatch.setattr(api, "geocode", fake)
    return names


def test_parse_dms():
    lat, lon = api.parse_dms("61°00'43.0\"N 17°08'50.3\"E")
    assert lat == pytest.approx(61.01194, abs=1e-4)
    assert lon == pytest.approx(17.14731, abs=1e-4)
    assert api.parse_dms("Paris") is None


def test_parse_dms_southwest_is_negative():
    lat, lon = api.parse_dms("33°52'00.0\"S 151°12'00.0\"W")
    assert lat < 0 and lon < 0


def test_latlon_segments_and_closing_point_dropped():
    url = "https://www.google.com/maps/dir/1,1/2,2/3,1/1,1/@2,2,5z"
    assert api.parse_waypoints(url) == [(1.0, 1.0), (2.0, 2.0), (3.0, 1.0)]


def test_embedded_coordinates_win_over_names(geocoded):
    url = "https://x/maps/dir/A/B/C/data=!1d3.5!2d51.5!1d4!2d52!1d5.25!2d50"
    assert api.parse_waypoints(url) == [(51.5, 3.5), (52.0, 4.0), (50.0, 5.25)]
    assert geocoded == []


def test_encoded_slash_stays_inside_place_name(geocoded):
    url = "https://x/maps/dir/A/The+Belgium%2FFrance+tri-point/C"
    api.parse_waypoints(url)
    assert geocoded == ["A", "The Belgium/France tri-point", "C"]


def test_non_directions_link_is_rejected(geocoded):
    with pytest.raises(TrackOutlineError, match="/dir/"):
        api.parse_waypoints("https://www.google.com/maps/place/Paris")
    assert geocoded == []


def test_too_few_waypoints():
    with pytest.raises(TrackOutlineError, match="at least 3"):
        api.parse_waypoints("https://x/maps/dir/1,1/2,2")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"output": "x.jpg"}, "must end in"),
        ({"smoothing": 1.5}, "between 0 and 1"),
        ({"smoothing": 0.2, "closed": False}, "closed loops"),
        ({"output": "/nonexistent-dir/x.png"}, "does not exist"),
        ({"borders": ["XX"]}, "Unknown border"),
    ],
)
def test_create_outline_validation(tmp_path, kwargs, message):
    url = "https://x/maps/dir/1,1/2,2/3,1"
    kwargs = {"output": str(tmp_path / "x.png"), **kwargs}
    with pytest.raises(TrackOutlineError, match=message):
        api.create_outline(url, **kwargs)


class FakeResponse:
    def __init__(self, body=b"[]", url="https://resolved"):
        self.body, self.url = body, url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self.body

    def geturl(self):
        return self.url


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)


def test_geocode_falls_back_to_coarser_query(monkeypatch, no_sleep):
    queries = []

    def fake_urlopen(req, timeout):
        queries.append(req.full_url)
        found = len(queries) == 2
        return FakeResponse(b'[{"lat": "50.5", "lon": "4.5"}]' if found else b"[]")

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    assert api.geocode("Some Camp, Village, Belgium") == (50.5, 4.5)
    assert len(queries) == 2
    assert "Village" in queries[1] and "Some" not in queries[1]


def test_geocode_failure_is_a_track_outline_error(monkeypatch, no_sleep):
    monkeypatch.setattr(api.urllib.request, "urlopen", lambda req, timeout: FakeResponse(b"[]"))
    with pytest.raises(TrackOutlineError, match="Could not geocode"):
        api.geocode("Nowhere")

    def offline(req, timeout):
        raise OSError("offline")

    monkeypatch.setattr(api.urllib.request, "urlopen", offline)
    with pytest.raises(TrackOutlineError, match="offline"):
        api.geocode("Anywhere")


def test_short_links_are_resolved(monkeypatch):
    monkeypatch.setattr(
        api.urllib.request, "urlopen", lambda req, timeout: FakeResponse(url="https://full/dir/")
    )
    assert api.resolve_url("https://maps.app.goo.gl/abc") == "https://full/dir/"
    assert api.resolve_url("https://www.google.com/maps/dir/a/b") == (
        "https://www.google.com/maps/dir/a/b"
    )
