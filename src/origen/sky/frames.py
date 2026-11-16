"""The observer's ENU frame: east, north, up (spec §3.1)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def icrs_to_enu(topos: Any, t: Any) -> Array:
    """Per instant, the 3×3 matrix taking an ICRS (J2000) vector into the observer's ENU frame.

    Precession, nutation (with frame bias) and Earth rotation, from Skyfield's own altaz
    rotation, so it agrees with Skyfield's azimuth and altitude. Shape (3, 3, n).
    """
    neu = topos.rotation_at(t)  # Skyfield's rows: north, east, up (azimuth = atan2(e, n))
    if neu.ndim == 2:
        neu = neu[:, :, None]
    return np.stack((neu[1], neu[0], neu[2]))


def rotate(matrix: Array, vectors: Array) -> Array:
    """Apply per-instant matrices (3, 3, n) to per-instant vectors (3, n)."""
    return np.einsum("ijn,jn->in", matrix, vectors)


def unit(vectors: Array) -> Array:
    return vectors / np.linalg.norm(vectors, axis=0)
