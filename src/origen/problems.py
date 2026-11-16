"""Errors as application/problem+json (RFC 9457, spec §4)."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from origen.jsonout import ProblemJSON


class Problem(Exception):
    def __init__(self, status: int, detail: str, param: str | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.param = param


def body(status: int, detail: str, param: str | None) -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "param": param,
    }


def _validation_detail(err: dict[str, Any], param: str | None) -> str:
    ctx = err.get("ctx") or {}
    kind = err.get("type", "")
    if kind == "missing":
        return f"{param} is required"
    if "ge" in ctx and "le" in ctx:  # pragma: no cover - pydantic reports one bound at a time
        return f"{param} must be between {ctx['ge']} and {ctx['le']}"
    if "ge" in ctx:
        return f"{param} must be at least {ctx['ge']}"
    if "le" in ctx:
        return f"{param} must be at most {ctx['le']}"
    if kind.startswith("int"):
        return f"{param} must be a whole number"
    if kind.startswith("float"):
        return f"{param} must be a number"
    return f"{param}: {err.get('msg', 'invalid')}"


def install(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def problem(_: Request, exc: Problem) -> ProblemJSON:
        return ProblemJSON(body(exc.status, exc.detail, exc.param), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> ProblemJSON:
        err = exc.errors()[0]
        loc = err.get("loc", ())
        param = str(loc[-1]) if len(loc) > 1 else None
        return ProblemJSON(body(422, _validation_detail(err, param), param), status_code=422)

    @app.exception_handler(HTTPException)
    async def http(_: Request, exc: HTTPException) -> ProblemJSON:
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return ProblemJSON(
            body(exc.status_code, detail, None), status_code=exc.status_code, headers=exc.headers
        )
