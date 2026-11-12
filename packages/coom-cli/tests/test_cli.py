"""The coom command on valid and invalid models."""

from pathlib import Path

import pytest

from coom.cli import main

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"


def test_check_accepts_a_valid_model(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(CONFORMANCE / "CORE" / "KidsBike.model")]) == 0
    assert capsys.readouterr().err == ""


def test_check_reports_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    model = tmp_path / "Broken.model"
    model.write_text("product { Missing part }\n")
    assert main(["check", str(model)]) == 1
    assert "Broken.model:1:" in capsys.readouterr().err
