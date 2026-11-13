"""The coom command, its help, exit codes and the lint command."""

import json
from pathlib import Path

import pytest

from coom.cli import main, parser
from coom.cli._arguments import CommandParser

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"
CORE = CONFORMANCE / "CORE"


def run(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str, str]:
    code = main(list(arguments))
    out, err = capsys.readouterr()
    return code, out, err


def test_without_arguments_prints_the_overview(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys)
    assert code == 0
    for command in ("lint", "test", "show", "diff", "solve", "explain", "edit rename", "config apply"):
        assert f"  {command} " in out
    assert "coom lint" in out


def test_help_names_a_command(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "help", "config", "apply")
    assert code == 0
    assert out.startswith("usage: coom config apply")
    assert "examples:\n  coom config apply" in out


def test_help_suggests_the_nearest_command(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "help", "lnit")
    assert code == 2
    assert "did you mean lint?" in err


def test_help_all_lists_every_command_and_option(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "help", "--all")
    assert code == 0

    def check(command: CommandParser) -> None:
        assert f"usage: {command.prog}" in out
        for action in command._actions:
            for option in action.option_strings:
                assert option in out, f"{command.prog} {option}"
        for subcommand in command.commands.values():
            check(subcommand)

    for command in parser().commands.values():
        check(command)


def test_every_command_has_examples() -> None:
    for command in parser().leaves():
        assert command.examples, command.prog
        assert all(example.startswith(command.prog) for example in command.examples), command.prog


def test_usage_errors_exit_with_2_and_show_an_example(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "lint", "--unknown")
    assert code == 2
    assert err.startswith("usage: coom lint")
    assert "example: coom lint" in err


def test_commands_that_are_not_implemented_exit_with_2(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "explain", "kidsBike.color = Red")
    assert code == 2
    assert "not implemented" in err


def test_lint_accepts_a_valid_model(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, "lint", "-m", str(CORE / "KidsBike.model"))
    assert code == 0
    assert err == ""
    assert out == "no problems in 1 file\n"


def test_lint_discovers_the_sources_of_a_folder(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "lint", "-C", str(CORE))
    assert code == 0
    assert out == "no problems in 2 files\n"


def test_lint_refuses_a_folder_with_several_products(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "lint", "-C", str(CONFORMANCE / "N-OUT"))
    assert code == 2
    assert "found 4 products" in err
    assert "GearBike.model" in err


def test_lint_refuses_a_folder_without_sources(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "lint", "-C", str(tmp_path))
    assert code == 2
    assert "found no *.model or *.test files" in err


def test_lint_resolves_files_relative_to_the_folder(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = run(capsys, "lint", "-C", str(CORE), "-m", "KidsBike.model", "KidsBike.test")
    assert code == 0
    code, _, err = run(capsys, "lint", "-C", str(CORE), "-m", "Missing.model")
    assert code == 2
    assert "Missing.model does not exist" in err


def test_lint_reports_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    model = tmp_path / "Broken.model"
    model.write_text("product { Missing part }\n")
    code, out, err = run(capsys, "lint", "-C", str(tmp_path))
    assert code == 1
    assert f"{model}:1:11: error name: the type Missing is not defined" in err
    assert out == "1 error in 1 file\n"


@pytest.mark.parametrize("model", sorted((CONFORMANCE / "syntax" / "invalid").glob("*.model")), ids=lambda p: p.stem)
def test_lint_reports_syntax_errors(model: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "lint", "-m", str(model))
    assert code == 1
    assert f"{model}:" in err


def test_lint_writes_diagnostics_into_the_json_envelope(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "Broken.model").write_text("product { Missing part }\n")
    code, out, err = run(capsys, "lint", "-C", str(tmp_path), "--format", "json")
    assert code == 1
    assert err == ""
    envelope = json.loads(out)
    assert envelope["version"] == 1
    assert envelope["command"] == "lint"
    assert envelope["items"] == []
    [diagnostic] = envelope["diagnostics"]
    assert diagnostic["severity"] == "error"
    assert diagnostic["code"] == "name"
    assert diagnostic["location"]["line"] == 1
    assert diagnostic["location"]["column"] == 11


def test_lint_compiles_a_snippet_against_the_model(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "lint", "-C", str(CORE), "--snippet", "behavior KidsBike { require color = Red }")
    assert (code, out) == (0, "no problems in the snippet\n")
    code, out, err = run(capsys, "lint", "-C", str(CORE), "--snippet", "behavior KidsBike { require colour = Red }")
    assert code == 1
    assert err == "<snippet>:1:29: error name: KidsBike has no feature colour\n"
    assert out == "1 error in the snippet\n"


def test_lint_refuses_a_snippet_against_a_broken_model(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "Broken.model").write_text("product { Missing part }\n")
    code, _, err = run(capsys, "lint", "-C", str(tmp_path), "--snippet", "enumeration Color { Red }")
    assert code == 2
    assert "the model has 1 error" in err
