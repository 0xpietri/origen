"""``origen`` command line.

origen serve [--host H] [--port P] [--reload]   run the web app (uvicorn)
origen fetch-data [--data-dir D]                download and check the ephemeris and stars
origen check-data [--data-dir D]                check them without downloading
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from origen import data

_PACKAGE_DIR = Path(__file__).resolve().parent


def _data_dir(args: argparse.Namespace) -> Path:
    return Path(args.data_dir).resolve() if args.data_dir else data.default_data_dir()


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.data_dir:
        os.environ["ORIGEN_DATA_DIR"] = str(_data_dir(args))
    uvicorn.run(
        "origen.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        # Watch only the package. uvicorn's polling reloader (no watchfiles here) stats every
        # *.py under the reload dirs four times a second; from the repo root that includes
        # .venv's thousands of files and keeps a core busy.
        reload_dirs=[str(_PACKAGE_DIR)] if args.reload else None,
        # uvicorn's own access log prints the query string; origen logs without it (spec §9).
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
    )
    return 0


def _fetch_data(args: argparse.Namespace) -> int:
    return data.main([str(_data_dir(args))])


def _check_data(args: argparse.Namespace) -> int:
    result = data.check(_data_dir(args))
    for key, state in result.items():
        print(f"{key}: {state}")
    return 0 if all(s == "ok" for s in result.values()) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="origen", description="The real sky, computed.")
    sub = p.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8800)
    serve.add_argument("--reload", action="store_true", help="restart on code changes")
    serve.add_argument("--forwarded-allow-ips", default="127.0.0.1")
    serve.add_argument("--data-dir")
    serve.set_defaults(func=_serve)

    for name, func, text in (
        ("fetch-data", _fetch_data, "download and check the data files"),
        ("check-data", _check_data, "check the data files without downloading"),
    ):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--data-dir", help="default: $ORIGEN_DATA_DIR or ./data")
        cmd.set_defaults(func=func)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
