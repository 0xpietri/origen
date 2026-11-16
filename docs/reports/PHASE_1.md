# Phase 1 report: the base (2026-11-16)

## Done
- Python 3.12 project with `uv` and a lockfile; ruff, mypy (strict on `src/`), pytest.
  Dependency groups: `dev` (default) and `research` (Astropy, astroquery, SciPy,
  JupyterLab; never in the image, never imported by `src/`).
- `origen fetch-data` downloads DE440s, Hipparcos (`hip_main.dat`) and the IAU star names
  into `./data` (or `$ORIGEN_DATA_DIR`). Each file has a pinned size and SHA-256 and a
  mirror of the same bytes; a file is moved into place only after both match, so a broken
  download is never used. `origen check-data` checks without downloading. The files are
  git-ignored.
- `origen serve` (port 8800 locally): `/healthz` with version, ephemeris, star catalogue
  and the state of each data file (503 while any is missing or damaged); `/` is a
  placeholder page whose first line is the motto. CSP and security headers; no inline
  scripts or styles. Access log: method, path, status and time, never the query string
  (uvicorn's own access log is off).
- README for the curious reader (motto first), MIT `LICENSE`, `.env.example`.
- Dockerfile (multi-arch base, `uv` 0.13.7 like factory-panel): the data files are
  fetched in their own layer by `data.py` alone, so code changes never download them
  again; the image re-checks them and refuses to build if one is wrong. Runs as an
  unprivileged user, with a health check.
- CI: lint, format, types and tests with the real data (cached by the pins); on PRs an
  amd64 image that must answer `/healthz`; on `main` the amd64 + arm64 image to GHCR,
  tagged with the commit SHA.

## Tests
20 tests: fetching (checksum, size, mirror fallback, damaged file replaced, nothing left
behind on failure), `/healthz` with and without data, the page and its motto, CSP, no
inline blocks, the access log without the query, determinism, the CLI, and that DE440s
opens with Skyfield and covers 1850 to 2149. Without the data, the three tests that need
it skip and say how to fetch it. Ruff and mypy clean. The image was built and run:
`/healthz` ok with all three files, about 40 MB of RAM idle, image 593 MB.

## Notes
- CDS (Strasbourg), Hipparcos's publisher, refused connections from the build machine;
  the CfA mirror of the same file served it. Both URLs are tried, the checksum is the same.
- The image is big mostly because of NumPy and the 86 MB of data; fine for now.

## Try it on your PC
From the repository folder, one line each:

```
git fetch origin && git checkout -f -B fase-1 origin/claude/project-thread-qjcwfm   # this phase's branch
uv sync && uv run origen fetch-data                                                  # install and download the data (once)
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy   # tests, lint, types
uv run origen serve --reload                                                         # then open http://127.0.0.1:8800
curl -s http://127.0.0.1:8800/healthz                                                # in another terminal
docker build -t origen:local . && docker run --rm -p 8800:8000 origen:local          # the image
```

If `uv` is missing: `sudo pacman -S uv`.

## Next
Phase 2, positions: `/v1/sky`, `/v1/stars`, `/v1/seasons`, their schemas, the recorded
Horizons and USNO fixtures, and the page with the sky right now.
