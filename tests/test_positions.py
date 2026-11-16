"""Positions against recorded JPL Horizons observer tables (spec §13)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from origen.sky import saturn
from origen.sky.engine import Sky

from .conftest import fixture, needs_data

HORIZONS = fixture("horizons.json")
ARCSEC = 1 / 3600

# Polar motion (about 0.3″ in 2024-2025) is not in Skyfield's bundled timescale; Horizons
# applies it. Near a pole it turns the horizon frame by up to 0.3″ × sec(latitude), about
# 2″ at Longyearbyen (78°N), so azimuth there gets that much more room. See the phase 2
# report.
POLAR_MOTION_ROOM = {"unquillo": 0.0, "madrid": 0.0, "longyearbyen": 1.5}


def magnitude_tolerance(body: str, phase_deg: float | None) -> float:
    if body == "moon":
        return 0.1
    # Skyfield leaves out Mars's surface features (±0.06, its docs); for Mercury beyond a
    # 120° phase angle (a thin crescent next to the Sun) its Mallama-Hilton fit and
    # Horizons' differ by up to 0.11. See the phase 2 report.
    if body == "mars":
        return 0.08
    if body == "mercury" and phase_deg is not None and phase_deg > 120:
        return 0.12
    return 0.05


def sky_at(client: TestClient, place: dict[str, float], at: str) -> dict[str, Any]:
    r = client.get(
        "/v1/sky",
        params={
            **{"lat": place["lat"], "lon": place["lon"], "elev_m": place["elev_m"]},
            "from": at,
            "hours": 1,
            "step_min": 60,
        },
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


@pytest.fixture(scope="module")
def answers(client: TestClient) -> dict[tuple[str, str], dict[str, Any]]:
    out = {}
    for name, place in HORIZONS["places"].items():
        for at in sorted({row["at"] for row in HORIZONS["rows"]}):
            out[(name, at)] = sky_at(client, place, at)
    return out


def rows() -> list[dict[str, Any]]:
    return list(HORIZONS["rows"])


@needs_data
@pytest.mark.parametrize("row", rows(), ids=lambda r: f"{r['place']}-{r['body']}-{r['at'][:10]}")
def test_against_horizons(row: dict[str, Any], answers: dict[Any, Any]) -> None:
    b = answers[(row["place"], row["at"])]["bodies"][row["body"]]
    moon = row["body"] == "moon"
    angle = (2.0 if moon else 1.0) * ARCSEC
    alt = b["alt_deg"][0]
    assert abs(alt - row["alt_deg"]) <= angle
    daz = (b["az_deg"][0] - row["az_deg"] + 180) % 360 - 180
    on_sky = abs(daz) * math.cos(math.radians(row["alt_deg"]))
    assert on_sky <= angle + POLAR_MOTION_ROOM[row["place"]] * ARCSEC
    assert abs(b["distance_km"][0] - row["distance_km"]) <= (1 if moon else 10)
    if row["illuminated_fraction"] is not None:
        assert abs(b["illuminated_fraction"][0] - row["illuminated_fraction"]) <= 0.001
    if row["magnitude"] is not None and b["magnitude"][0] is not None:
        tol = magnitude_tolerance(row["body"], row["phase_angle_deg"])
        assert abs(b["magnitude"][0] - row["magnitude"]) <= tol


@needs_data
@pytest.mark.parametrize(
    "row", rows()[::7], ids=lambda r: f"{r['place']}-{r['body']}-{r['at'][:10]}"
)
def test_ra_dec_of_date_against_horizons(row: dict[str, Any], sky: Sky) -> None:
    """The same targets and timescale give Horizons' apparent RA/Dec of date."""
    from origen.sky.engine import Observer

    place = HORIZONS["places"][row["place"]]
    topos = sky.topos(Observer(place["lat"], place["lon"], place["elev_m"]))
    t = sky.ts.utc(*(int(x) for x in row["at"][:19].replace("T", "-").replace(":", "-").split("-")))
    ra, dec, _ = (
        (sky.earth + topos).at(t).observe(sky.targets[row["body"]]).apparent().radec("date")
    )
    tol = (2.0 if row["body"] == "moon" else 1.0) * ARCSEC
    dra = ((ra._degrees - row["ra_deg"] + 180) % 360 - 180) * math.cos(math.radians(row["dec_deg"]))
    assert abs(dra) <= tol
    assert abs(dec.degrees - row["dec_deg"]) <= tol


@needs_data
def test_light_dir_agrees_with_the_phase(answers: dict[Any, Any]) -> None:
    """Lighting a sphere from light_dir gives the illuminated fraction origen reports."""
    for answer in answers.values():
        for name, b in answer["bodies"].items():
            if name == "sun":
                continue
            alt, az = math.radians(b["alt_deg"][0]), math.radians(b["az_deg"][0])
            toward = np.array(
                [math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az), math.sin(alt)]
            )
            light = np.array(b["light_dir"][0])
            assert abs(np.linalg.norm(light) - 1) < 1e-5
            k = (1 + float(np.dot(light, -toward))) / 2
            assert abs(k - b["illuminated_fraction"][0]) < 0.002, name


@needs_data
def test_saturn_ring_tilt_meeus_example_45a(sky: Sky) -> None:
    """Meeus, Astronomical Algorithms (2nd ed.), example 45.a: 1992 December 16, 0h TD,
    B = 16.442°."""
    t = sky.ts.tt(1992, 12, 16)
    astrometric = sky.earth.at(t).observe(sky.targets["saturn"])
    b = saturn.ring_tilt_deg(saturn.pole_icrs(t), astrometric.position.au.reshape(3, 1))
    assert abs(float(b[0]) - 16.442) <= 0.01


@needs_data
def test_saturn_ring_plane_crossing_of_2025(client: TestClient) -> None:
    """The Earth crossed Saturn's ring plane on 2025 March 23 (B from - to +... or the
    reverse): B changes sign within that day and is tiny there."""
    r = client.get(
        "/v1/sky",
        params={"lat": 0, "lon": 0, "from": "2025-03-22T00:00:00Z", "hours": 72, "step_min": 60},
    )
    b = r.json()["bodies"]["saturn"]["ring_tilt_deg"]
    signs = np.sign(b)
    crossing = int(np.nonzero(signs[1:] != signs[:-1])[0][0])
    assert r.json()["times"][crossing].startswith("2025-03-23")
    assert all(abs(x) < 0.2 for x in b)
    poles = r.json()["bodies"]["saturn"]["ring_pole"]
    assert all(abs(np.linalg.norm(p) - 1) < 1e-5 for p in poles)
