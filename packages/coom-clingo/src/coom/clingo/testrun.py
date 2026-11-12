"""Runs the test blocks of a model against the solver.

A test is a session. Its set, remove and reset steps change the inputs, and every set is checked to have a
completion. isAvailable and isBlocked ask whether the inputs with a value set, or instances created, still have a
completion, without changing the inputs. isShown, isEmpty, isHidden and isReadonly read the slot in the configuration
the solver completes the inputs to. isShown needs a visible slot whose value is at least a default, isEmpty accepts a
slot without value or with a value chosen only to complete the configuration. isHidden and isReadonly read the
effective visibility directive of the slot regardless of its value. isFixed needs a selected value or one the inputs
force.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from coom.clingo.solver import ClingoSolver
from coom.configuration import Configuration, Instance, Role, visibilities
from coom.model import (
    Directive,
    Feature,
    FeatureStep,
    IsAvailable,
    IsBlocked,
    IsEmpty,
    IsFixed,
    IsHidden,
    IsReadonly,
    IsShown,
    Model,
    Path,
    RemoveValue,
    ResetValue,
    SetValue,
    Structure,
    TestCase,
    TestStep,
)

# from the weakest reason for a value to the strongest
_ROLES = list(Role)


class Status(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class StepResult:
    step: TestStep
    status: Status
    message: str = ""


@dataclass(frozen=True, slots=True)
class TestResult:
    test: TestCase
    steps: tuple[StepResult, ...]

    @property
    def passed(self) -> bool:
        return all(step.status is not Status.FAILED for step in self.steps)


def run_tests(model: Model, solver: ClingoSolver | None = None) -> list[TestResult]:
    """Runs every test of the model, each in a session of its own."""
    solver = solver or ClingoSolver(model)
    return [run_test(solver, test) for test in model.tests]


def run_test(solver: ClingoSolver, test: TestCase) -> TestResult:
    if test.origin is not solver.model.root:
        reason = "the solver runs only tests of the product"
        return TestResult(test, tuple(StepResult(step, Status.SKIPPED, reason) for step in test.steps))
    session = Configuration(solver.model)
    return TestResult(test, tuple(_step(solver, session, step) for step in test.steps))


def _step(solver: ClingoSolver, session: Configuration, step: TestStep) -> StepResult:
    try:
        match step:
            case SetValue():
                _set(session, step)
                if solver.satisfiable(session):
                    return StepResult(step, Status.PASSED)
                return StepResult(step, Status.FAILED, f"setting {step.path} leaves no completion")
            case RemoveValue() | ResetValue():
                _remove(session, step.path)
                return StepResult(step, Status.PASSED)
            case IsAvailable() | IsBlocked():
                available = _available(solver, session, step)
                if available == isinstance(step, IsAvailable):
                    return StepResult(step, Status.PASSED)
                state = "available" if available else "blocked"
                what = "creating the instances" if step.value is None else repr(step.value.value)
                return StepResult(step, Status.FAILED, f"{what} is {state} for {step.path}")
            case IsShown() | IsEmpty() | IsHidden() | IsReadonly():
                solved = solver.solve(session)
                if solved is None:
                    return StepResult(step, Status.FAILED, "the inputs have no completion")
                match step:
                    case IsShown():
                        failure = _shown(solved, step)
                    case IsEmpty():
                        failure = _empty(solved, step)
                    case IsHidden():
                        failure = _hidden(solved, step)
                    case IsReadonly():
                        failure = _readonly(solved, step)
                return StepResult(step, Status.FAILED, failure) if failure else StepResult(step, Status.PASSED)
            case IsFixed():
                solved = solver.solve(session)
                if solved is None:
                    return StepResult(step, Status.FAILED, "the inputs have no completion")
                slot = _slot(solved, step.path)
                assignment = None if slot is None else slot[0].assignment(slot[1], slot[2])
                if assignment is None:
                    return StepResult(step, Status.FAILED, f"{step.path} holds no value")
                if step.value is not None and not _same(assignment.value, step.value.value):
                    return StepResult(step, Status.FAILED, f"{step.path} holds {assignment.value!r}")
                if assignment.role not in (Role.SELECTED, Role.CONSEQUENCE):
                    return StepResult(step, Status.FAILED, f"{step.path} is not fixed, its role is {assignment.role}")
                return StepResult(step, Status.PASSED)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        return StepResult(step, Status.FAILED, str(error))
    raise AssertionError(step)


def _slots(path: Path) -> list[tuple[FeatureStep, int]]:
    result = []
    for step in path.steps:
        if not isinstance(step, FeatureStep):
            raise KeyError(f"{path} addresses an attribute")
        index = 0 if step.index is None else step.index.first
        if index < 0:
            raise KeyError(f"{path} counts from the end")
        result.append((step, index))
    return result


def _set(session: Configuration, step: SetValue) -> None:
    instance = session.root
    slots = _slots(step.path)
    for number, (feature_step, index) in enumerate(slots):
        feature = feature_step.feature
        final = number == len(slots) - 1
        if isinstance(feature.type, Structure):
            child = instance.get(feature, index)
            if child is None:
                child = instance.set(feature, session.new(feature.type), index)
            if not isinstance(child, Instance):
                raise TypeError(f"{step.path} does not lead through instances")
            instance = child
            if final and step.value is not None:
                raise ValueError(f"{step.path} holds instances, not {step.value.value}")
        elif final:
            if step.value is None:
                raise ValueError(f"{step.path} needs a value")
            value = step.value.value
            instance.set(feature, int(value) if isinstance(value, Decimal) and value == int(value) else value, index)
        else:
            raise KeyError(f"{step.path} does not lead through instances")


def _available(solver: ClingoSolver, session: Configuration, step: IsAvailable | IsBlocked) -> bool:
    """Whether the inputs with the value of the step set, or its instances created, have a completion.

    The value replaces an input of the slot, so the check runs on a copy of the inputs rather than on the options the
    inputs leave open.
    """
    trial = Configuration.from_json(session.model, session.to_json())
    _set(trial, SetValue(step.path, step.value))
    return solver.satisfiable(trial)


def _remove(session: Configuration, path: Path) -> None:
    instance: Instance | None = session.root
    slots = _slots(path)
    for number, (feature_step, index) in enumerate(slots):
        if instance is None:
            return
        if number == len(slots) - 1:
            instance.remove(feature_step.feature, index)
            return
        child = instance.get(feature_step.feature, index)
        instance = child if isinstance(child, Instance) else None


def _shown(solved: Configuration, step: IsShown) -> str | None:
    """Why a slot is not shown, None if it is visible and holds a value that is at least a default."""
    slot = _slot(solved, step.path)
    if slot is not None and visibilities(solved).effective(*slot) is Directive.HIDE:
        return f"{step.path} is hidden"
    assignment = None if slot is None else slot[0].assignment(slot[1], slot[2])
    if assignment is None:
        return f"{step.path} has no value"
    if _ROLES.index(assignment.role) < _ROLES.index(Role.DEFAULT):
        return f"{step.path} holds {assignment.value!r} only to complete the configuration"
    if step.value is not None and not _same(assignment.value, step.value.value):
        return f"{step.path} holds {assignment.value!r}"
    return None


def _hidden(solved: Configuration, step: IsHidden) -> str | None:
    """Why a slot or one of its options is not hidden, None if it is."""
    slot = _slot(solved, step.path)
    if slot is None:
        return f"{step.path} does not exist"
    if step.value is None:
        return None if visibilities(solved).effective(*slot) is Directive.HIDE else f"{step.path} is not hidden"
    if step.value.value in visibilities(solved).hidden_options(*slot):
        return None
    return f"{step.value.value!r} is not hidden for {step.path}"


def _readonly(solved: Configuration, step: IsReadonly) -> str | None:
    """Why a slot can be changed, None if it is readonly or hidden."""
    slot = _slot(solved, step.path)
    if slot is None:
        return f"{step.path} does not exist"
    if visibilities(solved).effective(*slot) in (Directive.READONLY, Directive.HIDE):
        return None
    return f"{step.path} is not readonly"


def _empty(solved: Configuration, step: IsEmpty) -> str | None:
    """Why a slot is not empty, None if it holds no value or one chosen only to complete the configuration."""
    slot = _slot(solved, step.path)
    assignment = None if slot is None else slot[0].assignment(slot[1], slot[2])
    if assignment is None or assignment.role is Role.COMPLETION:
        return None
    return f"{step.path} holds {assignment.value!r} as {assignment.role}"


def _slot(configuration: Configuration, path: Path) -> tuple[Instance, Feature, int] | None:
    """The instance, feature and index of the slot a path addresses, None if an instance on the way is missing."""
    instance: object = configuration.root
    slots = _slots(path)
    for feature_step, index in slots[:-1]:
        if not isinstance(instance, Instance):
            return None
        instance = instance.get(feature_step.feature, index)
    if not isinstance(instance, Instance) or not slots:
        return None
    feature_step, index = slots[-1]
    return instance, feature_step.feature, index


def _same(actual: object, expected: object) -> bool:
    if isinstance(actual, Decimal) and isinstance(expected, Decimal):
        return actual == expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    return actual is expected or actual == expected
