"""Rise, set, transit and twilights inside a window (spec §5.3)."""

from __future__ import annotations

from typing import Any

import numpy as np
from skyfield import almanac

from origen.sky.engine import Sky

# Sun's centre at these altitudes; dawn when rising through them, dusk when setting.
TWILIGHTS = (("civil", -6.0), ("nautical", -12.0), ("astronomical", -18.0))


def _altaz(observer: Any, target: Any, t: Any) -> tuple[Any, Any]:
    alt, az, _ = observer.at(t).observe(target).apparent().altaz()
    return alt.degrees, az.degrees % 360.0


def _crossings(
    sky: Sky, observer: Any, body: str, t0: Any, t1: Any, horizon: float | None
) -> list[tuple[float, str, float]]:
    """(tt, 'rise'|'set', az) for each crossing that really happens in [t0, t1]."""
    target = sky.targets[body]
    out: list[tuple[float, str, float]] = []
    for kind, find in (("rise", almanac.find_risings), ("set", almanac.find_settings)):
        t, happened = find(observer, target, t0, t1, horizon_degrees=horizon)
        t = t[happened]
        if len(t):
            _, az = _altaz(observer, target, t)
            out += [(tt, kind, a) for tt, a in zip(t.tt, az, strict=True)]
    return out


def events(sky: Sky, topos: Any, t0: Any, t1: Any) -> list[dict[str, Any]]:
    """Every event in the window, sorted by time. Instants are Skyfield TT Julian dates
    under `tt`; the caller formats them.

    Rise and set use the almanac convention, so they match published tables: the upper
    limb on a sea-level horizon with 34′ of standard refraction (Skyfield's default
    horizon: 50′ below for the Sun; for the Moon, 34′ plus its topocentric semidiameter;
    the Moon's parallax is in its topocentric position).
    """
    observer = sky.earth + topos
    found: list[dict[str, Any]] = []
    for body in ("sun", "moon"):
        for tt, kind, az in _crossings(sky, observer, body, t0, t1, None):
            found.append({"body": body, "kind": kind, "tt": tt, "az_deg": az})
        transits = almanac.find_transits(observer, sky.targets[body], t0, t1)
        if len(transits):
            alt, _ = _altaz(observer, sky.targets[body], transits)
            for tt, a in zip(transits.tt, np.atleast_1d(alt), strict=True):
                found.append({"body": body, "kind": "transit", "tt": tt, "alt_deg": a})
    for name, degrees in TWILIGHTS:
        for tt, kind, az in _crossings(sky, observer, "sun", t0, t1, degrees):
            label = f"{name}_dawn" if kind == "rise" else f"{name}_dusk"
            found.append({"body": "sun", "kind": label, "tt": tt, "az_deg": az})
    found.sort(key=lambda e: (e["tt"], e["body"], e["kind"]))
    return found
