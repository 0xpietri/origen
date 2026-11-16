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
