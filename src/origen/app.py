"""The web app: /healthz and the page (phase 1). The sky endpoints arrive in phase 2."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from origen import __version__, data

WEB = Path(__file__).parent / "web"

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
    app = FastAPI(title="origen", version=__version__, docs_url=None, redoc_url=None)
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
    def healthz() -> JSONResponse:
        ok = all(state == "ok" for state in files.values())
        body = {
            "status": "ok" if ok else "degraded",
            "version": __version__,
            "ephemeris": data.EPHEMERIS,
            "stars": data.STARS,
            "data": files,
        }
        return JSONResponse(body, status_code=200 if ok else 503)

    @app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "index.html", {"motto": MOTTO, "version": __version__}
        )

    return app
