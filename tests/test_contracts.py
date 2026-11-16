"""Schemas, limits, errors and determinism (spec §4, §13)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from origen.app import SCHEMAS, create_app

from .conftest import REAL_DATA, needs_data

UNQUILLO = {"lat": -31.23, "lon": -64.32, "elev_m": 700}
SKY = {**UNQUILLO, "from": "2026-11-16T00:00:00Z"}


def validator(name: str) -> Draft202012Validator:
    docs = {p.name: json.loads(p.read_text()) for p in SCHEMAS.glob("*.json")}
    registry: Registry[Any] = Registry().with_resources(
        (doc["$id"], Resource.from_contents(doc)) for doc in docs.values()
    )
    schema = docs[f"{name}.json"]
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=registry)


def test_every_schema_is_valid_and_served(empty_dir: Path) -> None:
    client = TestClient(create_app(empty_dir))
    for name in ("sky.v1", "stars.v1", "seasons.v1", "error.v1"):
        validator(name)
        r = client.get(f"/schemas/{name}.json")
        assert r.status_code == 200
        assert json.loads(r.content)["$id"].endswith(f"/schemas/{name}.json")
    assert client.get("/schemas/other.json").status_code == 404


@needs_data
@pytest.mark.parametrize(
    ("path", "params", "schema"),
    [
        ("/v1/sky", SKY, "sky.v1"),
        (
            "/v1/sky",
            {
                "lat": 78.2232,
                "lon": 15.6267,
                "from": "2025-06-21T00:00:00Z",
                "hours": 168,
                "step_min": 5,
            },
            "sky.v1",
        ),
        (
            "/v1/sky",
            {"lat": -90, "lon": 180, "from": "1850-01-01T00:00:00Z", "hours": 1, "step_min": 1},
            "sky.v1",
        ),
        ("/v1/stars", {}, "stars.v1"),
        ("/v1/seasons", {"year": 2026}, "seasons.v1"),
    ],
)
def test_responses_follow_their_schema(
    path: str, params: dict[str, Any], schema: str, client: TestClient
) -> None:
    r = client.get(path, params=params)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    body = r.json()
    validator(schema).validate(body)
    assert body["schema"] == f"origen.{schema}"
    assert body["engine"]["ephemeris"] == "DE440s"


@needs_data
def test_sky_shape(client: TestClient) -> None:
    body = client.get("/v1/sky", params=SKY).json()
    assert body["count"] == 289 == len(body["times"]) == len(body["stars_rotation"])
    assert (
        body["times"][0] == "2026-11-16T00:00:00Z" and body["times"][-1] == "2026-11-18T00:00:00Z"
    )
    assert list(body["bodies"]) == [
        "sun",
        "moon",
        "mercury",
        "venus",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
        "pluto",
    ]
    assert "illuminated_fraction" not in body["bodies"]["sun"]
    for b in body["bodies"].values():
        assert all(len(col) == 289 for col in b.values())
    assert body["observer"] == {"lat_deg": -31.23, "lon_deg": -64.32, "elev_m": 700.0}


@needs_data
def test_from_defaults_to_now_floored(client: TestClient) -> None:
    body = client.get("/v1/sky", params={**UNQUILLO, "hours": 1, "step_min": 15}).json()
    assert body["from"][14:16] in ("00", "15", "30", "45") and body["from"].endswith(":00Z")


@needs_data
@pytest.mark.parametrize(
    ("params", "param"),
    [
        ({"lon": 0}, "lat"),
        ({"lat": 90.5, "lon": 0}, "lat"),
        ({"lat": 0, "lon": -181}, "lon"),
        ({"lat": "nan", "lon": 0}, "lat"),
        ({"lat": 0, "lon": 0, "elev_m": 9001}, "elev_m"),
        ({"lat": 0, "lon": 0, "hours": 0}, "hours"),
        ({"lat": 0, "lon": 0, "hours": 169}, "hours"),
        ({"lat": 0, "lon": 0, "step_min": 61}, "step_min"),
        ({"lat": 0, "lon": 0, "hours": 168, "step_min": 4}, "step_min"),
        ({"lat": 0, "lon": 0, "from": "2026-11-16T00:00:00"}, "from"),
        ({"lat": 0, "lon": 0, "from": "2026-02-30T00:00:00Z"}, "from"),
        ({"lat": 0, "lon": 0, "from": "1849-12-31T00:00:00Z"}, "from"),
        ({"lat": 0, "lon": 0, "from": "2149-12-29T00:00:00Z", "hours": 25}, "from"),
    ],
)
def test_limits_give_422_problems(params: dict[str, Any], param: str, client: TestClient) -> None:
    r = client.get("/v1/sky", params=params)
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    validator("error.v1").validate(body)
    assert body["param"] == param and body["status"] == 422


@needs_data
def test_seasons_limits(client: TestClient) -> None:
    for year in (1849, 2150, "x"):
        r = client.get("/v1/seasons", params={"year": year})
        assert r.status_code == 422 and r.json()["param"] == "year"


def test_without_data_the_api_says_so(empty_dir: Path) -> None:
    client = TestClient(create_app(empty_dir))
    for path in ("/v1/sky?lat=0&lon=0", "/v1/stars", "/v1/seasons?year=2026"):
        r = client.get(path)
        assert r.status_code == 503
        validator("error.v1").validate(r.json())
        assert "fetch-data" in r.json()["detail"]
    r = client.get("/nowhere")
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"


@needs_data
def test_same_request_same_bytes(client: TestClient) -> None:
    for path, params in (("/v1/sky", SKY), ("/v1/stars", {}), ("/v1/seasons", {"year": 2026})):
        assert client.get(path, params=params).content == client.get(path, params=params).content


SCRIPT = """
import hashlib, sys
from pathlib import Path
from fastapi.testclient import TestClient
from origen.app import create_app
c = TestClient(create_app(Path(sys.argv[1])))
for url in sys.argv[2:]:
    print(hashlib.sha256(c.get(url).content).hexdigest())
"""


@needs_data
def test_same_bytes_in_another_process(client: TestClient) -> None:
    urls = [
        "/v1/sky?lat=-31.23&lon=-64.32&elev_m=700&from=2026-11-16T00:00:00Z",
        "/v1/stars",
        "/v1/seasons?year=2026",
    ]
    out = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(REAL_DATA), *urls],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == [hashlib.sha256(client.get(u).content).hexdigest() for u in urls]


@needs_data
def test_no_negative_zero_or_nan(client: TestClient) -> None:
    text = client.get("/v1/sky", params=SKY).text
    assert "-0.0," not in text and "NaN" not in text and "Infinity" not in text
