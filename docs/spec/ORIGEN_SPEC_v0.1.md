# origen: specification v0.1

> Astronomy and astrology were born sisters. They will be again.

Status: draft for marcos's approval, 2026-11-16. Owner: marcos.
Everything marked **proposed** waits for his yes; open points are in section 14.
Where this spec says "decided", marcos said so in the request of 2026-11-16.

## 1. Purpose

origen (origen.pietri.dev, repository `0xpietri/origen`) is, in the long run, a
site for anyone curious about astronomy and astrology: the real sky over any
place on Earth, and later the chart of a moment and a place, computed with
serious tools and explained plainly.

From day one it is also **the only place in the pietri.dev ecosystem where the
sky is computed**. pietri.dev (the 3D world, `0xpietri/pietri.dev`),
micelio.pietri.dev and the apps that come later consume origen and compute
none of it. Showing Unquillo's sky in pietri.dev is origen's first use, not
what defines it: this spec, the README and the page speak to that curious
person, not to Unquillo.

The name plays with both ends: the origin of the universe and the personal
origin that every birth chart describes.

Decided rules:

- **No duplicated code between repositories, however small.** If something
  about the sky breaks, the fix lives only here.
- **The engine is a stateless calculator.** It receives a date, a time and a
  place and returns the result. It stores nothing, and it never logs personal
  data (section 9).
- **Users live in id.pietri.dev**, which does not exist yet. origen has no
  user tables and never stores user data (section 12).
- **Weather is not origen's.** It stays in pietri.dev, which reads Open-Meteo.
- origen never reads another project's database; it talks only over HTTP.

## 2. Scope

### 2.1 Version 1: the real sky (phases 1 to 3)

Astronomy only. It returns what pietri.dev needs to draw the real sky:

| Endpoint | Returns |
|---|---|
| `GET /v1/sky` | Samples of every body over a time window, their rise, set and twilight events, the Moon's phase, and the rotation that places the stars (section 5) |
| `GET /v1/stars` | Real Hipparcos stars down to magnitude 5, J2000, with proper names (section 6) |
| `GET /v1/seasons` | The instants of the equinoxes and solstices of a year (section 7) |
| `GET /` | A minimal page with the sky right now, as proof that everything works (section 8) |
| `GET /healthz` | `{"status": "ok", "version", "ephemeris", "stars"}` |

### 2.2 Later (not built now; this spec reserves their place)

Each one is asked for separately, with its own phase:

1. **Astrology of the sky right now**, inside `/v1/sky`, for pietri.dev's
   cards: sign, degrees, retrograde, house for that place and aspects
   (section 10.2).
2. **`POST /v1/charts`**: the birth chart (section 10.3).
3. **`POST /v1/descriptions`**: a short, deterministic, tongue-in-cheek
   description of a chart for an NPC, from Spanish templates marcos edits
   (section 11).
4. **origen's user interface**: sign in with id.pietri.dev, see one's own
   chart, its description and today's sky for one's place (section 12).

## 3. Stack

**Proposed, for marcos to confirm** (it is the one he suggested; nothing added):

- Python 3.12, `uv` with a committed lockfile, pytest, ruff (lint and format),
  mypy (strict on `src/`), like factory-panel.
- **Skyfield** with the JPL ephemeris **DE440s** for every position. NumPy
  comes with it.
- **FastAPI** + uvicorn. The page is Jinja with plain CSS and JS: no build
  step, no inline `<script>` or `<style>` blocks (CSP; inline `style=""`
  attributes are allowed).
- **Research** (dependency group `research`, never in the image and never
  imported by `src/`): Astropy, astroquery, SciPy, JupyterLab. Notebooks live
  in `research/`.
- **No database for now**: the ephemeris and the star catalogue are files.
  If one is ever needed, PostgreSQL 17 like the rest; never Redis.
- **Docker**, multi-arch (amd64 + arm64), behind Caddy on marcos's server.
  Images on GHCR tagged by commit, like the other projects. The ephemeris is
  downloaded while building the image and checked against a pinned SHA-256;
  it never enters git.
- **Later, for astrology**: an own pure module (no web, no I/O) on top of
  Skyfield's longitudes; Swiss Ephemeris (`pyswisseph`, AGPL) **only as a
  development dependency** to compare against in tests, never in the service
  or the image; GeoNames cities offline; historical time zones with
  `timezonefinder` + `zoneinfo` + a pinned `tzdata`, so no personal data
  ever goes to a third party.

### 3.1 Time and data rules

- Skyfield's timescale is built from the data bundled with the pinned
  Skyfield version (`load.timescale(builtin=True)`): ΔT, UT1 and leap seconds
  never come from the network at run time. Updating them is a dependency
  update with its own fixture check.
- All instants in and out are ISO 8601 in UTC with a `Z` (`2026-11-16T01:00:00Z`).
  Local time is a display matter of the page and the clients.
- Angles in degrees, distances in kilometres, magnitudes in V. Coordinates
  in the observer's horizontal frame are **ENU unit vectors** (east, north,
  up), so clients never guess an axis convention.

### 3.2 Repository layout (proposed)

```
src/origen/
  app.py              FastAPI app, routes, error handling
  cli.py              `origen serve`, `origen fetch-data`, `origen sky ...`
  data.py             paths, pinned checksums, loading the ephemeris and catalogue
  sky/                pure functions over Skyfield: positions, events, phases, seasons, stars
  astrology/          later: pure module (zodiac, houses, aspects, charts)
  descriptions/       later: template rendering
  web/                templates/ and static/ for the page
schemas/              JSON Schemas of every response, versioned (section 4)
data/
  ephemeris/          DE440s, downloaded, git-ignored
  stars/              the derived star catalogue and its sources (section 6, open point 14.2)
  astrology/          later: aspects and orbs, house systems (data, not code)
  descriptions/es/    later: description templates marcos edits
research/             notebooks; the app never imports them
scripts/              recording of reference fixtures (Horizons, USNO), by hand only
tests/                unit and API tests; fixtures/ holds the recorded references
docs/spec/, docs/reports/
```

## 4. Contracts

- Every response has a **JSON Schema** in `schemas/` (`sky.v1.json`,
  `stars.v1.json`, `seasons.v1.json`, `error.v1.json`), checked in tests
  against real responses. origen also serves them at `/schemas/<name>.json`.
- **Versions break only with `/v2`.** Within `/v1`, a field may be added,
  never renamed, removed or given a new meaning or unit.
- Every response carries `"schema": "origen.<name>.v1"` and an `engine`
  block: origen's version, `"ephemeris": "DE440s"`, the star catalogue's
  version and Skyfield's version. That is enough to reproduce any answer.
- **Determinism**: the same request to the same build gives byte-identical
  bodies. No generation timestamps in bodies, fixed key order, fixed rounding
  per field (section 5.4), the same JSON encoder everywhere. Tests prove it.
- Errors are `application/problem+json` (RFC 9457) with `type`, `title`,
  `status`, `detail` and the offending `param`. Out-of-range input is 422.
- pietri.dev keeps recorded origen responses (and the schema files of the
  version it was built against) as fixtures for its tests. Those are recorded
  data, not shared code.
- No authentication on `/v1` in version 1: it is public, and every request's
  work is bounded by the limits below. Rate limiting, if needed, is Caddy's
  (phase 3).

## 5. `GET /v1/sky`

### 5.1 Request

| Param | Meaning | Default | Range |
|---|---|---|---|
| `lat` | Latitude, degrees, north positive | required | −90 to 90 |
| `lon` | Longitude, degrees, east positive | required | −180 to 180 |
| `elev_m` | Height above sea level, metres | `0` | −500 to 9000 |
| `from` | First sample, UTC | now, floored to `step_min` | the ephemeris range (1850 to 2149) |
| `hours` | Window length | `48` | 1 to 168 |
| `step_min` | Minutes between samples | `10` | 1 to 60, and at most 2,017 samples |

Unquillo, the first client's place, is `lat=-31.23&lon=-64.32&elev_m=700`
(time zone `America/Argentina/Cordoba`, for display only).

The window includes both ends: `hours=48&step_min=10` gives 289 samples.

### 5.2 Response

Column-oriented, so a client interpolates between samples without
reshaping, and 48 hours stay small (estimated 150 to 250 KB, 30 to 50 KB
gzipped):

```json
{
  "schema": "origen.sky.v1",
  "engine": { "origen": "0.1.0", "ephemeris": "DE440s", "stars": "hip5-2026.11", "skyfield": "x.y" },
  "observer": { "lat_deg": -31.23, "lon_deg": -64.32, "elev_m": 700 },
  "from": "2026-11-16T00:00:00Z", "step_min": 10, "count": 289,
  "times": ["2026-11-16T00:00:00Z", "..."],
  "bodies": {
    "sun":     { "alt_deg": [], "az_deg": [], "distance_km": [], "magnitude": [],
                 "ecl_lon_deg": [], "ecl_lat_deg": [], "ecl_lon_rate_deg_day": [] },
    "moon":    { "...as above...": [], "illuminated_fraction": [], "light_dir": [[0.1, 0.2, 0.97]] },
    "mercury": {}, "venus": {}, "mars": {}, "jupiter": {},
    "saturn":  { "...as above...": [], "ring_tilt_deg": [], "ring_pole": [[0, 0, 1]] },
    "uranus": {}, "neptune": {}, "pluto": {}
  },
  "moon_phase": { "phase_deg": [], "next": [ { "phase": "full", "at": "..." } ] },
  "events": [ { "body": "sun", "kind": "rise", "at": "...", "az_deg": 112.4 } ],
  "stars_rotation": [[1, 0, 0, 0, 1, 0, 0, 0, 1]]
}
```

`ecl_*` fields are open point 14.1 (recommended in).

### 5.3 What each field means

- **Bodies**: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus,
  Neptune, Pluto. Planets are their barycentres where DE440s has no planet
  centre (Mars to Pluto); the difference is far below the tolerances.
- **`alt_deg`, `az_deg`**: topocentric apparent position (light time,
  aberration, deflection, precession and nutation of date) **without
  refraction**, so bodies and stars (whose rotation cannot include refraction)
  agree with each other. Azimuth from north through east, 0 to 360.
- **`distance_km`**: from the observer.
- **`illuminated_fraction`**: 0 to 1, for the Moon and the planets (the Sun
  has none).
- **`light_dir`**: unit ENU vector from the body towards the Sun, so a client
  lights a sphere at the body's position and gets the right phase and the
  right tilt of the terminator, as seen from that hemisphere. Moon and
  planets.
- **`magnitude`**: apparent V magnitude. Skyfield's `planetary_magnitude`
  (Mallama and Hilton 2018) where it covers the body; for the Sun, the Moon
  and Pluto the formula Horizons uses, cited in the code.
- **`ring_tilt_deg`** (Saturn): the ring opening angle B, the saturnicentric
  latitude of the observer over the ring plane (positive: the north face is
  visible). **`ring_pole`**: Saturn's north pole as an ENU unit vector (IAU
  WGCCRE pole), so a client can also orient the rings on screen.
- **`moon_phase.phase_deg`**: the Moon's minus the Sun's apparent ecliptic
  longitude, 0 to 360 (0 new, 90 first quarter, 180 full, 270 last quarter),
  per sample. **`next`**: the next new, first quarter, full and last quarter
  after `from`, always four entries, even beyond the window.
- **`events`**, sorted by time, only inside the window:
  - Sun: `rise`, `set`, `transit`; `civil_dawn`, `civil_dusk` (−6°),
    `nautical_dawn`, `nautical_dusk` (−12°), `astronomical_dawn`,
    `astronomical_dusk` (−18°). Twilights belong to the Sun only.
  - Moon: `rise`, `set`, `transit`.
  - Rise and set follow the almanac convention, so they match published
    tables: upper limb on a sea-level horizon with 34′ of standard refraction
    (the Moon's parallax and semidiameter included). Each event carries the
    body's `az_deg` (rise, set) or `alt_deg` (transit).
  - Polar day or night simply has no rise or set in the window.
- **`stars_rotation`**: per sample, a 3×3 matrix (row-major, 9 numbers) that
  turns an ICRS (J2000) unit vector into this observer's ENU frame at that
  instant: precession, nutation and Earth rotation. It leaves out annual
  aberration (≤ 20.5″), refraction and proper motion since J2000 (≤ 1.6′ for
  any star brighter than magnitude 5); all three are invisible at the size
  pietri.dev draws a star. A client multiplies, never computes the sky.

### 5.4 Rounding (fixed, for determinism)

Angles 4 decimals (0.36″), unit vectors and matrices 6 decimals, distances
1 km, magnitudes 2 decimals, fractions 4 decimals, rates 5 decimals,
instants to the second.

### 5.5 How pietri.dev uses it (decided)

pietri.dev never calls origen from the browser. Its server tick asks
`/v1/sky` every 15 minutes for 48 hours ahead and publishes the answer as a
static file; the browser only interpolates between samples. Because each
file covers 48 hours, pietri.dev's sky keeps working through two days of
origen being down. What pietri.dev changes on its side (dropping
`astronomy-engine`, the sky and seasons sections of its spec) is pietri.dev's
work, in its repository (open point 14.4).

## 6. `GET /v1/stars`

- Every Hipparcos star (ESA 1997, `hip_main.dat`) with V ≤ 5.0, about 1,600
  stars, positions at epoch J2000 in ICRS.
- Proper names from the IAU Working Group on Star Names list (the name, when
  the star has one; about 300 of them in this range).
- Columns: `hip`, `ra_deg`, `dec_deg`, `vmag`, `bv` (colour index, so clients
  can tint stars), `name` (or `null`).
- It never changes within a catalogue version, so it is served with a strong
  `ETag` and `Cache-Control: public, max-age=86400`.
- How the catalogue file reaches the service is open point 14.2.

## 7. `GET /v1/seasons?year=`

- `year` from 1850 to 2149 (the ephemeris range).
- Returns the four instants, named by the event, not by a hemisphere's
  season: `march_equinox`, `june_solstice`, `september_equinox`,
  `december_solstice`, each in UTC. The instant is when the Sun's apparent
  geocentric ecliptic longitude of date reaches 0°, 90°, 180° and 270°.
  Which season starts in which hemisphere is the client's call (pietri.dev:
  autumn starts at the March equinox).

## 8. The page (`GET /`)

- First line: the motto, "Astronomy and astrology were born sisters. They
  will be again." The page speaks to anyone curious about the sky.
- Shows the sky right now: a round sky chart (horizon circle, cardinal
  points, bodies and stars at their altitude and azimuth, the Moon with its
  phase), plus a table of the bodies (altitude, azimuth, magnitude, rise and
  set) and the Sun's twilights.
- Defaults to Unquillo; `?lat=&lon=&elev_m=&tz=` show any place (`tz` only
  changes how times are displayed; default `UTC`, Unquillo's link carries
  `America/Argentina/Cordoba`).
- Server-rendered with Jinja. One plain JS file in `static/` draws the chart
  from `/v1/sky` and `/v1/stars` on the same origin, refreshing every 10
  minutes. It draws, never computes.
- English UI. Credits at the bottom: JPL DE440s, ESA Hipparcos, IAU WGSN.
  The browser calls no third party: fonts self-hosted, nothing else loaded.

## 9. Privacy and logs (decided)

- origen stores nothing about a request.
- Application logs never include query strings or bodies: the access log
  keeps method, path, status and duration only. This matters little for
  Unquillo, and a lot once a user's own place, or a birth, reaches origen.
- The Caddy site block for origen.pietri.dev drops the query string from its
  access log too (phase 3), so the panel's log reading gets hosts and
  statuses, never places.
- No third party is ever called while answering: ephemeris, stars, cities and
  time zones are local files.

## 10. Astrology (later; its place reserved now)

### 10.1 Shape

- A pure module, `src/origen/astrology/`: functions from astronomical
  inputs (apparent geocentric ecliptic longitudes and their rates, true
  obliquity, local sidereal time, latitude) to astrological results. No web,
  no I/O, no Skyfield import. The `sky/` layer computes the inputs; this
  module only interprets them. That keeps one source of positions.
- Tropical zodiac, geocentric, ecliptic and equinox of date.
- Tables are data in `data/astrology/` (TOML): aspects (`conjunction 0°`,
  `sextile 60°`, `square 90°`, `trine 120°`, `opposition 180°` to start)
  with their orbs, per body if wanted; house systems available.
- Tests compare against Swiss Ephemeris (`pyswisseph`, dev only) for fixed
  dates and places: longitudes within 1″, cusps within 1″, the same signs,
  retrogrades and aspects.

### 10.2 Astrology of the sky right now (in `/v1/sky`)

An `astrology` block added to `/v1/sky` (an addition, so still `/v1`), per
body at each sample: `sign` (`aries` … `pisces`), `deg_in_sign`,
`retrograde`; per sample: the house of each body for that place (Placidus)
and the aspects between bodies. pietri.dev's planet cards read it.

### 10.3 `POST /v1/charts`

- Input: `date` (local, `YYYY-MM-DD`), `time` (local `HH:MM[:SS]`, optional),
  and a place, either `{ "lat", "lon" }` or `{ "name": "Unquillo, AR" }`,
  plus optional `house_system` (`placidus` default, `whole_sign`).
- Places by name come from GeoNames offline (`cities500`, CC BY 4.0,
  downloaded at image build with a checksum). An ambiguous name returns 422
  with the candidates; the client asks the person and sends coordinates.
- The historical UTC offset comes from the place's time zone
  (`timezonefinder`) and `zoneinfo` with a pinned `tzdata`. A local time that
  does not exist (a clock jump) is 422; an ambiguous one (clocks going back)
  needs `fold` (0 or 1), like Python's. The answer echoes the zone and offset
  used, so the person can see it.
- Output: per body ecliptic longitude, latitude, speed and retrograde, sign
  and degree; ascendant, midheaven and the 12 cusps; aspects with their orb
  and whether applying.
- **Without a time**: no houses, ascendant or midheaven; positions are for
  local noon, the answer says so (`"time_known": false`) and gives the Moon's
  possible range that day.
- Placidus is undefined beyond the polar circles: there the chart uses whole
  signs and says so.
- Nothing received is stored or logged (section 9).

## 11. Descriptions (later)

- `POST /v1/descriptions` receives a chart (the output of `/v1/charts`) and
  returns a short astral description for an NPC, in Spanish.
- Built from templates in `data/descriptions/es/` (TOML or Markdown with
  slots, decided in that phase) that marcos edits without touching code.
  Tone: half joking, laughing a little at astrology itself.
- Deterministic: the choice between template variants comes from a SHA-256
  of the canonical chart JSON, so the same chart always gives the same text
  for the same template version, which the answer carries.
- No AI at that point.

## 12. origen's user interface and id.pietri.dev (later)

origen will have its own interface for users (sign in, see one's chart, its
description and today's sky for one's place) as a **client** of
id.pietri.dev. What origen expects from it, written now so id.pietri.dev can
be built against it and pietri.dev's test user can simulate it:

- OpenID Connect, authorization code flow with PKCE; origen is a confidential
  client with its own redirect URI. Scopes: `openid profile` plus
  `birth` for the birth data.
- Claims used: `sub`, `name`, `picture`.
- Birth data, read with the user's access token from an id.pietri.dev
  resource (proposed `GET /v1/me/birth`):
  `{ "date", "time" | null, "place": { "name", "lat", "lon", "tz" }, "public": { "chart": bool, "description": bool } }`.
- origen keeps no tables: the session is an encrypted, signed, short-lived
  cookie holding the subject and the tokens; signing out clears it. A chart
  is recomputed on every view.
- What is public is decided in id.pietri.dev; origen only respects it.

## 13. Tests

- **Positions** against recorded JPL Horizons answers (observer tables,
  topocentric, airless) for fixed dates and places, Unquillo and two more
  (one northern, one near a pole): RA/Dec and azimuth/altitude within 1″ for
  the planets and 2″ for the Moon, illuminated fraction within 0.001,
  distance within 1 km for the Moon and 10 km otherwise, magnitude within
  0.05 (0.1 for the Moon). Positions and distances are recorded for the same
  targets origen uses (the barycentres of Mars to Pluto), magnitude and
  illumination for the planet itself.
- **Saturn's rings**: B against Meeus's worked example (*Astronomical
  Algorithms*, chapter 45) and published Astronomical Almanac values, within
  0.01°. (Horizons' sub-observer latitude is planetodetic, not the same
  angle.)
- **Rise, set, transit, twilights, Moon phases and seasons** against
  recorded US Naval Observatory tables (its JSON API) for fixed dates: within
  1 minute (the tables are rounded to the minute).
- **Stars**: count, a few known stars (Sirius, Canopus, α Centauri, Acrux)
  with their names and positions, and the rotation matrix checked against
  Skyfield's own alt/az for those stars within 25″ (the aberration it leaves
  out).
- **Determinism**: the same request twice, and in two processes, gives
  identical bytes.
- **Contracts**: every response validates against its schema; limits give
  422 with a problem body.
- Reference answers are recorded by `scripts/record_*.py`, run by hand when
  a fixture is added, and committed in `tests/fixtures/`. Tests never touch
  the network. Tests that need DE440s skip with a clear message when it has
  not been fetched; CI always fetches it.

## 14. Open points (stop: marcos's call)

1. **pietri.dev's planet cards versus "version 1 is astronomy only".**
   pietri.dev's spec (stage 1, section 9 and step 6) promises planet cards
   with sign, degrees and retrograde, and computes them in the browser with
   `astronomy-engine`; that has to go, and origen's version 1 brings no
   astrology. Options:
   - **(a) Recommended**: version 1 includes each body's apparent geocentric
     ecliptic longitude, latitude and longitude rate (`ecl_*`, section 5.2).
     They are astronomy, cost nothing, and retrograde motion is simply a
     negative rate. Sign and house stay for the astrology phase, asked for
     right after phase 3, so pietri.dev's cards show degrees now and the
     sign when that phase lands. pietri.dev must not derive the sign itself
     (no duplicated code).
   - (b) Leave `ecl_*` out; pietri.dev's cards show only astronomy until the
     astrology phase.
   - (c) Bring the astrology of the sky right now into phase 2.
2. **Where the star catalogue comes from.** The ephemeris is downloaded at
   build. For the stars:
   - **(a) Recommended**: commit the derived file (`data/stars/hip5.csv`,
     about 1,600 rows, ~100 KB) with the script that builds it from
     `hip_main.dat` and the IAU names, and the SHA-256 of both sources. Tests
     run offline, a catalogue change is a reviewable diff.
   - (b) Download `hip_main.dat` (~50 MB) and the names at build, like the
     ephemeris.
3. **The ephemeris range.** DE440s covers 1849-12-26 to 2150-01-22 (~32 MB).
   That is plenty for the sky, but birth charts of people born before 1850
   would be refused, and serious research may want more. Recommended: DE440s
   now, and decide when charts arrive whether the image also carries DE440
   (1550 to 2650, ~115 MB). Not blocking.
4. **pietri.dev's side.** Its spec needs an amendment (sections 8.1, 8.2, 9,
   10.5 and step 6: sky, seasons and the tick's sun elevation come from
   origen, `astronomy-engine` leaves). Recommended: a separate pietri.dev
   thread once this spec is approved, so each repository changes only its
   own files. Until origen is deployed, pietri.dev's tick points at a local
   origen (`ORIGEN_URL=http://127.0.0.1:8800`) or at recorded fixtures.
5. **Server details (phase 3, proposed)**: host port `127.0.0.1:8800` (the
   next free hundred), container memory limit 256 MB (DE440s is
   memory-mapped), behind Cloudflare and the Caddy + CrowdSec guard like the
   other public sites. pietri.dev's tick reaches it over the host.

## 15. Phases

Each phase ends with tests, a short report in `docs/reports/`, and a stop for
marcos's review. marcos tries every phase on his PC (CachyOS) with one-line
commands before anything goes up to GitHub, without waiting for CI. Every
phase's report lists those commands.

0. **Spec** (this document) and `CLAUDE.md`.
1. **Base**: `pyproject.toml` and `uv.lock`, ruff, mypy, pytest; `origen
   fetch-data` (downloads DE440s into `data/ephemeris/` and checks its
   SHA-256); `origen serve`; `/healthz`; a placeholder page with the motto;
   the README for the curious person; Dockerfile (multi-arch, ephemeris
   fetched and checked at build); CI (lint, types, tests, an amd64 image
   build on PRs, the multi-arch image to GHCR on `main`).
2. **Positions**: `/v1/sky`, `/v1/stars`, `/v1/seasons`, their schemas, the
   recorded Horizons and USNO fixtures, and the page.
3. **Deploy** on marcos's server, only when he says.

The astrology (sky right now, charts, descriptions) and the user interface
are later phases, each asked for separately.

### 15.1 Commands to try a phase locally (from phase 1)

Each is one line, run from the repository folder:

```
uv sync                                                    # install, from the lockfile
uv run origen fetch-data                                   # download and check DE440s (once)
uv run pytest -q                                           # all tests
uv run ruff check . && uv run ruff format --check . && uv run mypy   # lint and types
uv run origen serve --reload                               # http://127.0.0.1:8800
curl -s 'http://127.0.0.1:8800/v1/sky?lat=-31.23&lon=-64.32&elev_m=700&hours=2' | head -c 600
xdg-open 'http://127.0.0.1:8800/?lat=-31.23&lon=-64.32&elev_m=700&tz=America/Argentina/Cordoba'
docker build -t origen:local . && docker run --rm -p 8800:8000 origen:local   # the image
```
