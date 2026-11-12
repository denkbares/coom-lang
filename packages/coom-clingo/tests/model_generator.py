"""Random small models and inputs for testing the solver against the brute force oracle."""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from coom.compiler import compile_text
from coom.configuration import Configuration, Instance
from coom.model import Model

_CARDINALITIES = ("0..1", "0..2", "1", "1..2")

_ROOT_CONDITIONS = (
    "color = A",
    "color != B",
    "flag",
    "flag = false",
    "!flag",
    "x > 3",
    "x <= y",
    "y = 4",
    "z",
    "!z",
    "z > 2",
    "count(parts) = 1",
    "sum(parts.n) > 4",
    "parts.size = small",
    "max(parts.n) > 2",
    "10 / x > 2",
    "parts[0].size = large",
    "x + y < 10",
    "x = 3",
    "y > x",
    "parts[0].n > 3",
    "f > 2.5",
    "x = f",
    "z + 1",
    "(10 / x) + y > 3",
)

_ROOT_FORMULAS = (
    "3",
    "y",
    "y + 1",
    "x * 2",
    "count(parts)",
    "sum(parts.size.w)",
    "sum(parts.n)",
    "max(parts.n)",
    "10 / y",
    "z + 1",
    "round(y / 3, 0)",
    "x",
    "z",
    "parts[0].n",
    "x - y",
    "f",
    "f * 2",
    "round(f, 0)",
    "(10 / x) + y",
)

_PART_CONDITIONS = ("size = small", "size != large", "n > 3", "n = 2")
_PART_FORMULAS = ("size.w", "4", "size.w + 1")


@dataclass(frozen=True, slots=True)
class Case:
    seed: int
    text: str
    model: Model
    inputs: Configuration | None


def case(seed: int) -> Case:
    """A random model that compiles, with random inputs, the same for the same seed."""
    generator = random.Random(seed)
    while True:
        text = _model(generator)
        result = compile_text(text)
        if result.ok:
            return Case(seed, text, result.model, _inputs(generator, result.model))


def _condition(generator: random.Random, atoms: tuple[str, ...]) -> str:
    first = generator.choice(atoms)
    match generator.randrange(5):
        case 0:
            return f"{first} && {generator.choice(atoms)}"
        case 1:
            return f"{first} || {generator.choice(atoms)}"
        case 2:
            return f"!({first})"
        case _:
            return first


def _root_statement(generator: random.Random) -> list[str]:
    target = generator.choice(("x", "y", "z", "f"))
    formula = generator.choice(_ROOT_FORMULAS)
    condition = _condition(generator, _ROOT_CONDITIONS)
    match generator.randrange(7):
        case 0:
            return [f"require {condition}"]
        case 1:
            return [f"condition {condition}", f"imply {target} = {formula}"]
        case 2:
            return [f"imply {target} = {formula}"]
        case 3:
            return [f"require {target} = {formula}"]
        case 4:
            value = generator.choice(("color = A", "color = B", "flag = true", "flag = false"))
            return [f"condition {condition}", f"imply {value}"]
        case 5:
            rows = [
                f"allow ({generator.choice(('A', 'B', '(A,B)'))} {generator.choice(('true', 'false'))})"
                for _ in range(generator.randrange(1, 3))
            ]
            return ["combinations (color flag)", *rows]
        case _:
            return [f"default {target} = {formula}"]


def _part_statement(generator: random.Random) -> list[str]:
    condition = generator.choice(_PART_CONDITIONS)
    match generator.randrange(4):
        case 0:
            return [f"imply n = {generator.choice(_PART_FORMULAS)}"]
        case 1:
            return [f"condition {condition}", "require n < 3"]
        case 2:
            return [f"require n = {generator.choice(_PART_FORMULAS)}"]
        case _:
            return [f"condition {condition}", "imply size = large"]


def _model(generator: random.Random) -> str:
    blocks = []
    for _ in range(generator.randrange(1, 6)):
        blocks.append(("Root", _root_statement(generator)))
    for _ in range(generator.randrange(0, 2)):
        blocks.append(("Part", _part_statement(generator)))
    behaviors = "\n".join(
        f"behavior {origin} {{\n" + "".join(f"    {line}\n" for line in lines) + "}" for origin, lines in blocks
    )
    return f"""
product {{ Root root }}
structure Root {{
    Color color
    bool flag
    {generator.choice(_CARDINALITIES)} Part parts
    num 0-20 x
    num 0-20 y
    0..1 num 0-20 z
    num.# 0-20 f
}}
structure Part {{
    Size size
    num 0-20 n
}}
enumeration Color {{ A; B }}
enumeration Size {{
    attribute num w
    small = (2)
    large = (5)
}}
{behaviors}
"""


def _inputs(generator: random.Random, model: Model) -> Configuration | None:
    if generator.randrange(3) == 0:
        return None
    configuration = Configuration(model)
    configuration.add_required()
    root = configuration.root.get("root")
    assert isinstance(root, Instance)
    for _ in range(generator.randrange(1, 4)):
        match generator.randrange(6):
            case 0:
                root.set(generator.choice(("x", "y", "z")), generator.randrange(0, 8))
            case 5:
                root.set("f", Decimal(generator.randrange(0, 80)) / 10)
            case 1:
                root.set("color", generator.choice(("A", "B")))
            case 2:
                root.set("flag", generator.choice((True, False)))
            case 3:
                feature = model.structure("Root").feature("parts")
                if feature.max is not None and root.last_index(feature) + 1 < feature.max:
                    root.add(feature)
            case _:
                root.set("x", 0)
    return configuration
