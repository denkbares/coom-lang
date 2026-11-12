"""COOM arithmetic on exact rationals.

Sums, differences, products and quotients are exact. A value is rounded only when it is stored into a feature, half
away from zero to the grid of the feature. Roots, logarithms, powers with fractional exponents and the trigonometric
and hyperbolic functions are exact where the result is rational and otherwise rounded to nearest at 20 significant
digits. Angles are in degrees. An operation without a value, such as a division by zero, raises Fault. A result with
more than 100000 digits raises Exceeded.
"""

import math
from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext
from fractions import Fraction
from functools import cache

PRECISION = 20
"""The significant digits of results that are not rational."""

SIZE_LIMIT = 100_000
"""The largest number of digits of a numerator or denominator."""

_SIZE_BITS = math.ceil(SIZE_LIMIT * math.log2(10))
_WORK = Context(prec=2 * PRECISION + 10, Emax=10**9, Emin=-(10**9))
_RESULT = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN, Emax=10**9, Emin=-(10**9))

_ZERO, _ONE, _HALF = Fraction(0), Fraction(1), Fraction(1, 2)
_DEG_30, _DEG_45, _DEG_60, _DEG_90 = Fraction(30), Fraction(45), Fraction(60), Fraction(90)
_DEG_120, _DEG_180 = Fraction(120), Fraction(180)


class Fault(ArithmeticError):
    """An operation that has no value."""


class Exceeded(ArithmeticError):
    """An operation whose result is too large to represent."""


# Grids


def to_grid(value: Fraction, digits: int) -> Fraction:
    """Rounds a value half away from zero to the grid with the given number of fraction digits."""
    scale = Fraction(10) ** digits
    scaled = abs(value) * scale
    whole, rest = divmod(scaled.numerator, scaled.denominator)
    if 2 * rest >= scaled.denominator:
        whole += 1
    return (-whole if value < 0 else whole) / scale


def to_decimal(value: Fraction) -> Decimal:
    """Converts a value with a terminating decimal expansion, such as a grid value, exactly to a decimal."""
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError(f"{value} has no terminating decimal expansion")
    digits = max(twos, fives)
    return Decimal(value.numerator * 10**digits // value.denominator).scaleb(-digits)


# Field operations, powers and remainders


def multiply(left: Fraction, right: Fraction) -> Fraction:
    return _checked(left * right)


def divide(left: Fraction, right: Fraction) -> Fraction:
    if right == 0:
        raise Fault("division by zero")
    return _checked(left / right)


def modulo(left: Fraction, right: Fraction) -> Fraction:
    """The remainder of a division that truncates towards zero, so the result has the sign of the dividend."""
    if right == 0:
        raise Fault("modulo by zero")
    return left - right * math.trunc(left / right)


def power(base: Fraction, exponent: Fraction) -> Fraction:
    if exponent.denominator == 1:
        return _integer_power(base, exponent.numerator)
    if base < 0:
        raise Fault("power of a negative number with a fractional exponent")
    if base == 0:
        if exponent > 0:
            return _ZERO
        raise Fault("zero to a negative power")
    numerator, denominator = _root(base.numerator, exponent.denominator), _root(base.denominator, exponent.denominator)
    if numerator is not None and denominator is not None:
        return _integer_power(Fraction(numerator, denominator), exponent.numerator)
    return _rounded(lambda: (_decimal(exponent) * _decimal(base).ln()).exp())


def _integer_power(base: Fraction, exponent: int) -> Fraction:
    if exponent == 0:
        return _ONE
    if base == 0:
        if exponent > 0:
            return _ZERO
        raise Fault("zero to a negative power")
    bits = max(base.numerator.bit_length(), base.denominator.bit_length()) - 1
    if bits * abs(exponent) > _SIZE_BITS:
        raise Exceeded("the power has too many digits")
    return _checked(base**exponent)


def _checked(value: Fraction) -> Fraction:
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > _SIZE_BITS:
        raise Exceeded("the result has too many digits")
    return value


def _root(value: int, degree: int) -> int | None:
    """Returns the integer whose power of the degree is the value, None if there is none."""
    if value in (0, 1):
        return value
    if degree >= value.bit_length():
        return None
    root = math.isqrt(value) if degree == 2 else _root_floor(value, degree)
    return root if root**degree == value else None


def _root_floor(value: int, degree: int) -> int:
    """The largest integer whose power of the degree does not exceed the value, by Newton's iteration from above."""
    root = 1 << -(-value.bit_length() // degree)
    while True:
        lower = ((degree - 1) * root + value // root ** (degree - 1)) // degree
        if lower >= root:
            return root
        root = lower


# Roots and logarithms


def sqrt(value: Fraction) -> Fraction:
    if value < 0:
        raise Fault("square root of a negative number")
    numerator, denominator = _root(value.numerator, 2), _root(value.denominator, 2)
    if numerator is not None and denominator is not None:
        return Fraction(numerator, denominator)
    return _rounded(lambda: _decimal(value).sqrt())


def ln(value: Fraction) -> Fraction:
    if value <= 0:
        raise Fault("logarithm of a number that is not positive")
    if value == 1:
        return _ZERO
    return _rounded(lambda: _decimal(value).ln())


def log(value: Fraction, base: Fraction) -> Fraction:
    """The logarithm of the value to the base, exact if it is rational."""
    if value <= 0 or base <= 0 or base == 1:
        raise Fault(f"logarithm of {value} to the base {base}")
    if value == 1:
        return _ZERO
    with localcontext(_WORK):
        estimate = _decimal(value).ln() / _decimal(base).ln()
    candidate = Fraction(estimate).limit_denominator(1000)
    if _is_log(value, base, candidate):
        return candidate
    return _rounded(lambda: estimate)


def _is_log(value: Fraction, base: Fraction, candidate: Fraction) -> bool:
    """Whether the value to the power of the candidate's denominator is the base to the power of its numerator."""
    bits = max(x.bit_length() for x in (value.numerator, value.denominator, base.numerator, base.denominator))
    if bits * max(abs(candidate.numerator), candidate.denominator) > _SIZE_BITS:
        return False
    return value**candidate.denominator == base**candidate.numerator


# Trigonometry in degrees


def sin(degrees: Fraction) -> Fraction:
    return _sine(degrees % 360)


def cos(degrees: Fraction) -> Fraction:
    return _sine((degrees + 90) % 360)


def _sine(angle: Fraction) -> Fraction:
    """The sine of an angle from 0 to 360 degrees, reduced to a sine or cosine of at most 45 degrees."""
    negative = angle >= _DEG_180
    if negative:
        angle -= _DEG_180
    if angle > _DEG_90:
        angle = _DEG_180 - angle
    result = {_ZERO: _ZERO, _DEG_30: _HALF, _DEG_90: _ONE}.get(angle)
    if result is None and angle <= _DEG_45:
        result = _rounded(lambda: _sin_series(_radians(angle)))
    elif result is None:
        result = _rounded(lambda: _cos_series(_radians(_DEG_90 - angle)))
    return -result if negative else result


def tan(degrees: Fraction) -> Fraction:
    angle = degrees % 180
    negative = angle > _DEG_90
    if negative:
        angle = _DEG_180 - angle
    if angle == _DEG_90:
        raise Fault(f"tangent of {degrees} degrees")
    result = {_ZERO: _ZERO, _DEG_45: _ONE}.get(angle)
    if result is None and angle < _DEG_45:
        result = _rounded(lambda: _tan_series(_radians(angle)))
    elif result is None:
        # above 45 degrees the cotangent of the exact complement keeps the accuracy near the pole
        result = _rounded(lambda: 1 / _tan_series(_radians(_DEG_90 - angle)))
    return -result if negative else result


def asin(value: Fraction) -> Fraction:
    magnitude = abs(value)
    if magnitude > 1:
        raise Fault(f"arc sine of {value}")
    result = {_ZERO: _ZERO, _HALF: _DEG_30, _ONE: _DEG_90}.get(magnitude)
    if result is None:
        result = _rounded(lambda: _degrees(_atan_series(_decimal(magnitude) / _decimal(1 - magnitude**2).sqrt())))
    return -result if value < 0 else result


def acos(value: Fraction) -> Fraction:
    if abs(value) > 1:
        raise Fault(f"arc cosine of {value}")
    result = {_ONE: _ZERO, _HALF: _DEG_60, _ZERO: _DEG_90, -_HALF: _DEG_120, -_ONE: _DEG_180}.get(value)
    if result is not None:
        return result
    # 2 atan(sqrt((1 - x) / (1 + x))) keeps its accuracy near both ends, where 1 - x or 1 + x is small
    return _rounded(lambda: 2 * _degrees(_atan_series(_decimal((1 - value) / (1 + value)).sqrt())))


def atan(value: Fraction) -> Fraction:
    result = {_ZERO: _ZERO, _ONE: _DEG_45}.get(abs(value))
    if result is None:
        result = _rounded(lambda: _degrees(_atan_series(_decimal(abs(value)))))
    return -result if value < 0 else result


# Hyperbolic functions of plain numbers


def sinh(value: Fraction) -> Fraction:
    return _ZERO if value == 0 else _rounded(lambda: _sinh(_decimal(value)))


def cosh(value: Fraction) -> Fraction:
    return _ONE if value == 0 else _rounded(lambda: _cosh(_decimal(value)))


def tanh(value: Fraction) -> Fraction:
    return _ZERO if value == 0 else _rounded(lambda: _sinh(_decimal(value)) / _cosh(_decimal(value)))


# Calculations in working precision, which carries enough guard digits for the result precision


def _rounded(calculate: Callable[[], Decimal]) -> Fraction:
    """Runs a calculation in working precision and rounds the result to the result precision."""
    try:
        with localcontext(_WORK):
            result = _RESULT.plus(calculate())
    except DecimalException as error:
        raise Exceeded("the result is beyond the representable range") from error
    if result and abs(result.adjusted()) > SIZE_LIMIT:
        raise Exceeded("the result is beyond the representable range")
    return Fraction(result)


def _decimal(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


@cache
def _pi() -> Decimal:
    """Pi by Machin's formula."""
    with localcontext(_WORK):
        return 4 * (4 * _atan_small(1 / Decimal(5)) - _atan_small(1 / Decimal(239)))


def _radians(degrees: Fraction) -> Decimal:
    return _decimal(degrees) * _pi() / 180


def _degrees(radians: Decimal) -> Decimal:
    return radians * 180 / _pi()


def _sin_series(x: Decimal) -> Decimal:
    return _alternating(x, x * x, 1)


def _cos_series(x: Decimal) -> Decimal:
    return _alternating(Decimal(1), x * x, 0)


def _tan_series(x: Decimal) -> Decimal:
    return _sin_series(x) / _cos_series(x)


def _alternating(term: Decimal, square: Decimal, k: int) -> Decimal:
    """Sums the Taylor series of sine (k = 1) or cosine (k = 0) from its first term."""
    total = term
    while True:
        term = -term * square / ((k + 1) * (k + 2))
        k += 2
        if total + term == total:
            return total
        total += term


def _atan_series(x: Decimal) -> Decimal:
    """The arc tangent in radians of a nonnegative number, by halving the angle until the argument is small."""
    if x > 1:
        return _pi() / 2 - _atan_series(1 / x)
    halvings = 0
    while x > Decimal("0.1"):
        x = x / (1 + (1 + x * x).sqrt())
        halvings += 1
    return _atan_small(x) * (1 << halvings)


def _atan_small(x: Decimal) -> Decimal:
    square, term, total, k = x * x, x, x, 1
    while True:
        term = -term * square
        k += 2
        if total + term / k == total:
            return total
        total += term / k


def _sinh(x: Decimal) -> Decimal:
    if abs(x) >= 1:
        return (x.exp() - (-x).exp()) / 2
    square, term, total, k = x * x, x, x, 1
    while True:
        term = term * square / ((k + 1) * (k + 2))
        k += 2
        if total + term == total:
            return total
        total += term


def _cosh(x: Decimal) -> Decimal:
    return (x.exp() + (-x).exp()) / 2
