from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from origen import data

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from origen.sky.engine import Sky

REAL_DATA = data.default_data_dir()
FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def real_data_ok() -> bool:
    return all(state == "ok" for state in data.check(REAL_DATA).values())


needs_data = pytest.mark.skipif(
    not real_data_ok(),
    reason=f"data files not fetched into {REAL_DATA}: run `uv run origen fetch-data`",
)


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture(scope="session")
def client() -> TestClient:
    """The app over the real data files, shared by the tests that need them."""
    from fastapi.testclient import TestClient

    from origen.app import create_app

    return TestClient(create_app(REAL_DATA))


@pytest.fixture(scope="session")
def sky() -> Sky:
    from origen.sky.engine import Sky

    return Sky(REAL_DATA)
