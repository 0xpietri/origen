"""The web app: /v1 (the sky, the stars, the seasons), /schemas, /healthz and the page."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from origen import __version__, api, data, problems
from origen.jsonout import JSON
from origen.problems import Problem

WEB = Path(__file__).parent / "web"
SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
SCHEMA_NAMES = ("sky.v1", "stars.v1", "seasons.v1", "error.v1")

# The page's default place: Unquillo, the first client's (spec §5.1, §8).
UNQUILLO = {"lat": -31.23, "lon": -64.32, "elev_m": 700.0}
UNQUILLO_TZ = "America/Argentina/Cordoba"
TZ_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){0,2}$")

MOTTO = "Astronomy and astrology were born sisters. They will be again."

# Only files from this origin; no inline <script> or <style> blocks (CLAUDE.md).
# Inline style="" attributes stay allowed for drawn widths and positions.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)

access_log = logging.getLogger("origen.access")


def create_app(data_dir: Path | None = None) -> FastAPI:
    """Build the app. Data files are checked once here, never per request."""
    # A no-op when logging is already set up (tests, or an embedding server).
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    data_dir = data_dir or data.default_data_dir()
    files = data.check(data_dir)
    service = _load_service(data_dir) if all(v == "ok" for v in files.values()) else None
    app = FastAPI(
        title="origen", version=__version__, docs_url=None, redoc_url=None, openapi_url=None
    )
    problems.install(app)

    def get_service() -> api.Service:
        if service is None:
            raise Problem(503, "the data files are missing or damaged: run `origen fetch-data`")
        return service

    app.include_router(api.router(get_service))
    templates = Jinja2Templates(directory=WEB / "templates")
    app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")

    @app.middleware("http")
    async def headers_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        # Method, path, status and duration only: never the query string or the body,
        # which will carry people's places and births (spec §9).
        access_log.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response

    @app.api_route("/healthz", methods=["GET", "HEAD"])
    def healthz() -> JSON:
        ok = all(state == "ok" for state in files.values())
        body = {
            "status": "ok" if ok else "degraded",
            "version": __version__,
            "ephemeris": data.EPHEMERIS,
            "stars": data.STARS,
            "data": files,
        }
        return JSON(body, status_code=200 if ok else 503)

    @app.get("/schemas/{name}.json")
    def schema(name: str) -> Response:
        if name not in SCHEMA_NAMES:
            raise Problem(404, f"no schema named {name}")
        return Response(
            (SCHEMAS / f"{name}.json").read_bytes(), media_type="application/schema+json"
        )

    @app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def index(
        request: Request,
        lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
        lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
        elev_m: Annotated[float | None, Query(ge=-500, le=9000)] = None,
        tz: Annotated[str, Query(max_length=64)] = "UTC",
    ) -> HTMLResponse:
        if (lat is None) != (lon is None):
            raise Problem(422, "give both lat and lon, or neither", "lat" if lat is None else "lon")
        if not TZ_NAME.match(tz):
            raise Problem(422, "tz must be a time zone name like America/Argentina/Cordoba", "tz")
        if lat is None or lon is None:
            place = {**UNQUILLO, "name": "Unquillo, Argentina"}
        else:
            place = {"lat": lat, "lon": lon, "elev_m": elev_m or 0.0, "name": None}
        context = {
            "motto": MOTTO,
            "version": __version__,
            "place": place,
            "tz": tz,
            "unquillo": {**UNQUILLO, "tz": UNQUILLO_TZ},
        }
        return templates.TemplateResponse(request, "index.html", context)

    return app


def _load_service(data_dir: Path) -> api.Service:
    from origen.sky import stars
    from origen.sky.engine import Sky

    sky = Sky(data_dir)
    return api.Service(sky, stars.load(sky, data_dir))
