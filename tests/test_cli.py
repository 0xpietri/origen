from pathlib import Path

import pytest

from origen.cli import build_parser, main


def test_serve_defaults_to_the_local_port() -> None:
    args = build_parser().parse_args(["serve"])
    assert (args.host, args.port, args.reload) == ("127.0.0.1", 8800, False)


def test_check_data_fails_on_an_empty_folder(
    empty_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check-data", "--data-dir", str(empty_dir)]) == 1
    assert "de440s: missing" in capsys.readouterr().out


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit):
        main([])


def _serve_kwargs(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> dict[str, object]:
    import uvicorn

    seen: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: seen.update(kw))
    assert main(argv) == 0
    return seen


def test_reload_watches_only_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    # Watching the repo root makes the polling reloader stat all of .venv four times a second.
    kwargs = _serve_kwargs(monkeypatch, ["serve", "--reload"])
    assert kwargs["reload"] is True
    assert kwargs["reload_dirs"] == [str(Path(__file__).parents[1] / "src" / "origen")]


def test_serve_without_reload_watches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    kwargs = _serve_kwargs(monkeypatch, ["serve"])
    assert (kwargs["reload"], kwargs["reload_dirs"]) == (False, None)
