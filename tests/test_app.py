import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from origen import __version__, data
from origen.app import MOTTO, WEB, create_app

from .conftest import REAL_DATA, needs_data


def test_healthz_without_data_is_degraded(empty_dir: Path) -> None:
    r = TestClient(create_app(empty_dir)).get("/healthz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["version"] == __version__
    assert body["ephemeris"] == "DE440s"
    assert body["stars"] == data.STARS
    assert body["data"] == {"de440s": "missing", "hipparcos": "missing", "iau_names": "missing"}


@needs_data
def test_healthz_with_data_is_ok() -> None:
    r = TestClient(create_app(REAL_DATA)).get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_page_opens_with_the_motto(empty_dir: Path) -> None:
    r = TestClient(create_app(empty_dir)).get("/")
    assert r.status_code == 200
    first_text = re.search(r"<body>\s*<main>\s*<p[^>]*>([^<]+)</p>", r.text)
    assert first_text and first_text.group(1) == MOTTO
    assert "Content-Security-Policy" in r.headers
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


def test_static_files_are_served(empty_dir: Path) -> None:
    r = TestClient(create_app(empty_dir)).get("/static/origen.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]


def test_no_inline_script_or_style_blocks() -> None:
    for page in (WEB / "templates").rglob("*.html"):
        html = page.read_text()
        assert "<style" not in html, page
        for tag in re.findall(r"<script\b[^>]*>", html):
            assert "src=" in tag, f"inline script in {page}"


def test_access_log_never_has_the_query(empty_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(create_app(empty_dir))
    with caplog.at_level(logging.INFO, logger="origen.access"):
        client.get("/healthz?lat=-31.23&lon=-64.32&birth=1980-01-01")
    lines = [r.getMessage() for r in caplog.records if r.name == "origen.access"]
    assert lines and lines[0].startswith("GET /healthz 503")
    assert not any("lat" in line or "1980" in line or "?" in line for line in lines)


def test_responses_are_deterministic(empty_dir: Path) -> None:
    client = TestClient(create_app(empty_dir))
    assert client.get("/healthz").content == client.get("/healthz").content


def test_head_works_for_uptime_checks(empty_dir: Path) -> None:
    client = TestClient(create_app(empty_dir))
    assert client.head("/").status_code == 200
    assert client.head("/healthz").status_code == 503


def test_page_defaults_to_unquillo_and_takes_any_place(empty_dir: Path) -> None:
    client = TestClient(create_app(empty_dir))
    page = client.get("/").text
    assert 'data-lat="-31.23"' in page and 'data-tz="UTC"' in page and "Unquillo" in page
    assert "tz=America/Argentina/Cordoba" in page
    page = client.get("/?lat=51.48&lon=0&elev_m=46&tz=Europe/London").text
    assert 'data-lat="51.48"' in page and 'data-tz="Europe/London"' in page
    for credit in ("JPL DE440s", "ESA Hipparcos", "IAU WGSN"):
        assert credit in page
    # Scripts and styles come from this origin only: no third party is loaded.
    for url in re.findall(r'(?:src|href)="(http[^"]*)"', page):
        assert url.startswith("http://testserver/static/") or url.startswith("https://github.com/")


def test_page_refuses_bad_places(empty_dir: Path) -> None:
    client = TestClient(create_app(empty_dir))
    assert client.get("/?lat=10").status_code == 422
    assert client.get("/?lat=10&lon=200").status_code == 422
    r = client.get("/?tz=<script>")
    assert r.status_code == 422 and r.json()["param"] == "tz"


def test_the_chart_script_draws_from_origen_only() -> None:
    js = (WEB / "static" / "sky.js").read_text()
    assert "/v1/sky" in js and "/v1/stars" in js
    assert "http://" not in js.replace('"http://www.w3.org/2000/svg"', "") and "https://" not in js
