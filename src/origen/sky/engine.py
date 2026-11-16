"""The loaded ephemeris and timescale, and the bodies origen reports (spec §5.3)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skyfield.api import load, load_file, wgs84

from origen import data

# origen's name -> the DE440s target. Mars to Pluto are their system barycentres: DE440s
# has no planet centres for them, and the offset is far below the tolerances (spec §5.3).
BODIES: dict[str, str] = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars barycenter",
    "jupiter": "jupiter barycenter",
    "saturn": "saturn barycenter",
    "uranus": "uranus barycenter",
    "neptune": "neptune barycenter",
    "pluto": "pluto barycenter",
}

# DE440s covers 1849-12-26 to 2150-01-22 (spec §5.1, §7). A /v1/sky window lies between
# these two instants. The end leaves room for the four next Moon phases, always reported:
# the last new Moon DE440s holds is 2149-12-30T01:05Z, so a window may not end after
# 2149-12-30T00:00Z.
FIRST_INSTANT = datetime(1850, 1, 1, tzinfo=UTC)
END_INSTANT = datetime(2149, 12, 30, tzinfo=UTC)
FIRST_YEAR = 1850
LAST_YEAR = 2149


@dataclass(frozen=True)
class Observer:
    lat_deg: float
    lon_deg: float
    elev_m: float


class Sky:
    """DE440s and Skyfield's bundled timescale, opened once when the app starts."""

    def __init__(self, data_dir: Path) -> None:
        # Bundled ΔT, UT1 and leap seconds: nothing comes from the network (spec §3.1).
        self.ts = load.timescale(builtin=True)
        self.eph = load_file(str(data_dir / "ephemeris" / "de440s.bsp"))
        self.earth = self.eph["earth"]
        self.sun = self.eph["sun"]
        self.targets: dict[str, Any] = {k: self.eph[v] for k, v in BODIES.items()}
        # The last TDB Julian date every segment covers, less a margin for light time.
        self.last_jd = min(seg.end_jd for seg in self.eph.spk.segments) - 1.0
        # Skyfield objects are not documented as thread-safe; requests take turns.
        self.lock = threading.Lock()

    def topos(self, observer: Observer) -> Any:
        return wgs84.latlon(observer.lat_deg, observer.lon_deg, elevation_m=observer.elev_m)

    def close(self) -> None:
        self.eph.close()


def engine_block(stars: str = data.STARS) -> dict[str, str]:
    """What it takes to reproduce any answer (spec §4)."""
    import skyfield

    from origen import __version__

    return {
        "origen": __version__,
        "ephemeris": data.EPHEMERIS,
        "stars": stars,
        "skyfield": skyfield.__version__,
    }
