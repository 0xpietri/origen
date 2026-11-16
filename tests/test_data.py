import hashlib
from pathlib import Path

import pytest

from origen import data


def make_source(tmp_path: Path, name: str, content: bytes) -> str:
    src = tmp_path / "src" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(content)
    return src.as_uri()


def file_for(content: bytes, *urls: str) -> data.DataFile:
    return data.DataFile(
        key="sample",
        path="sample/file.bin",
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        urls=urls,
        source="test",
    )


def quiet(_: str) -> None:
    pass


def test_fetch_downloads_and_checks(tmp_path: Path, empty_dir: Path) -> None:
    content = b"sky" * 1000
    f = file_for(content, make_source(tmp_path, "a", content))
    assert data.status_of(empty_dir, f) == "missing"
    assert data.fetch_one(empty_dir, f, log=quiet) == "fetched"
    assert (empty_dir / f.path).read_bytes() == content
    assert data.status_of(empty_dir, f) == "ok"
    # A file already in place and intact is not downloaded again.
    assert data.fetch_one(empty_dir, f, log=quiet) == "present"


def test_falls_back_to_the_mirror(tmp_path: Path, empty_dir: Path) -> None:
    content = b"stars"
    broken = (tmp_path / "nowhere").as_uri()
    f = file_for(content, broken, make_source(tmp_path, "mirror", content))
    assert data.fetch_one(empty_dir, f, log=quiet) == "fetched"
    assert (empty_dir / f.path).read_bytes() == content


def test_wrong_checksum_is_refused_and_leaves_nothing(tmp_path: Path, empty_dir: Path) -> None:
    f = file_for(b"the real bytes", make_source(tmp_path, "a", b"other bytes!!!"))
    with pytest.raises(data.FetchError, match="SHA-256"):
        data.fetch_one(empty_dir, f, log=quiet)
    assert list((empty_dir / "sample").iterdir()) == []


def test_wrong_size_is_refused(tmp_path: Path, empty_dir: Path) -> None:
    f = file_for(b"four", make_source(tmp_path, "a", b"forty-two bytes, more than four"))
    with pytest.raises(data.FetchError, match="bytes"):
        data.fetch_one(empty_dir, f, log=quiet)
    assert data.status_of(empty_dir, f) == "missing"


def test_a_damaged_file_is_replaced(tmp_path: Path, empty_dir: Path) -> None:
    content = b"ephemeris"
    f = file_for(content, make_source(tmp_path, "a", content))
    target = empty_dir / f.path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"ephemeriz")
    assert data.status_of(empty_dir, f) == "bad"
    assert data.fetch_one(empty_dir, f, log=quiet) == "fetched"
    assert target.read_bytes() == content


def test_pinned_files_are_well_formed() -> None:
    keys = [f.key for f in data.FILES]
    assert keys == ["de440s", "hipparcos", "iau_names"]
    for f in data.FILES:
        assert len(f.sha256) == 64 and int(f.sha256, 16) >= 0
        assert f.size > 0
        assert f.urls and all(u.startswith("https://") for u in f.urls)
        assert not Path(f.path).is_absolute()


def test_main_reports_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = file_for(b"x", (tmp_path / "nowhere").as_uri())
    monkeypatch.setattr(data, "FILES", (f,))
    monkeypatch.setattr(data, "fetch", lambda d: data.fetch_one(d, f, log=quiet))
    assert data.main([str(tmp_path / "d")]) == 1
