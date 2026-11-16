# origen
Astronomy and astrology were born sisters. They will be again.

origen is a site for anyone curious about the sky: where the Sun, the Moon, the planets
and the brightest stars really are, over any place on Earth, right now or at any moment
between 1850 and 2150. It computes with the tools professionals use (the JPL DE440s
ephemeris through [Skyfield](https://rhodesmill.org/skyfield/), and the ESA Hipparcos
star catalogue) and explains the results plainly. Astrology comes later, in this same
repository, built on the same positions.

origen is a calculator: you send a date, a time and a place, and it answers. It stores
nothing you send.

It is also the one place in the [pietri.dev](https://pietri.dev) family where the sky is
computed; pietri.dev's little 3D world shows the real sky over Unquillo, Córdoba, by asking
origen.

Status: phase 2. The page shows the sky right now over any place, and the API answers:

- `GET /v1/sky?lat=&lon=[&elev_m=&from=&hours=&step_min=]`: every body sampled over a
  window, their rise, set and twilights, the Moon's phase and the rotation that places the stars.
- `GET /v1/stars`: the 1,625 Hipparcos stars down to magnitude 5, at J2000, with IAU names.
- `GET /v1/seasons?year=`: the instants of the equinoxes and solstices.
- `GET /schemas/<name>.json`: the JSON Schema of every answer.

- Specification: [`docs/spec/ORIGEN_SPEC_v0.1.md`](docs/spec/ORIGEN_SPEC_v0.1.md)
- Phase reports: [`docs/reports/`](docs/reports/)
- Rules for AI agents working here: [`CLAUDE.md`](CLAUDE.md)

## Run it

Needs [uv](https://docs.astral.sh/uv/) (it brings Python 3.12 if you don't have it).

```
uv sync                       # install from the lockfile
uv run origen fetch-data      # download and check the ephemeris and the stars (~85 MB, once)
uv run origen serve --reload  # http://127.0.0.1:8800
```

`uv run pytest` runs the tests; `uv run ruff check . && uv run ruff format --check . && uv run mypy`
runs lint and types. The data files go to `./data` (or `$ORIGEN_DATA_DIR`), are checked against
pinned SHA-256 checksums, and never enter git.

With Docker: `docker build -t origen . && docker run --rm -p 8800:8000 origen`.

## Sources and credits

- Positions: JPL planetary ephemeris DE440s (Park et al. 2021), via Skyfield.
- Stars: The Hipparcos Catalogue (ESA 1997, CDS I/239).
- Star names: IAU Working Group on Star Names (CC BY).

## Licence

MIT, see [`LICENSE`](LICENSE).
