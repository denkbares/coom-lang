"""The show command, its views and formats, and the JSON schema of models."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from coom.cli import main
from coom.compiler import compile, compile_text
from coom.model.json import write_model
from coom.parser import parse

ROOT = Path(__file__).resolve().parents[3]
CONFORMANCE = ROOT / "spec" / "conformance"
SCHEMA = json.loads((ROOT / "spec" / "schema" / "model.schema.json").read_text())
ENTITY_SCHEMA = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": "#/$defs/entity"}
CORE = CONFORMANCE / "CORE"
KINDS = ("structure", "feature", "enumeration", "attribute", "option", "behavior", "test")
MODELS = sorted(path for path in CONFORMANCE.rglob("*.model") if "syntax" not in path.relative_to(CONFORMANCE).parts)


def run(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str, str]:
    code = main(list(arguments))
    out, err = capsys.readouterr()
    return code, out, err


def sources(model: Path) -> list[str]:
    """Returns the arguments that name a conformance model together with its tests."""
    test = model.with_suffix(".test")
    return ["-C", str(model.parent), "-m", model.name, *([test.name] if test.exists() else [])]


def test_without_selector_shows_the_product_tree(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE))
    assert code == 0
    assert out == (
        ":root\n"
        "  :root.kidsBike  KidsBike\n"
        "    KidsBike.color  Color\n"
        "    KidsBike.supportWheels  bool\n"
        "    KidsBike.wheelSize  Wheel\n"
    )
    code, out, _ = run(capsys, "show", "-C", str(CORE), "--depth", "1")
    assert out == ":root\n  :root.kidsBike  KidsBike\n"


def test_one_match_shows_the_detail(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE), "KidsBike.color")
    assert code == 0
    assert out == (
        "KidsBike.color\n"
        "  kind      feature\n"
        "  type      Color\n"
        "  options   Color.Red, Color.Yellow\n"
        f"  location  {CORE / 'KidsBike.model'}:6:5\n"
        "    structure KidsBike {\n"
        "        Color color\n"
        "    }\n"
    )


def test_behaviors_and_tests_are_selected_by_location(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE), "@KidsBike.test:5")
    assert code == 0
    assert out.startswith("@KidsBike.test:3\n  kind      test\n  origin    :root\n")
    assert "        isEmpty kidsBike.supportWheels\n" in out


def test_several_matches_show_a_list(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE), "KidsBike.*", "--kind", "feature")
    assert code == 0
    model = CORE / "KidsBike.model"
    assert out == (
        f"feature  KidsBike.color          {model}:6:5\n"
        f"feature  KidsBike.supportWheels  {model}:7:5\n"
        f"feature  KidsBike.wheelSize      {model}:8:5\n"
    )


def test_kinds_select_from_the_whole_model(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE), "--kind", "test", "--limit", "2")
    assert code == 0
    lines = out.splitlines()
    assert [line.split()[1] for line in lines[:2]] == ["@KidsBike.test:3", "@KidsBike.test:11"]
    assert lines[2] == "showing 2 of 6 entities, use --limit N for more or --limit 0 for all"


def test_unknown_names_and_kinds_exit_with_2(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "show", "-C", str(CORE), "Kidsbike.color")
    assert code == 2
    assert err == "unknown item Kidsbike.color, did you mean KidsBike.color or KidsBike?\n"
    code, _, err = run(capsys, "show", "-C", str(CORE), "--kind", "tset")
    assert code == 2
    assert "did you mean test?" in err


def test_empty_results_are_explicit(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE), "Bike.*")
    assert (code, out) == (1, "nothing matches Bike.*\n")
    code, out, _ = run(capsys, "show", "-C", str(CORE), "KidsBike.*", "--kind", "option")
    assert (code, out) == (1, "nothing of kind option matches KidsBike.*\n")
    code, out, _ = run(capsys, "show", "-C", str(CORE), "Bike.*", "--format", "json")
    assert code == 1
    assert json.loads(out)["items"] == []


def test_a_model_with_errors_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "Broken.model").write_text("product { Missing part }\n")
    code, _, err = run(capsys, "show", "-C", str(tmp_path))
    assert code == 2
    assert "the model has 1 error, run coom lint" in err


def test_coom_format_writes_the_selection(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", "-C", str(CORE), "Color.Red", "KidsBike.color", "--format", "coom")
    assert code == 0
    assert out == "structure KidsBike {\n    Color color\n}\n\nenumeration Color { Red }\n"


@pytest.mark.parametrize("model", MODELS, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_every_printed_name_is_accepted_again(model: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", *sources(model), "--view", "list", "--limit", "0", "--kind", ",".join(KINDS))
    assert code == 0
    names = [line.split()[1] for line in out.splitlines()]
    code, tree, _ = run(capsys, "show", *sources(model))
    assert code == 0
    names += [line.split()[0] for line in tree.splitlines()]
    code, again, err = run(capsys, "show", *names, *sources(model), "--view", "list", "--limit", "0")
    assert code == 0, err
    assert again == out


@pytest.mark.parametrize("model", MODELS, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_json_conforms_to_the_schema(model: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "show", *sources(model), "--format", "json")
    assert code == 0
    items: list[dict[str, Any]] = json.loads(out)["items"]
    for item in items:
        jsonschema.validate(item, ENTITY_SCHEMA)
    files = [model, *([model.with_suffix(".test")] if model.with_suffix(".test").exists() else [])]
    whole = write_model(compile(*(parse(file.read_text(), source=str(file)) for file in files)).model)
    jsonschema.validate(whole, SCHEMA)
    assert items == [whole["root"], *whole["structures"], *whole["enumerations"], *whole["behaviors"], *whole["tests"]]


def test_json_selection_has_the_objects_of_the_whole_model(capsys: pytest.CaptureFixture[str]) -> None:
    _, whole, _ = run(capsys, "show", "-C", str(CORE), "--format", "json")
    _, selected, _ = run(capsys, "show", "-C", str(CORE), "KidsBike.color", "Color", "--format", "json")
    items = {item["name"]: item for item in json.loads(whole)["items"]}
    assert json.loads(selected)["items"] == [items["KidsBike"]["features"][0], items["Color"]]


def test_schema_rejects_unknown_fields() -> None:
    model = write_model(compile_text("product { bool stand }").model)
    jsonschema.validate(model, SCHEMA)
    model["root"]["features"][0]["colour"] = "Red"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(model, SCHEMA)
