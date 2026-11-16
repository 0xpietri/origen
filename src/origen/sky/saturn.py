"""Saturn's ring geometry (spec §5.3)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def pole_icrs(t: Any) -> Array:
    """Saturn's north pole, ICRS unit vectors (3, n).

    IAU WGCCRE 2015 (Archinal et al. 2018, Celest. Mech. Dyn. Astr. 130:22):
    α0 = 40.589 − 0.036 T, δ0 = 83.537 − 0.004 T, T in Julian centuries of TDB from J2000.
    """
    centuries = (np.atleast_1d(t.tdb) - 2451545.0) / 36525.0
    ra = np.radians(40.589 - 0.036 * centuries)
    dec = np.radians(83.537 - 0.004 * centuries)
    return np.stack((np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)))


def ring_tilt_deg(pole: Array, observer_to_saturn: Array) -> Array:
    """The ring opening angle B: the saturnicentric latitude of the observer over the ring
    plane (the equator), positive when the north face is visible."""
    toward_observer = -observer_to_saturn / np.linalg.norm(observer_to_saturn, axis=0)
    return np.degrees(np.arcsin(np.clip(np.sum(pole * toward_observer, axis=0), -1.0, 1.0)))
