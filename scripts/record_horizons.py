"""Record JPL Horizons observer tables as test fixtures (spec §13). Run by hand only.

    uv run python scripts/record_horizons.py

Writes tests/fixtures/horizons.json. Tests never touch the network: they read that file.

For every place, body and instant it asks Horizons for the topocentric, airless,
apparent RA/Dec of date and azimuth/elevation, and the range, of the same target origen
uses (the barycentres of Mars to Pluto), and for the apparent magnitude and illuminated
fraction of the planet itself. The instants are in 2024-2025, where both Horizons and
Skyfield's bundled Earth-orientation data are measured, not predicted.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "horizons.json"

PLACES = {
    "unquillo": {"lat": -31.23, "lon": -64.32, "elev_m": 700},
    "madrid": {"lat": 40.4168, "lon": -3.7038, "elev_m": 657},
    "longyearbyen": {"lat": 78.2232, "lon": 15.6267, "elev_m": 10},
}

TIMES = [
    "2024-03-31T06:00:00Z",
    "2025-01-15T00:00:00Z",
    "2025-03-23T12:00:00Z",
    "2025-06-01T18:00:00Z",
    "2025-09-07T18:30:00Z",
]

# origen body -> (Horizons target for position and range, target for magnitude/illumination)
BODIES = {
    "sun": ("10", "10"),
    "moon": ("301", "301"),
    "mercury": ("199", "199"),
    "venus": ("299", "299"),
    "mars": ("4", "499"),
    "jupiter": ("5", "599"),
    "saturn": ("6", "699"),
    "uranus": ("7", "799"),
    "neptune": ("8", "899"),
    "pluto": ("9", "999"),
}


def jd_utc(iso: str) -> float:
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return dt.timestamp() / 86400.0 + 2440587.5


def query(command: str, place: dict[str, float], quantities: str) -> list[list[str]]:
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@399'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{place['lon']},{place['lat']},{place['elev_m'] / 1000}'",
        "TLIST_TYPE": "'JD'",
        "TIME_TYPE": "'UT'",
        "TLIST": " ".join(f"'{jd_utc(t):.6f}'" for t in TIMES),
        "QUANTITIES": f"'{quantities}'",
        "ANG_FORMAT": "'DEG'",
        "APPARENT": "'AIRLESS'",
        "REF_SYSTEM": "'ICRF'",
        "EXTRA_PREC": "'YES'",
        "CSV_FORMAT": "'YES'",
        "RANGE_UNITS": "'KM'",
        "TIME_DIGITS": "'SECONDS'",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        result = json.load(resp)["result"]
    body = result.split("$$SOE")[1].split("$$EOE")[0]
    rows = [[c.strip() for c in line.split(",")] for line in body.strip().splitlines()]
    if len(rows) != len(TIMES):
        sys.exit(f"Horizons gave {len(rows)} rows for {command}, expected {len(TIMES)}")
    time.sleep(0.5)
    return rows


def num(text: str) -> float | None:
    return None if text in ("n.a.", "") else float(text)


def main() -> int:
    records = []
    for place_name, place in PLACES.items():
        for body, (pos_target, phys_target) in BODIES.items():
            print(f"{place_name} {body}", flush=True)
            # Columns: date, solar flag, lunar flag, RA, Dec, Az, El, delta, deldot
            pos = query(pos_target, place, "2,4,20")
            # Columns: date, flags, APmag, S-brt, Illu%, r, rdot, delta, deldot, S-T-O
            phys = query(phys_target, place, "9,10,19,20,24")
            for iso, p, q in zip(TIMES, pos, phys, strict=True):
                records.append(
                    {
                        "place": place_name,
                        "body": body,
                        "at": iso,
                        "ra_deg": float(p[3]),
                        "dec_deg": float(p[4]),
                        "az_deg": float(p[5]),
                        "alt_deg": float(p[6]),
                        "distance_km": float(p[7]),
                        "magnitude": num(q[3]),
                        "illuminated_fraction": None if body == "sun" else float(q[5]) / 100,
                        "phase_angle_deg": num(q[10]),
                    }
                )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "source": "JPL Horizons API (ssd.jpl.nasa.gov/api/horizons.api), observer tables",
        "recorded": datetime.now(UTC).strftime("%Y-%m-%d"),
        "settings": "topocentric geodetic site, airless apparent, RA/Dec of date, range in km",
        "places": PLACES,
        "bodies": {b: {"position": p, "physical": q} for b, (p, q) in BODIES.items()},
        "rows": records,
    }
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{len(records)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
