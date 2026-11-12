"""The reference solver on small models, with every solved configuration checked by the evaluation oracle."""

from decimal import Decimal
from pathlib import Path

import pytest

from coom.clingo.solver import ClingoSolver, ClingoSolverError
from coom.clingo.testrun import Status, run_tests
from coom.compiler import compile_files, compile_text
from coom.configuration import Configuration, Instance, Role, verdicts
from coom.diagnostics import Severity
from coom.model import Model, Option

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"
MODELS = sorted(path for path in CONFORMANCE.rglob("*.model") if "syntax" not in path.relative_to(CONFORMANCE).parts)


def model_of(text: str) -> Model:
    result = compile_text(text)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    return result.model


def solve(model: Model, configuration: Configuration | None = None) -> Configuration | None:
    solved = ClingoSolver(model).solve(configuration)
    if solved is not None:
        assert_valid(solved)
    return solved


def assert_valid(configuration: Configuration) -> None:
    broken = [verdict for verdict in verdicts(configuration) if verdict.is_hard and not verdict.truth.may_be_true]
    assert not broken, broken


def inputs(model: Model, **values: object) -> Configuration:
    """A configuration of the product's single structure feature with the given values selected."""
    configuration = Configuration(model)
    configuration.add_required()
    part = configuration.root.values(model.root.features[0])[0]
    assert isinstance(part, Instance)
    for name, value in values.items():
        part.set(name, value)  # type: ignore[arg-type]
    return configuration


def part(configuration: Configuration) -> Instance:
    value = configuration.root.values(configuration.model.root.features[0])[0]
    assert isinstance(value, Instance)
    return value


def names(values: frozenset[object]) -> set[object]:
    return {getattr(value, "name", value) for value in values}


@pytest.mark.parametrize("path", MODELS, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_conformance_model_solves(path: Path) -> None:
    assert solve(compile_files([path]).model) is not None


# Discrete reasoning

KIDS_BIKE = (CONFORMANCE / "CORE" / "KidsBike.model").read_text()


def test_feasible_follows_tables_and_conditions() -> None:
    model = model_of(KIDS_BIKE)
    solver = ClingoSolver(model)
    assert names(solver.feasible(inputs(model, color="Yellow"), "kidsBike.wheelSize")) == {"W18", "W20"}
    assert names(solver.feasible(inputs(model, supportWheels=True), "kidsBike.wheelSize")) == {"W14", "W16"}
    assert solver.feasible(inputs(model, color="Yellow"), "kidsBike.supportWheels") == {False}


def test_inputs_without_completion_are_refused() -> None:
    model = model_of(KIDS_BIKE)
    assert solve(model, inputs(model, color="Yellow", supportWheels=True)) is None
    solved = solve(model, inputs(model, color="Yellow"))
    assert solved is not None
    assert part(solved).assignment("color").role is Role.SELECTED  # type: ignore[union-attr]


def test_instances_follow_cardinalities() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike { 1..3 Bag bags }
structure Bag { Color color }
enumeration Color { Red; Green }
behavior Bike {
    require count(bags) = 3
    require bags.color = Green
}
"""
    )
    solved = solve(model)
    assert solved is not None
    bags = part(solved).values("bags")
    assert len(bags) == 3
    assert all(isinstance(bag, Instance) and bag.get("color").name == "Green" for bag in bags)  # type: ignore[union-attr]


def test_unbounded_cardinalities_are_rejected() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike { 0..* Bag bags }
structure Bag { bool big }
"""
    )
    with pytest.raises(ClingoSolverError, match="bounded cardinality"):
        ClingoSolver(model)


# Numbers


def test_implications_compute_values() -> None:
    solved = solve(compile_files([CONFORMANCE / "N-OUT" / "WeightyBike.model"]).model)
    assert solved is not None
    weights = part(solved).get("weights")
    assert isinstance(weights, Instance)
    wheel = part(solved).get("wheelSize")
    assert isinstance(wheel, Option)
    weight = wheel.value("weight")
    assert isinstance(weight, Decimal)
    assert weights.get("totalWeight") == 10000 + 2 * weight


def test_transcendental_values_restrict_options() -> None:
    model = compile_files([CONFORMANCE / "N-FULL" / "SundayBike.model"]).model
    solver = ClingoSolver(model)
    # without defaults the geometry stays open and nothing is excluded
    assert names(solver.feasible(None, "sundayBike.topTubeBag")) == {"short", "middle", "long"}
    geometry = inputs(model, reach=470, stack=600, seatTubeAngle=73)
    assert names(solver.feasible(geometry, "sundayBike.topTubeBag")) == {"short", "middle"}
    solved = solver.solve()
    assert solved is not None
    assert part(solved).get("effectiveTopTubeLength") == Decimal(653)
    assert part(solved).assignment("reach").role is Role.DEFAULT  # type: ignore[union-attr]


def test_numeric_inputs_narrow_options() -> None:
    model = compile_files([CONFORMANCE / "N-LIN" / "ComfortBike.model"]).model
    solver = ClingoSolver(model)
    assert names(solver.feasible(inputs(model, riderWeight=115), "comfortBike.suspension")) == {"s2"}
    assert not solver.satisfiable(inputs(model, riderWeight=130))


def test_requires_determine_bare_paths() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num a
    num b
    num total
}
behavior Bike {
    require total = a + b
}
"""
    )
    solved = solve(model, inputs(model, a=2, b=3))
    assert solved is not None
    assert part(solved).get("total") == 5
    assert solve(model, inputs(model, a=2, b=3, total=6)) is None


def test_values_stay_open_without_producer() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num a
    num b
}
behavior Bike {
    imply a = b
    imply b = a
}
"""
    )
    solved = solve(model)
    assert solved is not None
    assert part(solved).get("a") is None and part(solved).get("b") is None
    seeded = solve(model, inputs(model, a=3))
    assert seeded is not None
    assert part(seeded).get("b") == 3


def test_values_do_not_justify_their_own_guard() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike { num x }
behavior Bike {
    condition x > 0
    imply x = 1
}
"""
    )
    solved = solve(model)
    assert solved is not None
    assert part(solved).get("x") is None


def test_open_operands_do_not_lend_support_to_guards() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    0..1 Bag bag
    num x
    0..1 num z
}
structure Bag { Size size }
enumeration Size { small; large }
behavior Bike {
    condition bag.size = small || z > 2
    imply z = x
}
"""
    )
    found = ClingoSolver(model).enumerate(inputs(model, x=4))
    without_bag = [configuration for configuration in found if part(configuration).get("bag") is None]
    assert without_bag
    assert all(part(configuration).get("z") is None for configuration in without_bag)


def test_guards_do_not_rest_on_the_absence_of_what_they_produce() -> None:
    # without z the guard holds through !z, with z only through z, which the guard produces itself
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num y
    0..1 num z
}
behavior Bike {
    condition z || !z
    imply y = 3
}
behavior Bike {
    imply z = y
}
"""
    )
    assert not ClingoSolver(model).satisfiable()


def test_conflicting_writers_exclude_their_guards() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num x
    Mode mode
}
enumeration Mode { A; B }
behavior Bike {
    imply x = 2
    condition mode = A
    imply x = 1
}
"""
    )
    assert names(ClingoSolver(model).feasible(None, "bike.mode")) == {"B"}


def test_ranges_are_constraints() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num 0-10 x
    Size size
}
enumeration Size {
    attribute num factor
    small = (2)
    large = (20)
}
behavior Bike {
    imply x = size.factor
}
"""
    )
    assert names(ClingoSolver(model).feasible(None, "bike.size")) == {"small"}


def test_faulting_requirement_fails() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num n
    num x
}
behavior Bike {
    require (100 / n > 5) && x > 3
}
"""
    )
    assert solve(model, inputs(model, n=0)) is None
    assert solve(model, inputs(model, n=10)) is not None


def test_faults_are_indefinite_while_other_operands_are_open() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num n
    num x
}
behavior Bike {
    require (1 / n) > x
}
"""
    )
    assert solve(model, inputs(model, n=0)) is None
    assert solve(model, inputs(model, n=1)) is not None


def test_aggregates_over_nothing_leave_their_target_open() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    0..2 Bag bags
    num heaviest
}
structure Bag { num weight }
behavior Bike {
    imply heaviest = max(bags.weight)
    require count(bags) = 0
}
"""
    )
    solved = solve(model)
    assert solved is not None
    assert part(solved).get("heaviest") is None


def test_rounding_waits_only_for_its_value() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num.## price
    num.# digits
    num.# rounded
}
behavior Bike {
    imply rounded = round(price, digits)
}
"""
    )
    solved = solve(model, inputs(model, price="2.46"))
    assert solved is not None
    assert part(solved).get("rounded") == Decimal("2.5")


def test_blank_texts_are_falsy() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    0..1 string note
    num marked
}
behavior Bike {
    condition note
    imply marked = 1
}
"""
    )
    blank = solve(model, inputs(model, note="  "))
    assert blank is not None and part(blank).get("marked") is None
    written = solve(model, inputs(model, note="fragile"))
    assert written is not None and part(written).get("marked") == 1


MIXED_GRIDS = """
product { Bike bike }
structure Bike {
    num coarse
    num.## fine
    num.## other
}
"""


def test_inputs_agree_with_requirements_at_the_lowest_precision() -> None:
    model = model_of(MIXED_GRIDS + "behavior Bike { require coarse = fine }")
    solved = solve(model, inputs(model, coarse=3, fine=Decimal("3.40")))
    assert solved is not None
    assert part(solved).get("fine") == Decimal("3.40")
    assert solve(model, inputs(model, coarse=3, fine=Decimal("3.60"))) is None
    derived = solve(model, inputs(model, fine=Decimal("3.40")))
    assert derived is not None
    assert part(derived).get("coarse") == 3


def test_inputs_agree_with_implications_at_the_lowest_precision() -> None:
    model = model_of(MIXED_GRIDS + "behavior Bike { imply fine = coarse }")
    solved = solve(model, inputs(model, coarse=3, fine=Decimal("3.40")))
    assert solved is not None
    assert part(solved).get("fine") == Decimal("3.40")
    assert solve(model, inputs(model, coarse=3, fine=Decimal("3.60"))) is None


def test_the_most_precise_implication_gives_the_value() -> None:
    model = model_of(
        MIXED_GRIDS
        + """
behavior Bike {
    imply fine = coarse
    imply fine = other
}
"""
    )
    solved = solve(model, inputs(model, coarse=3, other=Decimal("3.40")))
    assert solved is not None
    assert part(solved).get("fine") == Decimal("3.40")
    assert solve(model, inputs(model, coarse=3, other=Decimal("3.60"))) is None
    alone = solve(model, inputs(model, coarse=3))
    assert alone is not None
    assert part(alone).get("fine") == 3


def test_faulting_implications_fail_while_other_operands_are_open() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num n
    num x
    num y
}
behavior Bike {
    imply y = (1 / n) + x
}
"""
    )
    assert solve(model, inputs(model, n=0)) is None
    assert solve(model, inputs(model, n=1)) is not None


def test_formulas_over_absent_values_are_not_defined() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    0..1 num z
}
behavior Bike {
    require z + 1
}
"""
    )
    assert solve(model) is None
    assert solve(model, inputs(model, z=1)) is not None


# Defaults


def test_defaults_keep_their_role_next_to_implications() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    bool flag
    num x
}
behavior Bike {
    default flag = true
    default x = 3
}
behavior Bike {
    condition flag
    imply x = 3
}
"""
    )
    solved = solve(model)
    assert solved is not None
    assert part(solved).get("flag") is True
    assert part(solved).assignment("x").role is Role.DEFAULT  # type: ignore[union-attr]


def test_defaults_yield_to_selections() -> None:
    model = compile_files([CONFORMANCE / "D-BASE" / "WhiteBike.model"]).model
    solved = solve(model)
    assert solved is not None
    assert part(solved).get("color").name == "White"  # type: ignore[union-attr]
    assert part(solved).assignment("color").role is Role.DEFAULT  # type: ignore[union-attr]
    selected = solve(model, inputs(model, color="Black"))
    assert selected is not None
    assert part(selected).get("color").name == "Black"  # type: ignore[union-attr]


def test_higher_priority_defaults_come_first() -> None:
    solved = solve(compile_files([CONFORMANCE / "D-COND" / "SoftBrakeBike.model"]).model)
    assert solved is not None
    handle = part(solved).get("handle")
    assert isinstance(handle, Instance)
    assert handle.get("extraSoftGrips") is True
    assert handle.get("brakeLever").name == "Rugged"  # type: ignore[union-attr]


def test_defaults_that_defeat_their_guard_are_not_applied() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    num x
    num y
}
behavior Bike {
    default y = 0
    default x = 10 / y
}
"""
    )
    solved = solve(model)
    assert solved is not None
    assert part(solved).get("y") == 0
    assert part(solved).get("x") is None


def test_feasible_ignores_defaults() -> None:
    model = compile_files([CONFORMANCE / "D-BASE" / "WhiteBike.model"]).model
    assert names(ClingoSolver(model).feasible(None, "whiteBike.color")) == {"White", "Black", "Red"}


def test_optimization_is_ignored_with_a_warning() -> None:
    solver = ClingoSolver(compile_files([CONFORMANCE / "C-OPEN" / "CargoBike.model"]).model)
    assert [diagnostic.severity for diagnostic in solver.diagnostics] == [Severity.WARNING]


# Tests blocks


def test_test_blocks_run_against_the_solver() -> None:
    model = model_of(
        KIDS_BIKE
        + """
test {
    set kidsBike.color = Yellow
    isBlocked kidsBike.wheelSize = W14
    isAvailable kidsBike.wheelSize = W20
    set kidsBike.wheelSize = W20
    isShown kidsBike.wheelSize = W20
    isFixed kidsBike.supportWheels = false
}
test {
    set kidsBike.color = Yellow
    set kidsBike.supportWheels = true
}
"""
    )
    first, second = run_tests(model)
    assert [step.status for step in first.steps] == [Status.PASSED] * 6
    assert not second.passed
    assert second.steps[1].status is Status.FAILED
