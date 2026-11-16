"""One JSON encoder for every response, and the fixed rounding per field (spec §4, §5.4).

Same input, same bytes: insertion-ordered keys, compact separators, no NaN (null instead),
no negative zero, every number rounded to its field's places before encoding.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from typing import Any

import numpy as np
from fastapi.responses import Response

ANGLE = 4  # degrees: 0.36″
UNIT = 6  # unit vectors and matrices
MAGNITUDE = 2
FRACTION = 4
RATE = 5  # degrees per day


def dumps(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


class JSON(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return dumps(content)


class ProblemJSON(JSON):
    media_type = "application/problem+json"


def _clean(x: float) -> float | None:
    if math.isnan(x):
        return None
    return x + 0.0  # turns -0.0 into 0.0


def numbers(values: Iterable[float] | np.ndarray, places: int) -> list[float | None]:
    arr = np.round(np.asarray(values, dtype=np.float64), places)
    return [_clean(x) for x in arr.tolist()]


def number(value: float, places: int) -> float:
    out = _clean(round(float(value), places))
    if out is None:
        raise ValueError("NaN where a number is required")
    return out


def degrees_0_360(values: Iterable[float] | np.ndarray, places: int = ANGLE) -> list[float | None]:
    """Rounded angles in [0, 360): a value that rounds up to 360 becomes 0."""
    return [None if x is None else (0.0 if x >= 360.0 else x) for x in numbers(values, places)]


def kilometres(values: Iterable[float] | np.ndarray) -> list[int]:
    return [int(x) for x in np.rint(np.asarray(values, dtype=np.float64)).tolist()]


def vectors(columns: np.ndarray, places: int = UNIT) -> list[list[float | None]]:
    """(3, n) column vectors -> n rows of [x, y, z]."""
    return [numbers(row, places) for row in np.asarray(columns).T]


def matrices(stack: np.ndarray, places: int = UNIT) -> list[list[float | None]]:
    """(3, 3, n) per-instant matrices -> n rows of 9 numbers, row-major."""
    arr = np.asarray(stack)
    return [numbers(arr[:, :, k].reshape(9), places) for k in range(arr.shape[2])]
