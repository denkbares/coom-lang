"""Test blocks run against the clingo solver, with roles and visibility deciding what isShown and isEmpty see."""

from coom.clingo.testrun import Status, run_tests
from coom.compiler import compile_text

MODEL = """
product { Bike bike }
structure Bike {
    Color color
    bool lights
    Color seat
    Frame frame
}
structure Frame { Color color }
enumeration Color { Red; Green }
behavior Bike {
    default seat = Green
    condition color = Red
    hide lights
    readonly frame.color
}
test {
    set bike.color = Green
    set bike.lights = true
    isShown bike.lights = true
    isShown bike.seat = Green
    isShown bike.frame.color
    isEmpty bike.frame.color
    isEmpty bike.lights
    set bike.color = Red
    isShown bike.lights
}
"""


def test_is_shown_and_is_empty_follow_roles_and_visibility() -> None:
    result = compile_text(MODEL)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    (test,) = run_tests(result.model)
    passed, failed = Status.PASSED, Status.FAILED
    statuses = [step.status for step in test.steps]
    assert statuses == [passed, passed, passed, passed, failed, passed, failed, passed, failed]
    assert "complete" in test.steps[4].message
    assert "selected" in test.steps[6].message
    assert "hidden" in test.steps[8].message
