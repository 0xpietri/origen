"""The /v1 endpoints: /v1/sky, /v1/stars, /v1/seasons (spec §5 to §7)."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Query, Request, Response

from origen import jsonout as j
from origen.problems import Problem
from origen.sky import events as sky_events
from origen.sky import phases, positions
from origen.sky import stars as sky_stars
from origen.sky.engine import (
    END_INSTANT,
    FIRST_INSTANT,
    FIRST_YEAR,
    LAST_YEAR,
    Observer,
    Sky,
    engine_block,
)
from origen.sky.frames import icrs_to_enu

MAX_SAMPLES = 2017
INSTANT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?Z$")
INSTANT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
STARS_CACHE = "public, max-age=86400"


def iso(dt: datetime) -> str:
    return dt.strftime(INSTANT_FORMAT)


def parse_instant(text: str, param: str) -> datetime:
    m = INSTANT.match(text)
    if not m:
        raise Problem(422, f"{param} must be an instant in UTC like 2026-11-16T01:00:00Z", param)
    try:
        y, mo, d, h, mi = (int(m.group(i)) for i in range(1, 6))
        return datetime(y, mo, d, h, mi, int(m.group(6) or 0), tzinfo=UTC)
    except ValueError:
        raise Problem(422, f"{param} is not a valid date and time", param) from None


def floor_to_step(now: datetime, step_min: int) -> datetime:
    """Now, floored so its minute of the day is a multiple of `step_min`."""
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes = (now.hour * 60 + now.minute) // step_min * step_min
    return day + timedelta(minutes=minutes)


class Service:
    """The loaded sky and the star catalogue, with the responses built from them."""

    def __init__(self, sky: Sky, catalogue: sky_stars.Catalogue) -> None:
        self.sky = sky
        self.catalogue = catalogue
        self.stars_body = j.dumps(self._stars())
        self.stars_etag = '"' + hashlib.sha256(self.stars_body).hexdigest()[:32] + '"'

    # /v1/stars ---------------------------------------------------------------------------

    def _stars(self) -> dict[str, Any]:
        c = self.catalogue
        return {
            "schema": "origen.stars.v1",
            "engine": engine_block(),
            "epoch": "J2000",
            "frame": "ICRS",
            "max_vmag": sky_stars.MAX_VMAG,
            "count": len(c),
            "stars": {
                "hip": c.hip,
                "ra_deg": j.degrees_0_360(c.ra_deg),
                "dec_deg": j.numbers(c.dec_deg, j.ANGLE),
                "vmag": j.numbers(c.vmag, j.MAGNITUDE),
                "bv": [None if b is None else j.number(b, 3) for b in c.bv],
                "name": c.name,
            },
        }

    # /v1/seasons -------------------------------------------------------------------------

    def seasons(self, year: int) -> dict[str, Any]:
        with self.sky.lock:
            found = phases.seasons(self.sky, year)
            ts = self.sky.ts
            instants = {k: ts.tt_jd(tt).utc_strftime(INSTANT_FORMAT) for k, tt in found.items()}
        return {
            "schema": "origen.seasons.v1",
            "engine": engine_block(),
            "year": year,
            **{k: instants[k] for k in phases.SEASONS},
        }

    # /v1/sky -----------------------------------------------------------------------------

    def sky_at(self, observer: Observer, start: datetime, hours: int, step_min: int) -> Any:
        count = hours * 60 // step_min + 1
        times = [start + timedelta(minutes=k * step_min) for k in range(count)]
        end = start + timedelta(hours=hours)
        sky = self.sky
        with sky.lock:
            ts = sky.ts
            minutes = start.minute + np.arange(count) * step_min
            t = ts.utc(start.year, start.month, start.day, start.hour, minutes, start.second)
            t0 = ts.from_datetime(start)
            t1 = ts.from_datetime(end)
            topos = sky.topos(observer)
            enu = icrs_to_enu(topos, t)
            cols = positions.bodies(sky, topos, t, enu)
            phase = phases.moon_phase_deg(sky, t)
            upcoming = phases.next_phases(sky, t0)
            found = [e for e in sky_events.events(sky, topos, t0, t1) if t0.tt <= e["tt"] <= t1.tt]
            at = ts.tt_jd(np.array([e["tt"] for e in found] + [p[1] for p in upcoming]))
            stamps = list(np.atleast_1d(at.utc_strftime(INSTANT_FORMAT)))
        event_stamps, phase_stamps = stamps[: len(found)], stamps[len(found) :]
        return {
            "schema": "origen.sky.v1",
            "engine": engine_block(),
            "observer": {
                "lat_deg": observer.lat_deg,
                "lon_deg": observer.lon_deg,
                "elev_m": observer.elev_m,
            },
            "from": iso(start),
            "step_min": step_min,
            "count": count,
            "times": [iso(x) for x in times],
            "bodies": {name: self._body(name, c) for name, c in cols.items()},
            "moon_phase": {
                "phase_deg": j.degrees_0_360(phase),
                "next": [
                    {"phase": name, "at": stamp}
                    for (name, _), stamp in zip(upcoming, phase_stamps, strict=True)
                ],
            },
            "events": [self._event(e, s) for e, s in zip(found, event_stamps, strict=True)],
            "stars_rotation": j.matrices(enu),
        }

    @staticmethod
    def _body(name: str, c: dict[str, np.ndarray]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "alt_deg": j.numbers(c["alt_deg"], j.ANGLE),
            "az_deg": j.degrees_0_360(c["az_deg"]),
            "distance_km": j.kilometres(c["distance_km"]),
            "magnitude": j.numbers(c["magnitude"], j.MAGNITUDE),
            "ecl_lon_deg": j.degrees_0_360(c["ecl_lon_deg"]),
            "ecl_lat_deg": j.numbers(c["ecl_lat_deg"], j.ANGLE),
            "ecl_lon_rate_deg_day": j.numbers(c["ecl_lon_rate_deg_day"], j.RATE),
        }
        if name != "sun":
            out["illuminated_fraction"] = j.numbers(c["illuminated_fraction"], j.FRACTION)
            out["light_dir"] = j.vectors(c["light_dir"])
        if name == "saturn":
            out["ring_tilt_deg"] = j.numbers(c["ring_tilt_deg"], j.ANGLE)
            out["ring_pole"] = j.vectors(c["ring_pole"])
        return out

    @staticmethod
    def _event(e: dict[str, Any], stamp: str) -> dict[str, Any]:
        out: dict[str, Any] = {"body": e["body"], "kind": e["kind"], "at": stamp}
        if "az_deg" in e:
            out["az_deg"] = j.degrees_0_360([e["az_deg"]])[0]
        else:
            out["alt_deg"] = j.number(e["alt_deg"], j.ANGLE)
        return out


def router(get_service: Any) -> APIRouter:
    """The /v1 routes. `get_service()` returns the Service, or raises a 503 Problem."""
    r = APIRouter(prefix="/v1")

    @r.get("/sky")
    def sky(
        lat: Annotated[float, Query(ge=-90, le=90)],
        lon: Annotated[float, Query(ge=-180, le=180)],
        elev_m: Annotated[float, Query(ge=-500, le=9000)] = 0,
        from_: Annotated[str | None, Query(alias="from")] = None,
        hours: Annotated[int, Query(ge=1, le=168)] = 48,
        step_min: Annotated[int, Query(ge=1, le=60)] = 10,
    ) -> Response:
        service = get_service()
        count = hours * 60 // step_min + 1
        if count > MAX_SAMPLES:
            raise Problem(
                422,
                f"hours={hours} with step_min={step_min} gives {count} samples; "
                f"at most {MAX_SAMPLES} (for 168 hours, step_min of 5 or more)",
                "step_min",
            )
        if from_ is None:
            start = floor_to_step(datetime.now(UTC), step_min)
        else:
            start = parse_instant(from_, "from")
        if start < FIRST_INSTANT or start + timedelta(hours=hours) > END_INSTANT:
            raise Problem(
                422,
                f"the window must lie between {iso(FIRST_INSTANT)} and {iso(END_INSTANT)}, "
                "the range of the ephemeris",
                "from",
            )
        observer = Observer(lat_deg=lat, lon_deg=lon, elev_m=elev_m)
        return j.JSON(service.sky_at(observer, start, hours, step_min))

    @r.get("/stars")
    def stars(request: Request) -> Response:
        service = get_service()
        headers = {"ETag": service.stars_etag, "Cache-Control": STARS_CACHE}
        match = request.headers.get("if-none-match", "")
        if service.stars_etag in [m.strip() for m in match.split(",")] or match.strip() == "*":
            return Response(status_code=304, headers=headers)
        return Response(service.stars_body, media_type="application/json", headers=headers)

    @r.get("/seasons")
    def seasons(year: Annotated[int, Query(ge=FIRST_YEAR, le=LAST_YEAR)]) -> Response:
        return j.JSON(get_service().seasons(year), headers={"Cache-Control": STARS_CACHE})

    return r
