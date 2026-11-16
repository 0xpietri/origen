# Rules for AI agents working in this repository

## Source of truth
- This repository is origen (origen.pietri.dev): a site for anyone curious about astronomy and astrology, and the only place in the pietri.dev ecosystem where the sky is computed.
- The specification is `docs/spec/ORIGEN_SPEC_v0.1.md`. Read it fully before any change.
- Implement **only the phase you were asked for** (spec §15). Each phase ends with tests, a short report in `docs/reports/` (with the one-line commands to try it locally) and a stop.
- If the spec is ambiguous or contradicts itself, stop on that point, explain it, and propose options. Do not silently fill architectural gaps.
- The motto stays the first line of the README and of the page: "Astronomy and astrology were born sisters. They will be again."

## Language
- Code, comments, commit messages, docs and the page UI: **English**. Description templates (later) are Spanish data.
- The owner (marcos) talks in Spanish (rioplatense); user-facing chat is Spanish.
- Instants are UTC (ISO 8601 with `Z`) in and out; local time is only for display.

## Boundaries
- No duplicated code between repositories, however small. pietri.dev, micelio.pietri.dev and later apps consume origen; if something about the sky breaks, the fix lives only here.
- The engine is a stateless calculator: it stores nothing and never logs query strings, bodies or any personal data (spec §9).
- Users and their data live only in id.pietri.dev. origen has no user tables and never stores user data (spec §12).
- No third party is called while answering a request: ephemeris, stars, cities and time zones are local files.
- Never read or write another project's database; talk only over HTTP. Nothing here talks to the agents' office (`0xpietri/agents`) or holds its keys.
- Weather is not origen's; it stays in pietri.dev.
- Agents open PRs; they never merge. Deploy (phase 3) only when marcos says.

## Contracts
- Every response has a JSON Schema in `schemas/`. Within `/v1` fields may be added, never renamed, removed or changed in meaning or unit; breaking changes go to `/v2`.
- Same request, same build: byte-identical body. No generation timestamps, fixed rounding per field.
- Skyfield's timescale uses its bundled data (`builtin=True`); nothing astronomical is downloaded at run time.

## Engineering
- Stack (spec §3, as marcos confirms it there): Python 3.12, `uv` with a lockfile, pytest, ruff, mypy; Skyfield + JPL DE440s; FastAPI + Jinja, plain CSS/JS (no build step). Do not add a framework, engine or service without him.
- Astropy, astroquery, SciPy and Jupyter are the `research` dependency group only; `src/` never imports them or `research/`.
- Swiss Ephemeris (`pyswisseph`, AGPL) is a development dependency for comparison tests only, never in the service or the image.
- No database for now. If one is ever needed: PostgreSQL 17. Never Redis.
- The ephemeris is downloaded (`origen fetch-data`, and at image build) and checked against a pinned SHA-256; it never enters git.
- Every behaviour change comes with tests. Tests never touch the network; reference answers (JPL Horizons, USNO) are recorded by hand with `scripts/` and committed in `tests/fixtures/`.
- No inline `<script>` or `<style>` blocks: the CSP only allows files from `/static` (inline `style=""` attributes are allowed).
- Keep Docker images multi-arch (amd64 + arm64).
- Secrets only in `.env` / environment; commit `.env.example` with placeholders only.
