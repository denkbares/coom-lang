"""The session tests of the conformance suite, each test block run against the clingo solver."""

import warnings
from functools import cache
from pathlib import Path

import pytest

from coom.clingo.solver import ClingoSolver
from coom.clingo.testrun import Status, StepResult, run_test
from coom.compiler import compile_files
from coom.model import Model

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"
TESTS = sorted(CONFORMANCE.rglob("*.test"))
# O needs optimization, which the solver ignores
PROFILES = ("CORE", "N-OUT", "N-LIN", "N-FULL", "C-FIX", "C-USER", "C-OPEN", "D-BASE", "D-COND", "UI", "TEST")


@cache
def model(path: Path) -> Model:
    """The test file compiled together with the model of the same name."""
    result = compile_files([path.with_suffix(".model"), path])
    assert result.ok, "\n".join(map(str, result.diagnostics))
    return result.model


@cache
def solver(path: Path) -> ClingoSolver:
    return ClingoSolver(model(path))


CASES = [(path, number) for path in TESTS for number in range(len(model(path).tests))]


def test_every_supported_profile_has_session_tests() -> None:
    assert set(PROFILES) <= {path.parent.name for path in TESTS}


@pytest.mark.parametrize(
    ("path", "number"), CASES, ids=[f"{path.relative_to(CONFORMANCE)}:{number}" for path, number in CASES]
)
def test_session(path: Path, number: int) -> None:
    result = run_test(solver(path), model(path).tests[number])
    failed = [step for step in result.steps if step.status is Status.FAILED]
    skipped = [step for step in result.steps if step.status is Status.SKIPPED]
    for step in skipped:
        warnings.warn(f"{path.name} {_describe(step)}", stacklevel=1)
    assert not failed, "\n".join(_describe(step) for step in failed)
    if skipped and len(skipped) == len(result.steps):
        pytest.skip(f"every step skipped: {skipped[0].message}")


def _describe(result: StepResult) -> str:
    line = "?" if result.step.span is None else result.step.span.line
    return f"line {line} {type(result.step).__name__} {result.status}: {result.message}"
