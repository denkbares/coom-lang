"""Writing models as text that compiles back to an equal model."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from coom.compiler import compile_text
from coom.model import Attribute, Enumeration, Feature, Model, Option, Structure
from coom.writer import write

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"
MODELS = sorted(path for path in CONFORMANCE.rglob("*.model") if "syntax" not in path.relative_to(CONFORMANCE).parts)


def plain(value: Any, declaration: bool = False) -> Any:
    """Returns the content of a model part as nested tuples, with references to named items replaced by names."""
    if isinstance(value, Structure | Enumeration) and not declaration:
        return value.name
    if isinstance(value, Feature | Attribute | Option) and not declaration:
        return value.qualified_name
    if isinstance(value, tuple | list):
        return tuple(plain(item, declaration) for item in value)
    if isinstance(value, Mapping):
        return tuple((plain(key), plain(item)) for key, item in value.items())
    if is_dataclass(value) and not isinstance(value, type):
        members = isinstance(value, Structure | Enumeration)
        return (
            type(value).__name__,
            *(
                (field.name, plain(getattr(value, field.name), members))
                for field in fields(value)
                if field.compare and field.name not in ("span", "owner") and not field.name.startswith("_")
            ),
        )
    return value


def content(model: Model) -> Any:
    return plain((model.root, *model.structures, *model.enumerations), True), plain((model.behaviors, model.tests))


def round_trip(text: str) -> str:
    """Asserts that the written model compiles to an equal one and is written again unchanged."""
    original = compile_text(text)
    assert original.ok, "\n".join(map(str, original.diagnostics))
    written = write(original.model)
    result = compile_text(written)
    assert result.ok, written + "\n".join(map(str, result.diagnostics))
    assert content(result.model) == content(original.model), written
    assert write(result.model) == written
    return written


@pytest.mark.parametrize("path", MODELS, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_conformance_models_round_trip(path: Path) -> None:
    round_trip(path.read_text())


BIKE = """
product { Bike bike }
structure Bike {
    Color color
    0..4 Bag bags
    2 Bag spares
    1..* Bag extras
    num.## /kg -10.5-100 weight
    num /'m/s' *-0 speed
    bool stand
    string note
    Color Red
    Size Size
    num root
}
structure Bag { Size size }
enumeration Color { Red; Blue; 'light green' }
enumeration Size {
    attribute num volume
    attribute Color tint
    attribute string label
    attribute bool open
    small = (1.5 Red "it's \\"small\\"" true)
    large = (-5 'light green' "" false)
}
"""


def test_declarations() -> None:
    written = round_trip(BIKE)
    assert "num.## /kg -10.5-100 weight" in written
    assert "num /'m/s' *-0" in written
    assert "1..* Bag" in written


def test_formulas_keep_their_grouping() -> None:
    round_trip(
        BIKE + "behavior Bike {\n"
        " require weight = (1 - 2) - 3 - (4 - 5)\n"
        " require weight = 2 * (3 + 4) / (5 * 6)\n"
        " require weight = -(2 + 3) + -this.root\n"
        " require weight = (-2) ^ 3 ^ 4 + (2 ^ 3) ^ 4\n"
        " require weight = -2 ^ 2 + -sqrt(4)\n"
        " require weight = max(bags.size.volume, 3) + sum(bags[last-1..last].size.volume)\n"
        "}"
    )


def test_conditions_keep_their_grouping() -> None:
    written = round_trip(
        BIKE + "behavior Bike {\n"
        " require stand || note && (stand || color = Red) && 1 < weight <= 5\n"
        " require !(stand || note) && !stand && !(color = Blue) && !!true\n"
        " require (stand && note) && stand || (stand || note)\n"
        " require (weight + 1) * 2 > 0\n"
        "}"
    )
    assert "1 < weight && weight <= 5" in written


def test_names_that_would_denote_something_else() -> None:
    written = round_trip(
        BIKE + "behavior Bike {\n"
        " require color = this.Red\n"
        " require Red = color\n"
        " require this.root > 1\n"
        " require this.Size.volume > 1\n"
        " require Size.small.volume < weight\n"
        ' require note = "Red" || note = "it\'s"\n'
        " imply color = Blue\n"
        " imply bags[0].size = Size.large\n"
        " imply Red = 'light green'\n"
        "}"
    )
    assert "require color = this.Red" in written
    assert "require Red = color" in written
    assert "require this.root > 1" in written
    assert "require weight > 1.5" not in written and "1.5 < weight" in written
    assert "imply Red = 'light green'" in written


def test_statements_and_shared_conditions() -> None:
    written = round_trip(
        BIKE + "behavior Bike {\n"
        ' explanation "parked" condition stand {\n'
        '  condition color = Red { require weight > 1\n imply note = "a" }\n'
        "  default/2 weight = 3\n"
        '  explanation "other" require note\n'
        " }\n"
        " condition note default color = Blue\n"
        " minimize weight\n"
        " hide color Red 'light green'\n"
        " readonly note\n"
        " combinations (color, bags[0].size, weight)\n"
        "  allow (Red, -*-, 1)\n"
        "  forbid ((Red, Blue), (small), (< 2, >= -3))\n"
        " require (weight) condition (color)\n  (1) (Red)\n  (2) (-*-)\n"
        "}\n"
        "behavior { require bike.stand }\n"
        "behavior Bag { require size = small }"
    )
    assert 'explanation "parked" condition stand {' in written
    assert written.count("parked") == 1 and 'explanation "other" require note' in written
    assert "behavior {" in written


def test_tests() -> None:
    written = round_trip(
        BIKE + "test Bike {\n"
        ' set color = Red\n set weight = -1.5\n set note = "x"\n set stand\n'
        " remove color\n reset weight\n isFixed color = Blue\n isShown stand = true\n isShown note\n"
        " isEmpty bags\n isAvailable bags[0].size = small\n isBlocked color = 'light green'\n"
        " set this.Red = Color.Blue\n"
        "}\n"
        "test { isEmpty bike.bags }"
    )
    assert "set Red = Blue" in written
