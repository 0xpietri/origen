# Phase 0 report: specification and agent rules (2026-11-16)

## Done
- `docs/spec/ORIGEN_SPEC_v0.1.md`: purpose, scope of version 1 (`/v1/sky`,
  `/v1/stars`, `/v1/seasons`, the page), contracts, privacy, the reserved place
  of astrology (sky right now, charts, descriptions) and of the user interface
  with id.pietri.dev, tests and phases.
- `CLAUDE.md`: the same rules as marcos's other repositories, plus origen's
  own (no duplicated code across repositories, stateless engine, no user data).

## Tests
None: no code in phase 0.

## Decisions
- marcos approved the spec and the stack on 2026-11-16, and chose the MIT licence.
- Section 14: ecliptic longitude and rate in version 1; Hipparcos read with
  Skyfield's loader and downloaded like the ephemeris; port 127.0.0.1:8800 and
  256 MB; the ephemeris range waits for the birth charts; pietri.dev's
  amendment goes to a separate thread.

## Next
Phase 1, base: project, CI, Docker, ephemeris download.
