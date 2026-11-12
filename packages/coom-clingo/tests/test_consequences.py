"""Consequences, the values the inputs force, against every completion the solver enumerates."""

from decimal import Decimal
from pathlib import Path

import pytest
from model_generator import case

from coom.clingo.solver import ClingoSolver
from coom.clingo.testrun import Status, run_tests
from coom.compiler import compile_files, compile_text
from coom.configuration import Configuration, Instance, Role
from coom.model import Boolean, Enumeration, Model, Option, Structure

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"
SEEDS = range(200)


def model_of(text: str) -> Model:
    result = compile_text(text)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    return result.model


def part(configuration: Configuration) -> Instance:
    value = configuration.root.values(configuration.model.root.features[0])[0]
    assert isinstance(value, Instance)
    return value


def roles(configuration: Configuration) -> dict[str, tuple[object, Role]]:
    """Every filled slot by its path, with the value and its role, instances standing for their existence."""
    result: dict[str, tuple[object, Role]] = {}
    for instance in configuration.instances():
        prefix = f"{instance.path}." if instance.path else ""
        for feature in instance.type.features:
            for index, assignment in instance.assignments(feature).items():
                value = True if isinstance(assignment.value, Instance) else assignment.value
                result[f"{prefix}{feature.name}[{index}]"] = (value, assignment.role)
    return result


def same(left: object, right: object) -> bool:
    if isinstance(left, Option | bool) or isinstance(right, Option | bool):
        return left is right
    return left == right


@pytest.mark.parametrize("seed", SEEDS)
def test_consequences_hold_in_every_completion(seed: int) -> None:
    example = case(seed)
    solver = ClingoSolver(example.model)
    solved = solver.solve(example.inputs)
    if solved is None:
        return
    completions = [roles(configuration) for configuration in solver.enumerate(example.inputs)]
    context = f"seed {seed}\n{example.text}"
    for path, (value, role) in roles(solved).items():
        everywhere = all(path in completion and same(completion[path][0], value) for completion in completions)
        if role is Role.CONSEQUENCE:
            assert everywhere, f"{path} = {value!r} is no consequence\n{context}"
        elif everywhere and role is not Role.SELECTED and _is_discrete(solved, path):
            # discrete consequences are exact, only computed values may be missed by the dependency rule
            pytest.fail(f"{path} = {value!r} holds everywhere but has role {role}\n{context}")


def _is_discrete(configuration: Configuration, path: str) -> bool:
    owner, _, step = path.rpartition(".")
    instance = configuration.root if not owner else configuration[owner]
    assert isinstance(instance, Instance)
    feature = instance.type.feature(step.partition("[")[0])
    return isinstance(feature.type, Structure | Enumeration | Boolean)


def test_inputs_force_options_through_tables() -> None:
    model = compile_files([CONFORMANCE / "CORE" / "KidsBike.model"]).model
    configuration = Configuration(model)
    configuration.add_required()
    part(configuration).set("supportWheels", True)
    solved = ClingoSolver(model).solve(configuration)
    assert solved is not None
    assert part(solved).assignment("supportWheels").role is Role.SELECTED  # type: ignore[union-attr]
    assert part(solved).assignment("wheelSize").role is Role.COMPLETION  # type: ignore[union-attr]
    configuration = Configuration(model)
    configuration.add_required()
    part(configuration).set("color", "Yellow")
    solved = ClingoSolver(model).solve(configuration)
    assert solved is not None
    assert part(solved).get("supportWheels") is False
    assert part(solved).assignment("supportWheels").role is Role.CONSEQUENCE  # type: ignore[union-attr]


def test_defaults_are_never_consequences() -> None:
    solved = ClingoSolver(compile_files([CONFORMANCE / "D-BASE" / "WhiteBike.model"]).model).solve()
    assert solved is not None
    assert part(solved).assignment("color").role is Role.DEFAULT  # type: ignore[union-attr]


def test_required_instances_and_constant_values_are_consequences() -> None:
    solved = ClingoSolver(compile_files([CONFORMANCE / "N-OUT" / "WeightyBike.model"]).model).solve()
    assert solved is not None
    weights = part(solved).get("weights")
    assert isinstance(weights, Instance)
    assert part(solved).assignment("weights").role is Role.CONSEQUENCE  # type: ignore[union-attr]
    assert weights.assignment("frameWeight").role is Role.CONSEQUENCE  # type: ignore[union-attr]
    # the wheel weight depends on the wheel size, which the inputs leave open
    assert weights.assignment("wheelWeight").role is Role.COMPLETION  # type: ignore[union-attr]


def test_computed_values_follow_forced_inputs() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    Size size
    num total
}
enumeration Size {
    attribute num weight
    small = (2)
    large = (5)
}
behavior Bike {
    require size = large
    imply total = size.weight * 2
}
"""
    )
    solved = ClingoSolver(model).solve()
    assert solved is not None
    assert part(solved).get("total") == Decimal(10)
    assert part(solved).assignment("total").role is Role.CONSEQUENCE  # type: ignore[union-attr]


def test_values_from_optional_parts_are_not_fixed() -> None:
    model = model_of(
        """
product { Bike bike }
structure Bike {
    0..2 Bag bags
    num count
}
structure Bag { bool big }
behavior Bike {
    imply count = count(bags)
}
"""
    )
    solved = ClingoSolver(model).solve()
    assert solved is not None
    assert part(solved).assignment("count").role is Role.COMPLETION  # type: ignore[union-attr]


def test_is_fixed_steps() -> None:
    text = (
        (CONFORMANCE / "CORE" / "KidsBike.model").read_text()
        + """
test {
    set kidsBike.color = Yellow
    isFixed kidsBike.supportWheels = false
    isFixed kidsBike.color = Yellow
    isFixed kidsBike.wheelSize
}
"""
    )
    (result,) = run_tests(model_of(text))
    assert [step.status for step in result.steps] == [Status.PASSED] * 3 + [Status.FAILED]
