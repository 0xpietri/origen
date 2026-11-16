"""The star catalogue and the rotation that places it (spec §6, §13)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from skyfield.api import Star

from origen.sky.engine import Observer, Sky
from origen.sky.stars import iau_names

from .conftest import REAL_DATA, needs_data

ARCSEC = 1 / 3600

# J2000 ICRS places (SIMBAD, from Hipparcos), to compare with origen's propagation.
KNOWN = {
    32349: ("Sirius", 101.287155, -16.716116, -1.44),
    30438: ("Canopus", 95.987958, -52.695661, -0.62),
    71683: ("Rigil Kentaurus", 219.902066, -60.833975, -0.01),
    60718: ("Acrux", 186.649563, -63.099093, 0.77),
}


@needs_data
def test_catalogue(client: TestClient) -> None:
    r = client.get("/v1/stars")
    assert r.status_code == 200
    body = r.json()
    s = body["stars"]
    assert 1500 < body["count"] == len(s["hip"]) < 1700
    assert all(len(col) == body["count"] for col in s.values())
    assert s["hip"] == sorted(s["hip"])
    assert max(s["vmag"]) <= 5.0
    assert 250 < sum(n is not None for n in s["name"]) < 350
    for hip, (name, ra, dec, vmag) in KNOWN.items():
        i = s["hip"].index(hip)
        assert s["name"][i] == name
        assert abs(s["ra_deg"][i] - ra) * math.cos(math.radians(dec)) <= ARCSEC
        assert abs(s["dec_deg"][i] - dec) <= ARCSEC
        assert s["vmag"][i] == vmag
    assert s["bv"][s["hip"].index(32349)] == 0.009


@needs_data
def test_stars_are_cached_by_etag(client: TestClient) -> None:
    first = client.get("/v1/stars")
    etag = first.headers["etag"]
    assert etag.startswith('"') and first.headers["cache-control"] == "public, max-age=86400"
    again = client.get("/v1/stars", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    assert again.headers["etag"] == etag
    assert client.get("/v1/stars", headers={"If-None-Match": '"other"'}).status_code == 200


@needs_data
def test_names_file_parses() -> None:
    names = iau_names(REAL_DATA / "stars/IAU-CSN.txt")
    assert names[32349] == "Sirius" and names[87937] == "Barnard's Star"
    assert names[70890] == "Proxima Centauri"


@needs_data
@pytest.mark.parametrize(
    ("lat", "lon", "at"),
    [(-31.23, -64.32, "2026-11-16T03:00:00Z"), (78.2232, 15.6267, "2025-01-15T00:00:00Z")],
)
def test_rotation_places_stars_like_skyfield(
    lat: float, lon: float, at: str, client: TestClient, sky: Sky
) -> None:
    """stars_rotation × the J2000 vector agrees with Skyfield's apparent alt/az within 25″
    (it leaves out aberration, refraction-free on both sides)."""
    r = client.get("/v1/sky", params={"lat": lat, "lon": lon, "from": at, "hours": 1})
    m = np.array(r.json()["stars_rotation"][0]).reshape(3, 3)
    stars = client.get("/v1/stars").json()["stars"]
    y, mo, d = (int(x) for x in at[:10].split("-"))
    t = sky.ts.utc(y, mo, d, int(at[11:13]), int(at[14:16]))
    observer = sky.earth + sky.topos(Observer(lat, lon, 0))
    for hip in KNOWN:
        i = stars["hip"].index(hip)
        ra, dec = math.radians(stars["ra_deg"][i]), math.radians(stars["dec_deg"][i])
        e, n, u = m @ np.array(
            [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
        )
        star = Star(ra_hours=stars["ra_deg"][i] / 15, dec_degrees=stars["dec_deg"][i])
        alt, az, _ = observer.at(t).observe(star).apparent().altaz()
        ours = np.array([e, n, u])
        theirs = np.array(
            [
                math.cos(alt.radians) * math.sin(az.radians),
                math.cos(alt.radians) * math.cos(az.radians),
                math.sin(alt.radians),
            ]
        )
        separation = math.degrees(math.acos(min(1.0, float(ours @ theirs / np.linalg.norm(ours)))))
        assert separation <= 25 * ARCSEC, hip
