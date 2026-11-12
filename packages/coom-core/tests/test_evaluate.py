"""Truth of conditions and behaviors in configurations, with missing values, faults, precision and collections."""

from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

import pytest

from coom.compiler import compile, compile_files, compile_text
from coom.configuration import Configuration, Instance
from coom.configuration.evaluate import Result, Sequence, Truth, Undefined, all_of, any_of, evaluate, truth, verdicts
from coom.model import AttributeStep, FeatureStep, Model, PathAccess
from coom.model import Path as ModelPath
from coom.parser import parse

MODEL = """
product { Bike bike }
structure Bike {
    Color color
    0..4 Bag bags
    2 Wheel wheels
    num.## 0-1000 price
    num.#### 0-1000 exact
    num 0-100 count
    0..1 num 0-100 extra
    bool stand
    0..1 string note
}
structure Bag { Size size }
structure Wheel { num 10-30 inch }
enumeration Color { Red; Green; Blue }
enumeration Size {
    attribute num volume
    small = (1)
    large = (5)
}
"""

T, F, OPEN, INDEFINITE = Truth.TRUE, Truth.FALSE, Truth.OPEN, Truth.INDEFINITE

type Setup = Callable[[Instance], object]


def configure(bike: Instance) -> None:
    """A bike with every required value, a small and a large bag, and wheels of 20 and 24 inch."""
    bike.set("color", "Red")
    bike.set("price", "10.50")
    bike.set("exact", "10.4999")
    bike.set("count", 2)
    bike.set("stand", True)
    for size in ("small", "large"):
        bag = bike.add("bags")
        assert isinstance(bag, Instance)
        bag.set("size", size)
    for wheel, inch in zip(bike.values("wheels"), (20, 24), strict=True):
        assert isinstance(wheel, Instance)
        wheel.set("inch", inch)


def bike_after(setup: Setup, model: Model) -> Instance:
    configuration = Configuration(model)
    configuration.add_required()
    bike = configuration["bike"]
    assert isinstance(bike, Instance)
    configure(bike)
    setup(bike)
    return bike


def holds(statement: str, setup: Setup = lambda bike: None) -> Truth:
    """The truth of a single behavior of Bike in the configured bike after the setup."""
    result = compile(parse(MODEL + f"behavior Bike {{\n{statement}\n}}"), checks=False)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    [behavior] = result.model.behaviors
    return truth(behavior, bike_after(setup, result.model))


def test_truth_sets_combine_pointwise() -> None:
    assert OPEN.negate() == OPEN and INDEFINITE.negate() == INDEFINITE
    assert OPEN.both(INDEFINITE) == F | INDEFINITE
    assert F.both(INDEFINITE) == F and T.either(INDEFINITE) == T
    assert all_of([]) == T and any_of([]) == F
    assert all_of([T, OPEN]) == OPEN and any_of([F, OPEN, T]) == T


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("require price = 10.5", T),
        ("require count = 2.4", T),
        ("require count = 2.5", F),
        ("require price = exact", T),
        ("require round(exact, exact) = 10.4999", T),
        ("require exact = 10.4999", T),
        ("require price + 0 = 10.504", F),
        ("require 0.1 + 0.2 = 0.3", T),
        ("require (1 / 3) * 3 = 1", T),
        ("require price = count * 5.249", T),
        ("require round(price * 1.19, 2) = 12.5", T),
        ("require price > exact", F),
        ("require price >= exact", T),
    ],
)
def test_comparisons_are_decided_at_the_lowest_precision(statement: str, expected: Truth) -> None:
    assert holds(statement) == expected


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("require extra > 1", OPEN),
        ("require !(extra > 1)", OPEN),
        ("require extra > 1 || count = 2", T),
        ("require extra > 1 && count = 3", F),
        ("condition extra > 1 require count = 3", OPEN),
        ("condition extra > 1 require count = 2", T),
        ("require extra", F),
        ("require note", F),
        ("require !note", T),
        ("require stand", T),
    ],
)
def test_missing_values(statement: str, expected: Truth) -> None:
    assert holds(statement) == expected


def test_required_values_that_are_missing_are_open() -> None:
    assert holds("require price > 1", lambda bike: bike.remove("price")) == OPEN
    assert holds("require price", lambda bike: bike.remove("price")) == OPEN
    assert holds("require stand", lambda bike: bike.set("stand", False)) == F
    assert holds("require note", lambda bike: bike.set("note", "  ")) == F


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("require 1 / (count - 2) > 5", INDEFINITE),
        ("require !(1 / (count - 2) > 5)", INDEFINITE),
        ("require 1 / (count - 2) > 5 && extra > 1", F | INDEFINITE),
        ("require 1 / (count - 2) > 5 || count = 2", T),
        ("condition 1 / (count - 2) > 5 require count = 3", T),
        ("imply price = 1 / (count - 2)", F),
        ("default price = 1 / (count - 2)", T),
        ("require sqrt(-count) = 1", INDEFINITE),
        ("require tan(45 * count) = 1", INDEFINITE),
    ],
)
def test_faults(statement: str, expected: Truth) -> None:
    assert holds(statement) == expected


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("require bags.size = small", F),
        ("require bags.size != Size.large || count = 2", T),
        ("require bags.size.volume <= 5", T),
        ("require bags[last].size = large", T),
        ("require bags[last-1].size = small", T),
        ("require bags[3].size = small", OPEN),
        ("require count(bags) = 2", T),
        ("require sum(bags.size.volume) = 6", T),
        ("require min(bags.size) = small && max(bags.size) = large", T),
        ("require max(wheels.inch) - min(wheels.inch) = 4", T),
        ("require sum(wheels.inch) = 44", T),
    ],
)
def test_collections(statement: str, expected: Truth) -> None:
    assert holds(statement) == expected


def test_empty_and_incomplete_collections() -> None:
    def no_bags(bike: Instance) -> None:
        bike.remove("bags", 0)
        bike.remove("bags", 1)

    def unknown_wheel(bike: Instance) -> None:
        wheel = bike.get("wheels", 1)
        assert isinstance(wheel, Instance)
        wheel.remove("inch")

    assert holds("require bags.size = small", no_bags) == T
    assert holds("require count(bags) = 0 && sum(bags.size.volume) = 0", no_bags) == T
    assert holds("require min(bags.size) = small", no_bags) == OPEN
    assert holds("require wheels.inch > 20", unknown_wheel) == F
    assert holds("require wheels.inch >= 20", unknown_wheel) == OPEN
    assert holds("require sum(wheels.inch) > 0", unknown_wheel) == OPEN


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("imply price = 10.5", T),
        ("imply price = 3 * 3.5", T),
        ("imply price = 10.49", F),
        ("condition color = Blue imply price = 1", T),
        ("default price = 1", F),
        ("default/7 color = Red", T),
        ("imply bags.size = small", F),
        ("imply wheels.inch = max(wheels.inch)", F),
    ],
)
def test_assignments(statement: str, expected: Truth) -> None:
    assert holds(statement) == expected


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ("allow (Red true)", T),
        ("allow ((Green, Blue) -*-)\nallow (-*- false)", F),
        ("forbid (Red true)", F),
        ("forbid (Blue -*-)", T),
        ("allow (Red <15)", T),
    ],
)
def test_combinations(rows: str, expected: Truth) -> None:
    columns = "(color price)" if "<" in rows else "(color stand)"
    assert holds(f"combinations {columns}\n{rows}") == expected


def test_ordering_of_options_and_texts() -> None:
    assert holds("require color < Blue && color >= Red") == T
    assert holds('require note < "a10" && note > "a9"', lambda bike: bike.set("note", "a9x")) == T


def test_formula_values() -> None:
    model = compile_text(MODEL).model
    bike = bike_after(lambda bike: bike.remove("bags", 1), model)
    size, volume = model.structure("Bag").feature("size"), model.enumeration("Size").attribute("volume")
    volumes = ModelPath(bike.type, (FeatureStep(bike.type.feature("bags")), FeatureStep(size), AttributeStep(volume)))
    assert evaluate(PathAccess(volumes), bike) == Sequence((Fraction(1),))
    assert value_of(bike, "extra") is Undefined.ABSENT
    bike.remove("price")
    assert value_of(bike, "price") is Undefined.OPEN


def value_of(bike: Instance, feature: str) -> Result:
    return evaluate(PathAccess(ModelPath(bike.type, (FeatureStep(bike.type.feature(feature)),))), bike)


def test_verdicts_cover_every_instance_of_the_origin() -> None:
    result = compile_text(MODEL + "behavior Wheel { require inch >= 20 }\nbehavior Bike { default count = 3 }")
    bike = bike_after(lambda bike: None, result.model)
    found = list(verdicts(bike.configuration))
    assert [(v.instance.path, v.truth, v.is_hard) for v in found] == [
        ("bike.wheels[0]", T, True),
        ("bike.wheels[1]", T, True),
        ("bike", F, False),
    ]


PROFILES = Path(__file__).parents[3] / "spec" / "conformance"


@pytest.mark.parametrize("path", sorted(PROFILES.glob("*/*.model")), ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_profile_models_evaluate_in_their_initial_configuration(path: Path) -> None:
    result = compile_files([path])
    if not result.ok:
        pytest.skip("the model does not compile")
    configuration = Configuration(result.model)
    configuration.add_required()
    for verdict in verdicts(configuration):
        assert verdict.truth
