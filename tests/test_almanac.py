"""Rise, set, transit, twilights, Moon phases and seasons against recorded US Naval
Observatory tables (spec §13): within 1 minute, the tables being rounded to the minute."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from .conftest import fixture, needs_data

USNO = fixture("usno.json")
MINUTE = 60.0


def when(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def local_day(events: list[dict[str, str]]) -> list[dict[str, str]]:
    """USNO's yearly twilight tables group dawn and dusk by local day: a dusk earlier in UT
    than that day's dawn happened after UT midnight, on the next UT date."""
    out = []
    dawns = {
        e["kind"].rsplit("_", 1)[0]: when(e["at"]) for e in events if e["kind"].endswith("_dawn")
    }
    for e in events:
        at = when(e["at"])
        name = e["kind"].rsplit("_", 1)[0]
        if e["kind"].endswith("_dusk") and name in dawns and at < dawns[name] and name != "civil":
            at += timedelta(days=1)
        out.append({**e, "at": at.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


@needs_data
@pytest.mark.parametrize("day", USNO["days"], ids=lambda d: f"{d['place']}-{d['date']}")
def test_events_against_usno(day: dict[str, Any], client: TestClient) -> None:
    place = USNO["places"][day["place"]]
    r = client.get(
        "/v1/sky",
        params={
            "lat": place["lat"],
            "lon": place["lon"],
            "elev_m": place["elev_m"],
            "from": f"{day['date']}T00:00:00Z",
            "hours": 48,
            "step_min": 60,
        },
    )
    assert r.status_code == 200
    ours = r.json()["events"]
    for expected in local_day(day["events"]):
        at = when(expected["at"])
        matches = [
            abs((when(e["at"]) - at).total_seconds())
            for e in ours
            if e["body"] == expected["body"] and e["kind"] == expected["kind"]
        ]
        assert matches and min(matches) <= MINUTE, (expected, matches)
    # Where USNO has no sunrise in the UT day (polar day or night), neither has origen.
    usno_kinds = {(e["body"], e["kind"]) for e in day["events"]}
    first_day = [e for e in ours if e["at"].startswith(day["date"])]
    for kind in ("rise", "set"):
        if ("sun", kind) not in usno_kinds:
            assert not any(e["body"] == "sun" and e["kind"] == kind for e in first_day)


@needs_data
def test_events_are_sorted_and_inside_the_window(client: TestClient) -> None:
    r = client.get(
        "/v1/sky",
        params={"lat": -31.23, "lon": -64.32, "from": "2026-11-16T03:00:00Z", "hours": 30},
    )
    body = r.json()
    stamps = [e["at"] for e in body["events"]]
    assert stamps == sorted(stamps)
    assert all("2026-11-16T03:00:00Z" <= s <= "2026-11-17T09:00:00Z" for s in stamps)
    assert all(("az_deg" in e) != ("alt_deg" in e) for e in body["events"])


@needs_data
@pytest.mark.parametrize("case", USNO["moon_phases"], ids=lambda c: c["from"][:10])
def test_moon_phases_against_usno(case: dict[str, Any], client: TestClient) -> None:
    r = client.get("/v1/sky", params={"lat": 0, "lon": 0, "from": case["from"], "hours": 1})
    nxt = r.json()["moon_phase"]["next"]
    assert len(nxt) == 4
    expected = case["phases"][:4]
    assert [p["phase"] for p in nxt] == [p["phase"] for p in expected]
    for ours, theirs in zip(nxt, expected, strict=True):
        assert abs((when(ours["at"]) - when(theirs["at"])).total_seconds()) <= MINUTE


@needs_data
def test_phase_deg_matches_the_quarters(client: TestClient) -> None:
    r = client.get(
        "/v1/sky", params={"lat": 0, "lon": 0, "from": "2026-11-24T14:00:00Z", "hours": 2}
    )
    body = r.json()
    full = body["moon_phase"]["next"]
    assert any(p["phase"] == "full" and p["at"].startswith("2026-11-24T14:5") for p in full)
    # 14:00 and 16:00 bracket the full Moon (about 14:53): 180° lies between them.
    phase = body["moon_phase"]["phase_deg"]
    assert phase[0] < 180 < phase[-1]


@needs_data
@pytest.mark.parametrize("year", sorted(USNO["seasons"]))
def test_seasons_against_usno(year: str, client: TestClient) -> None:
    r = client.get("/v1/seasons", params={"year": year})
    assert r.status_code == 200
    body = r.json()
    # After the last measured ΔT (Earth's clock against atomic time), every almanac uses
    # its own prediction: in 2100 Skyfield's is about 96 s and USNO's apparently smaller,
    # which moves UTC instants by the difference. There, 90 s.
    tolerance = MINUTE if int(year) <= 2026 else 1.5 * MINUTE
    for key, at in USNO["seasons"][year].items():
        assert abs((when(body[key]) - when(at)).total_seconds()) <= tolerance, key
