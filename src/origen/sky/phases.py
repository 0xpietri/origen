"""The Moon's phase and the dates of the seasons (spec §5.3, §7)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from skyfield import almanac
from skyfield.searchlib import find_discrete

from origen.sky.engine import Sky

PHASES = ("new", "first_quarter", "full", "last_quarter")
SEASONS = ("march_equinox", "june_solstice", "september_equinox", "december_solstice")

# Four quarter phases always fall within 31 days of any instant (the longest gap between
# two of them is under 8 days).
NEXT_PHASES_DAYS = 31.0


def moon_phase_deg(sky: Sky, t: Any) -> NDArray[np.float64]:
    """The Moon's minus the Sun's apparent geocentric ecliptic longitude of date, 0 to 360."""
    return np.asarray(almanac.moon_phase(sky.eph, t).degrees, dtype=np.float64) % 360.0


def next_phases(sky: Sky, t0: Any) -> list[tuple[str, float]]:
    """The first new, first quarter, full and last quarter after `t0`: (phase, tt), by time."""
    t1 = sky.ts.tt_jd(min(t0.tt + NEXT_PHASES_DAYS, sky.last_jd))
    t, which = find_discrete(t0, t1, almanac.moon_phases(sky.eph))
    first: dict[int, float] = {}
    for tt, w in zip(t.tt, which, strict=True):
        first.setdefault(int(w), float(tt))
    return sorted(((PHASES[w], tt) for w, tt in first.items()), key=lambda p: p[1])


def seasons(sky: Sky, year: int) -> dict[str, float]:
    """The instants (tt) when the Sun's apparent geocentric ecliptic longitude of date
    reaches 0°, 90°, 180° and 270° in `year` (UTC)."""
    t0 = sky.ts.utc(year, 1, 1)
    t1 = sky.ts.utc(year + 1, 1, 1)
    t, which = find_discrete(t0, t1, almanac.seasons(sky.eph))
    return {SEASONS[int(w)]: float(tt) for tt, w in zip(t.tt, which, strict=True)}
