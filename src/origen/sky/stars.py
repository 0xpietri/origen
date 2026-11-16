"""The bright-star catalogue: Hipparcos stars down to V 5.0 at J2000, with IAU names (spec §6).

Hipparcos itself is read by Skyfield's loader (`skyfield.data.hipparcos`) and its proper
motions carried from the catalogue epoch (J1991.25) to J2000 by Skyfield's `Star`. That
loader keeps no colour, so the B-V field is read straight from the same lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from skyfield.api import Star
from skyfield.data import hipparcos
from skyfield.positionlib import Barycentric

from origen.sky.engine import Sky

MAX_VMAG = 5.0
J2000_TT = 2451545.0
BV_FIELD = 37  # hip_main.dat field H37, B-V colour index (ESA 1997, vol. 1, §2.1)


@dataclass(frozen=True)
class Catalogue:
    hip: list[int]
    ra_deg: list[float]
    dec_deg: list[float]
    vmag: list[float]
    bv: list[float | None]
    name: list[str | None]

    def __len__(self) -> int:
        return len(self.hip)


def iau_names(path: Path) -> dict[int, str]:
    """HIP number -> proper name (with diacritics), from the WGSN's IAU-CSN.txt."""
    names: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line[0] in "#$":
            continue
        tokens = line.split()
        # From the right: ... mag bnd HIP HD RA Dec Date [Notes]; the date is the anchor.
        date_at = max(i for i, tok in enumerate(tokens) if len(tok) == 10 and tok[4] == "-")
        hip = tokens[date_at - 4]
        if hip.isdigit():
            names.setdefault(int(hip), line[18:36].strip())
    return names


def _bv(path: Path, wanted: set[int]) -> dict[int, float]:
    out: dict[int, float] = {}
    with path.open(encoding="ascii") as f:
        for line in f:
            fields = line.split("|")
            hip = int(fields[1])
            if hip in wanted and fields[BV_FIELD].strip():
                out[hip] = float(fields[BV_FIELD])
    return out


def load(sky: Sky, data_dir: Path) -> Catalogue:
    hip_path = data_dir / "stars" / "hip_main.dat"
    with hip_path.open("rb") as f:
        df = hipparcos.load_dataframe(f)
    df = df[(df["magnitude"] <= MAX_VMAG) & df["ra_degrees"].notnull()].sort_index()
    star = Star.from_dataframe(df)
    # Seen from the solar-system barycentre at J2000: the catalogue place at epoch J2000.
    ssb = Barycentric(np.zeros(3), t=sky.ts.tt_jd(J2000_TT))
    ra, dec, _ = ssb.observe(star).radec()
    hips = [int(h) for h in df.index]
    bv = _bv(hip_path, set(hips))
    names = iau_names(data_dir / "stars" / "IAU-CSN.txt")
    vmag = df["magnitude"].to_numpy(dtype=np.float64)
    return Catalogue(
        hip=hips,
        ra_deg=[float(x) for x in np.asarray(ra._degrees) % 360.0],
        dec_deg=[float(x) for x in np.asarray(dec.degrees)],
        vmag=[float(x) for x in vmag],
        bv=[bv.get(h) for h in hips],
        name=[names.get(h) for h in hips],
    )


def unit_vectors(catalogue: Catalogue) -> np.ndarray:
    """ICRS unit vectors (3, n) of the catalogue's J2000 places."""
    ra = np.radians(catalogue.ra_deg)
    dec = np.radians(catalogue.dec_deg)
    return np.stack((np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)))
