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


STEPS = """
product {
    Bike bike
}
structure Bike {
    Color color
    bool lights
    num /kg 0-200 riderWeight
    0..3 Bag bags
    Frame frame
}
structure Frame { Color color }
structure Bag { bool big }
enumeration Color { Red; Green; Blue }
behavior Bike {
    condition riderWeight > 100
    require lights = true
    condition riderWeight > 100
    require count(bags) <= 1
    condition color = Red
    hide frame
    condition color = Green
    hide color Blue
    readonly riderWeight
}
test {
    set bike.lights = false
    isBlocked bike.riderWeight = 130
    isAvailable bike.riderWeight = 90
    set bike.riderWeight = 90
    remove bike.lights
    set bike.riderWeight = 115
    isBlocked bike.lights = false
    isAvailable bike.lights = true
    set bike.bags[0]
    isBlocked bike.bags[1]
    isAvailable bike.bags[0]
    isBlocked bike.riderWeight = 115
}
test {
    set bike.color = Red
    isHidden bike.frame
    isHidden bike.frame.color
    isReadonly bike.frame.color
    isReadonly bike.riderWeight
    isHidden bike.riderWeight
    isReadonly bike.lights
    set bike.color = Green
    isHidden bike.color = Blue
    isHidden bike.color = Red
    isHidden bike.color
}
"""


def test_feasibility_and_visibility_steps() -> None:
    result = compile_text(STEPS)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    feasibility, visibility = run_tests(result.model)
    passed, failed = Status.PASSED, Status.FAILED
    assert [step.status for step in feasibility.steps] == [passed] * 11 + [failed]
    assert "available" in feasibility.steps[11].message
    statuses = [step.status for step in visibility.steps]
    assert statuses == [passed] * 5 + [failed, failed, passed, passed, failed, failed]
    assert "not hidden" in visibility.steps[5].message
    assert "not readonly" in visibility.steps[6].message
