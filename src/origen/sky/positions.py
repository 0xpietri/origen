"""Where every body is, sample by sample (spec §5.2, §5.3)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from skyfield.framelib import ecliptic_frame

from origen.sky import magnitudes, saturn
from origen.sky.engine import Sky
from origen.sky.frames import rotate, unit

Array = NDArray[np.float64]


def bodies(sky: Sky, topos: Any, t: Any, enu: Array) -> dict[str, dict[str, Array]]:
    """Per body, column arrays over the instants `t` (unrounded floats).

    `alt_deg`/`az_deg`: topocentric apparent (light time, aberration, deflection,
    precession and nutation of date), without refraction. `distance_km`: from the
    observer, at light time. `ecl_*`: apparent geocentric ecliptic and equinox of date.
    """
    observer_at = (sky.earth + topos).at(t)
    earth_at = sky.earth.at(t)
    out: dict[str, dict[str, Array]] = {}
    for key, target in sky.targets.items():
        astrometric = observer_at.observe(target)
        apparent = astrometric.apparent()
        alt, az, _ = apparent.altaz()
        geocentric = earth_at.observe(target).apparent()
        ecl_lat, ecl_lon, _, _, lon_rate, _ = geocentric.frame_latlon_and_rates(ecliptic_frame)
        delta_au = astrometric.distance().au
        cols: dict[str, Array] = {
            "alt_deg": alt.degrees,
            "az_deg": az.degrees % 360.0,
            "distance_km": astrometric.distance().km,
        }
        if key == "sun":
            cols["magnitude"] = magnitudes.sun(delta_au)
        else:
            # The body's barycentric position when the light left it, and the Sun's then.
            body_bcrs = observer_at.position.au + astrometric.position.au
            t_emit = sky.ts.tt_jd(t.tt - astrometric.light_time)
            to_sun = sky.sun.at(t_emit).position.au - body_bcrs
            r_au = np.linalg.norm(to_sun, axis=0)
            phase_deg = apparent.phase_angle(sky.sun).degrees
            if key == "moon":
                cols["magnitude"] = magnitudes.moon(r_au, delta_au, phase_deg)
            elif key == "pluto":
                cols["magnitude"] = magnitudes.pluto(r_au, delta_au, phase_deg)
            else:
                cols["magnitude"] = magnitudes.planet(astrometric)
        cols["ecl_lon_deg"] = ecl_lon.degrees % 360.0
        cols["ecl_lat_deg"] = ecl_lat.degrees
        cols["ecl_lon_rate_deg_day"] = lon_rate.degrees.per_day
        if key != "sun":
            cols["illuminated_fraction"] = apparent.fraction_illuminated(sky.sun)
            cols["light_dir"] = unit(rotate(enu, to_sun))
        if key == "saturn":
            pole = saturn.pole_icrs(t)
            cols["ring_tilt_deg"] = saturn.ring_tilt_deg(pole, astrometric.position.au)
            cols["ring_pole"] = unit(rotate(enu, pole))
        out[key] = cols
    return out
