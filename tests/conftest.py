from pathlib import Path

import pytest

from origen import data

REAL_DATA = data.default_data_dir()


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
