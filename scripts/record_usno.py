"""Record US Naval Observatory tables as test fixtures (spec §13). Run by hand only.

    uv run python scripts/record_usno.py

Writes tests/fixtures/usno.json. Tests never touch the network: they read that file.

- Sun and Moon rise, set and upper transit, and civil twilight: the "one day" JSON API.
- Nautical and astronomical twilight: the yearly twilight tables (text), the given days.
- Moon phases and the equinoxes and solstices: the phases and seasons JSON APIs.

Every time is UT, rounded by USNO to the minute.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://aa.usno.navy.mil"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "usno.json"

PLACES = {
    "unquillo": {"lat": -31.23, "lon": -64.32, "elev_m": 700},
    "madrid": {"lat": 40.4168, "lon": -3.7038, "elev_m": 657},
    "longyearbyen": {"lat": 78.2232, "lon": 15.6267, "elev_m": 10},
}
DAYS = ["2025-03-23", "2025-06-21", "2025-12-21", "2026-11-16"]
PHASES_FROM = ["2025-01-01", "2026-11-16"]
SEASON_YEARS = [1900, 2026, 2100]

ONE_DAY = {
    "Rise": "rise",
    "Set": "set",
    "Upper Transit": "transit",
    "Begin Civil Twilight": "civil_dawn",
    "End Civil Twilight": "civil_dusk",
}
PHASE = {
    "New Moon": "new",
    "First Quarter": "first_quarter",
    "Full Moon": "full",
    "Last Quarter": "last_quarter",
}
SEASON = {3: "march_equinox", 6: "june_solstice", 9: "september_equinox", 12: "december_solstice"}


def get(path: str, params: dict[str, object]) -> str:
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "origen-fixtures/1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text: str = resp.read().decode()
    time.sleep(0.5)
    return text


def stamp(date: str, hhmm: str) -> str:
    return f"{date}T{hhmm[:2]}:{hhmm[-2:]}:00Z"


def one_day(place: dict[str, float], date: str) -> list[dict[str, str]]:
    data = json.loads(
        get(
            "/api/rstt/oneday",
            {
                "date": date,
                "coords": f"{place['lat']},{place['lon']}",
                "tz": 0,
            },
        )
    )["properties"]["data"]
    out = []
    for body, key in (("sun", "sundata"), ("moon", "moondata")):
        for e in data.get(key, []):
            if e["phen"] in ONE_DAY:
                out.append({"body": body, "kind": ONE_DAY[e["phen"]], "at": stamp(date, e["time"])})
    return out


def twilight_table(place: dict[str, float], year: int, task: int) -> list[str]:
    """The lines of USNO's yearly table (task 3 nautical, 4 astronomical), in UT."""
    html = get(
        "/calculated/rstt/year",
        {
            "ID": "AA",
            "year": year,
            "task": task,
            "lat": place["lat"],
            "lon": place["lon"],
            "label": "",
            "tz": "0.00",
            "tz_sign": "-1",
            "submit": "Get Data",
        },
    )
    pre = html.split("<pre", 1)[1].split("</pre>", 1)[0]
    return pre.splitlines()


def twilights(lines: list[str], date: str, name: str) -> list[dict[str, str]]:
    month, day = int(date[5:7]), int(date[8:10])
    begin, end = 4 + 11 * (month - 1), 9 + 11 * (month - 1)
    out = []
    for line in lines:
        if not re.match(rf"^{day:02d}\s", line):
            continue
        for col, kind in ((begin, "dawn"), (end, "dusk")):
            cell = line[col : col + 4]
            if cell.isdigit():
                out.append({"body": "sun", "kind": f"{name}_{kind}", "at": stamp(date, cell)})
    return out


def main() -> int:
    events = []
    for name, place in PLACES.items():
        tables = {
            (year, task): twilight_table(place, year, task)
            for year in sorted({int(d[:4]) for d in DAYS})
            for task in (3, 4)
        }
        for date in DAYS:
            print(name, date, flush=True)
            found = one_day(place, date)
            year = int(date[:4])
            found += twilights(tables[(year, 3)], date, "nautical")
            found += twilights(tables[(year, 4)], date, "astronomical")
            events.append({"place": name, "date": date, "events": found})
    phases = []
    for date in PHASES_FROM:
        data = json.loads(get("/api/moon/phases/date", {"date": date, "nump": 8}))
        phases.append(
            {
                "from": f"{date}T00:00:00Z",
                "phases": [
                    {
                        "phase": PHASE[p["phase"]],
                        "at": f"{p['year']:04d}-{p['month']:02d}-{p['day']:02d}T{p['time']}:00Z",
                    }
                    for p in data["phasedata"]
                ],
            }
        )
    seasons = {}
    for year in SEASON_YEARS:
        data = json.loads(get("/api/seasons", {"year": year}))
        seasons[str(year)] = {
            SEASON[d["month"]]: f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}T{d['time']}:00Z"
            for d in data["data"]
            if d["phenom"] in ("Equinox", "Solstice")
        }
    doc = {
        "source": "US Naval Observatory, Astronomical Applications (aa.usno.navy.mil)",
        "recorded": datetime.now(UTC).strftime("%Y-%m-%d"),
        "settings": "UT (tz=0); times rounded to the minute by USNO; sea-level horizon",
        "places": PLACES,
        "days": events,
        "moon_phases": phases,
        "seasons": seasons,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
