"""The data files origen computes from, and how they are fetched and checked (spec §3, §6).

None of them enters git. Each is downloaded from its publisher (or a mirror of the same
file), checked against a pinned size and SHA-256, and only then moved into place, so a
half-downloaded or altered file is never used.

This module uses the standard library only, so the Docker build can run it on its own,
before the rest of the code is copied: `python data.py <data dir>`.
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

# Shown in /healthz and, from phase 2, in every response's `engine` block.
EPHEMERIS = "DE440s"
STARS = "hip1997-iaucsn20220404"

USER_AGENT = "origen-fetch-data/1 (+https://github.com/0xpietri/origen)"
CHUNK = 1 << 20


@dataclass(frozen=True)
class DataFile:
    key: str
    path: str  # relative to the data directory
    size: int
    sha256: str
    urls: tuple[str, ...]  # tried in order; every one serves the same bytes
    source: str


FILES: tuple[DataFile, ...] = (
    DataFile(
        key="de440s",
        path="ephemeris/de440s.bsp",
        size=32_726_016,
        sha256="c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2",
        urls=(
            "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp",
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
        ),
        source="JPL planetary ephemeris DE440s, 1849-12-26 to 2150-01-22 (Park et al. 2021)",
    ),
    DataFile(
        key="hipparcos",
        path="stars/hip_main.dat",
        size=53_316_318,
        sha256="58ceabb104d647160d9437ce6e513a02a036bb4ad9f8879a5a22fd52943616e0",
        urls=(
            "https://cdsarc.cds.unistra.fr/ftp/cats/I/239/hip_main.dat",
            "https://vizier.cfa.harvard.edu/ftp/cats/I/239/hip_main.dat",
        ),
        source="The Hipparcos Catalogue, ESA 1997 (CDS I/239), read with Skyfield's loader",
    ),
    DataFile(
        key="iau_names",
        path="stars/IAU-CSN.txt",
        size=71_800,
        sha256="84fac0c90f1b19abc491c2793469e0caa7b003ad1bc93a790ca41147010d0eb0",
        urls=("https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt",),
        source="IAU Catalog of Star Names, WGSN, last updated 2022-04-04 (CC BY)",
    ),
)


class FetchError(RuntimeError):
    pass


def default_data_dir() -> Path:
    return Path(os.environ.get("ORIGEN_DATA_DIR", "data")).resolve()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def status_of(data_dir: Path, file: DataFile) -> str:
    """`ok`, `missing` or `bad` (wrong size or checksum)."""
    path = data_dir / file.path
    if not path.is_file():
        return "missing"
    if path.stat().st_size != file.size or sha256_of(path) != file.sha256:
        return "bad"
    return "ok"


def check(data_dir: Path, files: Iterable[DataFile] = FILES) -> dict[str, str]:
    return {f.key: status_of(data_dir, f) for f in files}


def _download(url: str, dest: Path, file: DataFile, timeout: float) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while block := resp.read(CHUNK):
            size += len(block)
            if size > file.size:
                raise FetchError(f"more than the expected {file.size} bytes")
            h.update(block)
            out.write(block)
    if size != file.size:
        raise FetchError(f"got {size} bytes, expected {file.size}")
    if h.hexdigest() != file.sha256:
        raise FetchError(f"SHA-256 {h.hexdigest()} does not match the pinned {file.sha256}")


def fetch_one(
    data_dir: Path,
    file: DataFile,
    timeout: float = 60.0,
    log: Callable[[str], None] = print,
) -> str:
    """Make sure one file is in place and intact. Returns `present` or `fetched`."""
    if status_of(data_dir, file) == "ok":
        return "present"
    dest = data_dir / file.path
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    errors = []
    for url in file.urls:
        log(f"{file.key}: downloading {url}")
        try:
            _download(url, part, file, timeout)
        except (OSError, FetchError) as e:
            errors.append(f"{url}: {e}")
            log(f"{file.key}: failed, {e}")
            part.unlink(missing_ok=True)
            continue
        os.replace(part, dest)
        return "fetched"
    raise FetchError(f"{file.key}: every source failed:\n  " + "\n  ".join(errors))


def fetch(
    data_dir: Path,
    files: Iterable[DataFile] = FILES,
    timeout: float = 60.0,
    log: Callable[[str], None] = print,
) -> dict[str, str]:
    return {f.key: fetch_one(data_dir, f, timeout, log) for f in files}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    data_dir = Path(args[0]).resolve() if args else default_data_dir()
    try:
        result = fetch(data_dir)
    except FetchError as e:
        print(e, file=sys.stderr)
        return 1
    for key, state in result.items():
        print(f"{key}: {state}")
    print(f"data in {data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
