"""Apparent V magnitudes (spec §5.3).

Mercury to Neptune: Skyfield's `planetary_magnitude`, Mallama and Hilton, "Computing
apparent planetary magnitudes for The Astronomical Almanac" (2018). It gives NaN where
its formula has no data (Saturn beyond a 6.5° phase angle, Neptune before 2000 beyond
1.9°); origen reports those as null.

The Sun, the Moon and Pluto: the formulas JPL Horizons uses for its `APmag` column, so
origen's values can be checked against Horizons.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from skyfield.magnitudelib import planetary_magnitude

Array = NDArray[np.float64]

PARSEC_AU = 206_264.806_247_096_36  # 1 pc in au: 648000/π

# The Sun: APmag = M - 5 + 5 log10(d / 1 pc), with M = 4.83 (Horizons' column note).
SUN_ABSOLUTE_V = 4.83

# The Moon: Allen, Astrophysical Quantities (3rd ed., 1973, §66), the form Horizons uses:
# V = V(1,0) + 5 log10(r Δ) + 0.026 |α| + 4.0e-9 α⁴, α the phase angle in degrees, r and Δ
# in au. Horizons' output fits V(1,0) = +0.23 at every phase (its header lists +0.21), so
# origen uses +0.23. Like Horizons, it leaves out the opposition surge (Horizons' note: about
# 0.12 too faint within a day of full Moon).
MOON_V10 = 0.23

# Pluto, with Charon: V = H + 5 log10(r Δ) + β α, H = -1.00 and β = 0.041 mag/degree,
# which reproduce Horizons' APmag for Pluto (999) to 0.001 (tests/fixtures/horizons.json).
PLUTO_H = -1.00
PLUTO_BETA = 0.041


def sun(distance_au: Array) -> Array:
    return SUN_ABSOLUTE_V - 5.0 + 5.0 * np.log10(distance_au / PARSEC_AU)


def moon(r_au: Array, delta_au: Array, phase_deg: Array) -> Array:
    a = np.abs(phase_deg)
    return MOON_V10 + 5.0 * np.log10(r_au * delta_au) + 0.026 * a + 4.0e-9 * a**4


def pluto(r_au: Array, delta_au: Array, phase_deg: Array) -> Array:
    return PLUTO_H + 5.0 * np.log10(r_au * delta_au) + PLUTO_BETA * phase_deg


def planet(astrometric: Any) -> Array:
    with np.errstate(invalid="ignore"):
        return np.asarray(planetary_magnitude(astrometric), dtype=np.float64)
