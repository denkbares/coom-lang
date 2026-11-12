"""Exact arithmetic, rounding to grids, exact special cases and faults."""

import math
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction

import pytest

from coom.configuration import arithmetic

F = Fraction


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (F(5, 2), 0, F(3)),
        (F(-5, 2), 0, F(-3)),
        (F(2675, 1000), 2, F(268, 100)),
        (F(1, 3), 2, F(33, 100)),
        (F(-1, 200), 2, F(-1, 100)),
        (F(149), -2, F(100)),
    ],
)
def test_rounding_is_half_away_from_zero(value: Fraction, digits: int, expected: Fraction) -> None:
    assert arithmetic.to_grid(value, digits) == expected


def test_decimal_conversion_is_exact_for_terminating_values() -> None:
    assert arithmetic.to_decimal(F(1, 8)) == Decimal("0.125")
    assert str(arithmetic.to_decimal(F(-123, 100))) == "-1.23"
    with pytest.raises(ValueError):
        arithmetic.to_decimal(F(1, 3))


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (arithmetic.sqrt(F(9, 4)), F(3, 2)),
        (arithmetic.power(F(8, 27), F(2, 3)), F(4, 9)),
        (arithmetic.power(F(2), F(-3)), F(1, 8)),
        (arithmetic.log(F(8), F(2)), F(3)),
        (arithmetic.log(F(1, 9), F(27)), F(-2, 3)),
        (arithmetic.ln(F(1)), F(0)),
        (arithmetic.sin(F(180)), F(0)),
        (arithmetic.sin(F(-30)), F(-1, 2)),
        (arithmetic.cos(F(60)), F(1, 2)),
        (arithmetic.tan(F(45)), F(1)),
        (arithmetic.tan(F(135)), F(-1)),
        (arithmetic.asin(F(1, 2)), F(30)),
        (arithmetic.acos(F(-1, 2)), F(120)),
        (arithmetic.atan(F(-1)), F(-45)),
        (arithmetic.cosh(F(0)), F(1)),
        (arithmetic.modulo(F(-7), F(3)), F(-1)),
        (arithmetic.modulo(F(7), F(-3)), F(1)),
    ],
)
def test_rational_results_are_exact(result: Fraction, expected: Fraction) -> None:
    assert result == expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (arithmetic.sqrt(F(2)), math.sqrt(2)),
        (arithmetic.ln(F(10)), math.log(10)),
        (arithmetic.log(F(10), F(3)), math.log(10, 3)),
        (arithmetic.power(F(2), F(1, 3)), 2 ** (1 / 3)),
        (arithmetic.sin(F(10)), math.sin(math.radians(10))),
        (arithmetic.cos(F(10)), math.cos(math.radians(10))),
        (arithmetic.tan(F(89)), math.tan(math.radians(89))),
        (arithmetic.asin(F(-9, 10)), math.degrees(math.asin(-0.9))),
        (arithmetic.acos(F(1, 3)), math.degrees(math.acos(1 / 3))),
        (arithmetic.atan(F(7)), math.degrees(math.atan(7))),
        (arithmetic.sinh(F(1, 10)), math.sinh(0.1)),
        (arithmetic.tanh(F(-2)), math.tanh(-2)),
    ],
)
def test_irrational_results_agree_with_floating_point(result: Fraction, expected: float) -> None:
    assert float(result) == pytest.approx(expected, rel=1e-14)


def test_irrational_results_have_twenty_significant_digits() -> None:
    root = arithmetic.sqrt(F(2))
    assert arithmetic.to_decimal(root) == Decimal("1.4142135623730950488")
    assert root * root != 2


@pytest.mark.parametrize(
    "operation",
    [
        lambda: arithmetic.divide(F(1), F(0)),
        lambda: arithmetic.modulo(F(1), F(0)),
        lambda: arithmetic.sqrt(F(-1)),
        lambda: arithmetic.ln(F(0)),
        lambda: arithmetic.log(F(8), F(1)),
        lambda: arithmetic.power(F(0), F(-1)),
        lambda: arithmetic.power(F(-8), F(1, 3)),
        lambda: arithmetic.tan(F(90)),
        lambda: arithmetic.tan(F(1170)),
        lambda: arithmetic.asin(F(2)),
        lambda: arithmetic.acos(F(-3, 2)),
    ],
)
def test_faults(operation: Callable[[], Fraction]) -> None:
    with pytest.raises(arithmetic.Fault):
        operation()


def test_results_beyond_the_size_limit_are_exceeded() -> None:
    with pytest.raises(arithmetic.Exceeded):
        arithmetic.power(F(2), F(10**7))
    with pytest.raises(arithmetic.Exceeded):
        arithmetic.cosh(F(10**12))
