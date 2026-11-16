# Phase 2 report: positions (2026-11-16)

## Done
- `GET /v1/sky`: the ten bodies sampled over the window (topocentric apparent alt/az without
  refraction, distance, magnitude, apparent geocentric ecliptic longitude, latitude and longitude
  rate, illuminated fraction and `light_dir` for the Moon and planets, Saturn's `ring_tilt_deg`
  and `ring_pole`), the Moon's `phase_deg` per sample and its next four quarters, the events
  (Sun and Moon rise, set and transit; civil, nautical and astronomical dawn and dusk) and
  `stars_rotation`, one ICRS→ENU matrix per sample. Default `from`: now, floored so its minute
  of the day is a multiple of `step_min`.
- `GET /v1/stars`: 1,625 Hipparcos stars with V ≤ 5.0 (309 with an IAU name), at J2000 in ICRS.
  Skyfield's loader reads `hip_main.dat` and Skyfield's `Star` carries the proper motions from
  J1991.25 to J2000; the B-V field is read from the same lines. Built once at start-up; strong
  ETag (304 on `If-None-Match`) and `Cache-Control: public, max-age=86400`.
- `GET /v1/seasons?year=`: the four instants, named by the event.
- JSON Schemas in `schemas/` (`sky.v1`, `stars.v1`, `seasons.v1`, `error.v1`), served at
  `/schemas/<name>.json`. Errors are `application/problem+json` with the offending `param`
  (422 for bad input, 404, and 503 while the data files are missing).
- One JSON encoder and fixed rounding per field (`jsonout.py`): angles 4 decimals, vectors and
  matrices 6, distances to the km, magnitudes 2, fractions 4, rates 5, instants to the second;
  no NaN (null), no negative zero.
- The page: the motto first, a round chart of the sky right now (horizon, cardinal points,
  every star to magnitude 5 placed with `stars_rotation`, the planets, the Moon with its phase
  and the right tilt of its lit side), the table of bodies, the Sun's day and the Moon's next
  phase. Unquillo by default; `?lat=&lon=&elev_m=&tz=` and a small form for any place.
  `static/sky.js` draws from `/v1/sky` and `/v1/stars`, refreshes every 10 minutes and computes
  nothing. Credits at the bottom.
- `scripts/record_horizons.py` and `scripts/record_usno.py` recorded the fixtures in
  `tests/fixtures/` (by hand, once; tests never touch the network).

## Tests
249 tests, ruff and mypy clean. Against JPL Horizons (150 rows: Unquillo, Madrid and
Longyearbyen, 78°N; five instants in 2024-2025; the ten bodies): altitude, azimuth, RA/Dec,
distance, illuminated fraction and magnitude. Against USNO: rise, set, transit and the three
twilights for 12 place-days (polar day and night included), the Moon's quarters and the
seasons of 1900, 2026 and 2100. Saturn's B against Meeus's example 45.a (16.442°) and the
Earth's crossing of the ring plane on 2025-03-23. Stars: count, names, Sirius, Canopus, α Cen
and Acrux, and the rotation against Skyfield's alt/az within 25″. `light_dir` gives back the
illuminated fraction. Contracts: every answer validates against its schema; limits give 422.
Determinism: the same request gives the same bytes, twice and in another process.

Measured differences: position typically 0.05 to 0.4″ from Horizons; Moon distance 0.02 km;
events within 1 minute of USNO everywhere.

## Points for marcos (the spec could not be met literally; tests use the values below)
1. **Azimuth near a pole.** Skyfield's bundled timescale (required, §3.1) has no polar
   motion; Horizons applies it. At Longyearbyen that turns the horizon by up to 2″, over the
   1″ of §13. Tests allow 2.5″ in azimuth there (1″ elsewhere, where it passes). Invisible at
   any size a client draws.
2. **Magnitudes.** Skyfield's Mars leaves out its surface features (±0.06) and its Mercury fit
   beyond a 120° phase angle (a thin crescent next to the Sun) differs from Horizons by up to
   0.11. Tests allow 0.08 for Mars and 0.12 for that Mercury; 0.05 elsewhere. The Moon uses
   V(1,0) = +0.23, which reproduces Horizons exactly (its header says +0.21), and Pluto H = -1.00.
3. **Seasons in 2100.** After the last measured ΔT every almanac predicts its own; USNO and
   Skyfield end up about 30 to 70 s apart. 1900 and 2026 are within 1 minute; 2100 gets 90 s.
4. **The last days of DE440s.** `next` always has four Moon phases, so a `/v1/sky` window must
   end by 2149-12-30T00:00Z (the last new Moon DE440s holds is 2149-12-30T01:05Z). Seasons go
   to 2149 as written.
5. **pandas** is now a run-time dependency: Skyfield's Hipparcos loader needs it (decision
   14.2). Peak memory of the service in a 168-hour request: about 135 MB, under the 256 MB.
6. **Size.** 48 hours at 10 minutes is about 300 KB (105 KB gzipped), over the spec's estimate
   of 150-250 KB, mostly `stars_rotation` and `light_dir`. Compression belongs to Caddy
   (phase 3); origen itself sends it uncompressed so the bytes stay identical.
7. **The page's rise and set** are shown for the Sun and the Moon only, the bodies whose events
   `/v1/sky` carries (§5.3).

## Try it on your PC
From the repository folder, one line each:

```
git fetch ./origen-fase-2.bundle fase-2 && git checkout -f -B fase-2 FETCH_HEAD          # this phase, from the bundle
uv sync && uv run origen fetch-data                                                          # install and data (already there from phase 1)
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy          # tests, lint, types
uv run origen serve --reload                                                                 # then the next lines
xdg-open 'http://127.0.0.1:8800/?lat=-31.23&lon=-64.32&elev_m=700&tz=America/Argentina/Cordoba'
curl -s 'http://127.0.0.1:8800/v1/sky?lat=-31.23&lon=-64.32&elev_m=700&hours=2' | head -c 600
curl -s 'http://127.0.0.1:8800/v1/seasons?year=2026'
```

To record the fixtures again (network, by hand): `uv run python scripts/record_horizons.py`
and `uv run python scripts/record_usno.py`.

## Next
Phase 3, deploy, only when marcos says. Astrology after that, as its own phase.
