"""Evaluation of formulas, conditions and behaviors against a configuration.

Every formula is evaluated for an origin instance, the instance of the behavior's structure that relative paths start
from. A formula has a value, a sequence of values for a range path, or no value for one of the reasons of Undefined.

Conditions have strong Kleene semantics extended to sets of outcomes, see Truth. A comparison with an operand that
has no value is OPEN, since filling the value may decide it either way. A comparison whose operand faults is
INDEFINITE, since no completion makes it true. Comparisons are decided at the lowest precision among their sides, where
a bare numeric path contributes the digits of its type and round(e, d) contributes d.

A behavior holds for an instance unless its preconditions hold and its statement is violated. A require holds if its
condition does, an imply or default if the target holds the value of the formula, and a combinations table if some
allow row and no forbid row matches. Every value of a configuration counts as final, whatever its role.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, Flag
from fractions import Fraction
from typing import assert_never

from coom.configuration import arithmetic
from coom.configuration._configuration import Configuration, Instance
from coom.model import (
    And,
    AttributeStep,
    Behavior,
    Binary,
    BinaryOp,
    Call,
    Combinations,
    Compare,
    CompareOp,
    Condition,
    Constant,
    ConstantValue,
    Default,
    Feature,
    FeatureStep,
    Formula,
    Function,
    Imply,
    IsDefined,
    Negate,
    Not,
    Numerical,
    Optimize,
    Option,
    Or,
    Path,
    PathAccess,
    Require,
    Row,
    RowKind,
    Visibility,
)

# Truth


class Truth(Flag):
    """The outcomes a condition can still take, a set of TRUE, FALSE and INDEFINITE.

    A decided condition is TRUE or FALSE. A condition that waits for a value is OPEN, both outcomes are possible. A
    condition that faults is INDEFINITE, it is neither true nor false in any completion. Negation and the connectives
    apply the strong Kleene tables to every combination of outcomes, so `TRUE.both(INDEFINITE)` is INDEFINITE and
    `FALSE.both(INDEFINITE)` is FALSE, while `OPEN.both(INDEFINITE)` is FALSE or INDEFINITE.
    """

    TRUE = 1
    FALSE = 2
    INDEFINITE = 4
    OPEN = TRUE | FALSE

    @classmethod
    def of(cls, value: bool) -> Truth:
        return cls.TRUE if value else cls.FALSE

    @property
    def may_be_true(self) -> bool:
        return Truth.TRUE in self

    def negate(self) -> Truth:
        result = Truth(0)
        for outcome in self:
            result |= _NEGATION[outcome]
        return result

    def both(self, other: Truth) -> Truth:
        return _pointwise(self, other, _kleene_and)

    def either(self, other: Truth) -> Truth:
        return _pointwise(self, other, _kleene_or)


_NEGATION = {Truth.TRUE: Truth.FALSE, Truth.FALSE: Truth.TRUE, Truth.INDEFINITE: Truth.INDEFINITE}


def _kleene_and(x: Truth, y: Truth) -> Truth:
    if Truth.FALSE in (x, y):
        return Truth.FALSE
    return Truth.INDEFINITE if Truth.INDEFINITE in (x, y) else Truth.TRUE


def _kleene_or(x: Truth, y: Truth) -> Truth:
    if Truth.TRUE in (x, y):
        return Truth.TRUE
    return Truth.INDEFINITE if Truth.INDEFINITE in (x, y) else Truth.FALSE


def _pointwise(left: Truth, right: Truth, table: Callable[[Truth, Truth], Truth]) -> Truth:
    result = Truth(0)
    for x in left:
        for y in right:
            result |= table(x, y)
    return result


def all_of(truths: Iterable[Truth]) -> Truth:
    """The conjunction of the truths, TRUE for none, taking no further truth once the result is FALSE."""
    result = Truth.TRUE
    for truth in truths:
        result = result.both(truth)
        if result == Truth.FALSE:
            break
    return result


def any_of(truths: Iterable[Truth]) -> Truth:
    """The disjunction of the truths, FALSE for none, taking no further truth once the result is TRUE."""
    result = Truth.FALSE
    for truth in truths:
        result = result.either(truth)
        if result == Truth.TRUE:
            break
    return result


# Values of formulas


class Undefined(Enum):
    """Why a formula has no value, in the order in which the reasons win when operands combine."""

    FAULT = "fault"
    """An operation without a value, such as a division by zero."""
    EXCEEDED = "exceeded"
    """A result too large to represent."""
    OPEN = "open"
    """A slot that exists but holds no value yet."""
    ABSENT = "absent"
    """A slot that does not exist, such as an empty optional slot or an index beyond the last instance."""


type Scalar = Fraction | bool | str | Option | Instance
"""A single value during evaluation, numbers being exact rationals."""


@dataclass(frozen=True, slots=True)
class Sequence:
    """The values a range path addresses, and the number of slots on the way that are open."""

    values: tuple[Scalar, ...]
    open: int = 0

    @property
    def is_complete(self) -> bool:
        return self.open == 0


type Result = Scalar | Sequence | Undefined


def evaluate(formula: Formula, origin: Instance) -> Result:
    """Evaluates a formula for an origin instance."""
    match formula:
        case Constant():
            return _scalar(formula.value)
        case PathAccess():
            return access(formula.path, origin)
        case Negate():
            operand = evaluate(formula.operand, origin)
            if isinstance(operand, Undefined):
                return operand
            return -operand if isinstance(operand, Fraction) else Undefined.OPEN
        case Binary():
            return _calculate(formula.op, [evaluate(formula.left, origin), evaluate(formula.right, origin)])
        case Call() if formula.function in _AGGREGATES:
            return _aggregate(formula.function, [evaluate(argument, origin) for argument in formula.args])
        case Call() if formula.function is Function.ROUND:
            value = evaluate(formula.args[0], origin)
            if isinstance(value, Undefined):
                return value
            return arithmetic.to_grid(value, _digits(formula)) if isinstance(value, Fraction) else Undefined.OPEN
        case Call():
            return _calculate(formula.function, [evaluate(argument, origin) for argument in formula.args])
        case _:
            assert_never(formula)


def _scalar(value: ConstantValue | Instance) -> Scalar:
    return Fraction(value) if isinstance(value, Decimal) else value


def _digits(call: Call) -> int:
    """The digits a rounding rounds to, from an integer literal or from the declared grid of a numeric path."""
    if len(call.args) < 2:
        return 0
    match call.args[1]:
        case Constant(value=Decimal() as digits):
            return int(digits)
        case PathAccess(path=path) if isinstance(path.type, Numerical):
            return path.type.digits
    raise ValueError(f"the digits of {call} are neither a number nor a numeric feature")


# Paths


def access(path: Path, origin: Instance) -> Result:
    """Returns what a path addresses from an origin instance, a sequence if the path is a range."""
    start = origin if origin.type is path.origin else origin.root
    if path.origin is not start.type:
        raise ValueError(f"the path {path} does not start at {origin!r}")
    return _sequence(path, start) if path.is_range else _single(path, start)


def _single(path: Path, start: Instance) -> Result:
    current: Scalar = start
    for step in path.steps:
        match step:
            case FeatureStep(feature=feature):
                if not isinstance(current, Instance):
                    return Undefined.ABSENT
                index = _index(current, feature, step.index.first if step.index else 0)
                assignment = None if index is None else current.assignment(feature, index)
                if index is None or assignment is None:
                    required = index is not None and index < feature.min
                    return Undefined.OPEN if required else Undefined.ABSENT
                current = _scalar(assignment.value)
            case AttributeStep(attribute=attribute):
                if not isinstance(current, Option):
                    return Undefined.ABSENT
                current = _scalar(current.values[attribute])
            case _:
                assert_never(step)
    return current


def _sequence(path: Path, start: Instance) -> Sequence:
    values: list[Scalar] = [start]
    open = 0
    for step in path.steps:
        following: list[Scalar] = []
        for value in values:
            match step:
                case FeatureStep():
                    if isinstance(value, Instance):
                        open += _read_slots(value, step, following)
                case AttributeStep(attribute=attribute):
                    if isinstance(value, Option):
                        following.append(_scalar(value.values[attribute]))
                case _:
                    assert_never(step)
        values = following
    return Sequence(tuple(values), open)


def _read_slots(instance: Instance, step: FeatureStep, values: list[Scalar]) -> int:
    """Appends the values of the slots a step addresses in an instance and returns how many of them are open."""
    feature = step.feature
    if step.is_range:
        last = _last(instance, feature)
        first_index, last_index = (0, -1) if step.index is None else (step.index.first, step.index.last)
        first = max(0, first_index if first_index >= 0 else last + 1 + first_index)
        final = last_index if last_index >= 0 else last + 1 + last_index
        if feature.max is not None:
            final = min(feature.max - 1, final)
    else:
        index = _index(instance, feature, step.index.first if step.index else 0)
        if index is None:
            return 0
        first, final, last = index, index, None
    open = 0
    for index in range(first, final + 1):
        assignment = instance.assignment(feature, index)
        if assignment is not None:
            values.append(_scalar(assignment.value))
        elif index < feature.min:
            open += 1
        elif last is not None and index > last:
            break
    return open


def _last(instance: Instance, feature: Feature) -> int:
    """The last slot of the extent of a feature, which covers the required slots and every filled one."""
    required = feature.min if feature.max is None else min(feature.min, feature.max)
    return max(instance.last_index(feature), required - 1)


def _index(instance: Instance, feature: Feature, index: int) -> int | None:
    """Resolves an index counted from the end, None if it lies outside the cardinality."""
    if index < 0:
        index += _last(instance, feature) + 1
    if index < 0 or (feature.max is not None and index >= feature.max):
        return None
    return index


# Calculations

_AGGREGATES = frozenset({Function.COUNT, Function.SUM, Function.MIN, Function.MAX})

_OPERATIONS: dict[BinaryOp | Function, Callable[..., Fraction]] = {
    BinaryOp.ADD: lambda x, y: x + y,
    BinaryOp.SUB: lambda x, y: x - y,
    BinaryOp.MUL: arithmetic.multiply,
    BinaryOp.DIV: arithmetic.divide,
    BinaryOp.POW: arithmetic.power,
    Function.POW: arithmetic.power,
    Function.MOD: arithmetic.modulo,
    Function.LOG: arithmetic.log,
    Function.LN: arithmetic.ln,
    Function.SQRT: arithmetic.sqrt,
    Function.CEIL: lambda x: Fraction(math.ceil(x)),
    Function.FLOOR: lambda x: Fraction(math.floor(x)),
    Function.SIN: arithmetic.sin,
    Function.COS: arithmetic.cos,
    Function.TAN: arithmetic.tan,
    Function.ASIN: arithmetic.asin,
    Function.ACOS: arithmetic.acos,
    Function.ATAN: arithmetic.atan,
    Function.SINH: arithmetic.sinh,
    Function.COSH: arithmetic.cosh,
    Function.TANH: arithmetic.tanh,
}


def _calculate(operation: BinaryOp | Function, operands: list[Result]) -> Result:
    undefined = [operand for operand in operands if isinstance(operand, Undefined)]
    if undefined:
        return min(undefined, key=list(Undefined).index)
    numbers = [operand for operand in operands if isinstance(operand, Fraction)]
    if len(numbers) != len(operands):
        return Undefined.OPEN
    try:
        return _OPERATIONS[operation](*numbers)
    except arithmetic.Fault:
        return Undefined.FAULT
    except arithmetic.Exceeded:
        return Undefined.EXCEEDED


def _aggregate(function: Function, operands: list[Result]) -> Result:
    """Aggregates over the values of the operands, skipping absent ones and waiting for open ones."""
    for operand in operands:
        if operand in (Undefined.FAULT, Undefined.EXCEEDED):
            return operand
    values: list[Scalar] = []
    for operand in operands:
        match operand:
            case Undefined.OPEN:
                return operand
            case Sequence() if not operand.is_complete:
                return Undefined.OPEN
            case Sequence():
                values.extend(operand.values)
            case Undefined():
                pass
            case _:
                values.append(operand)
    match function:
        case Function.COUNT:
            return Fraction(len(values))
        case Function.SUM:
            numbers = [value for value in values if isinstance(value, Fraction)]
            return sum(numbers, Fraction(0)) if len(numbers) == len(values) else Undefined.OPEN
        case _:
            order = CompareOp.LT if function is Function.MIN else CompareOp.GT
            best: Scalar | None = None
            for value in values:
                if best is None or _atom(order, value, best) == Truth.TRUE:
                    best = value
            return Undefined.OPEN if best is None else best


# Comparisons


def compare(op: CompareOp, left: Formula, right: Formula, origin: Instance) -> Truth:
    """Compares two formulas at the lowest precision among their sides."""
    left_value = evaluate(left, origin)
    if left_value is Undefined.FAULT:
        return Truth.INDEFINITE
    right_value = evaluate(right, origin)
    if right_value is Undefined.FAULT:
        return Truth.INDEFINITE
    if isinstance(left_value, Undefined) or isinstance(right_value, Undefined):
        return Truth.OPEN
    return _decide(op, precision(left), left_value, precision(right), right_value)


def precision(formula: Formula) -> int | None:
    """The digits a side of a comparison contributes, those of a bare numeric path or of a rounding."""
    match formula:
        case PathAccess(path=path) if isinstance(path.type, Numerical):
            return path.type.digits
        case Call(function=Function.ROUND):
            return _digits(formula)
        case _:
            return None


def _decide(
    op: CompareOp, left_digits: int | None, left: Scalar | Sequence, right_digits: int | None, right: Scalar | Sequence
) -> Truth:
    sides = [digits for digits in (left_digits, right_digits) if digits is not None]
    if sides:
        digits = min(sides)
        if left_digits != digits:
            left = _rounded(left, digits)
        if right_digits != digits:
            right = _rounded(right, digits)
    return _values(op, left, right)


def _rounded(value: Scalar | Sequence, digits: int) -> Scalar | Sequence:
    match value:
        case Fraction():
            return arithmetic.to_grid(value, digits)
        case Sequence():
            members = (arithmetic.to_grid(v, digits) if isinstance(v, Fraction) else v for v in value.values)
            return Sequence(tuple(members), value.open)
        case _:
            return value


def _values(op: CompareOp, left: Scalar | Sequence, right: Scalar | Sequence) -> Truth:
    """Compares values, universally over the members of a sequence, which stays OPEN while members are open."""
    match left, right:
        case Sequence(), Sequence():
            return Truth.OPEN
        case Sequence(), _:
            return all_of(_atom(op, value, right) for value in left.values).both(_completeness(left))
        case _, Sequence():
            return all_of(_atom(op, left, value) for value in right.values).both(_completeness(right))
        case _:
            return _atom(op, left, right)


def _completeness(sequence: Sequence) -> Truth:
    return Truth.TRUE if sequence.is_complete else Truth.OPEN


def _atom(op: CompareOp, left: Scalar | Sequence, right: Scalar | Sequence) -> Truth:
    """Compares two single values, INDEFINITE if they cannot be compared by the operator."""
    if op in (CompareOp.EQ, CompareOp.NE):
        equal = _equal(left, right)
        return equal.negate() if op is CompareOp.NE else equal
    order = _order(left, right)
    if order is None:
        return Truth.INDEFINITE
    match op:
        case CompareOp.LT:
            return Truth.of(order < 0)
        case CompareOp.LE:
            return Truth.of(order <= 0)
        case CompareOp.GT:
            return Truth.of(order > 0)
        case CompareOp.GE:
            return Truth.of(order >= 0)
    raise AssertionError(op)


def _equal(left: Scalar | Sequence, right: Scalar | Sequence) -> Truth:
    match left, right:
        case (Instance(), Instance()) | (Option(), Option()):
            return Truth.of(left is right)
        case (bool(), bool()) | (Fraction(), Fraction()) | (str(), str()):
            return Truth.of(left == right)
        case _:
            return Truth.INDEFINITE


def _order(left: Scalar | Sequence, right: Scalar | Sequence) -> int | None:
    match left, right:
        case Fraction(), Fraction():
            return (left > right) - (left < right)
        case str(), str():
            return _text_order(left, right)
        case Option(), Option() if left.owner is right.owner:
            return left.index - right.index
        case _:
            return None


def _text_order(left: str, right: str) -> int:
    """Orders texts by character, except that runs of digits compare by their number."""
    left_key, right_key = _text_key(left), _text_key(right)
    return (left_key > right_key) - (left_key < right_key)


def _text_key(text: str) -> list[tuple[int, int | str]]:
    return [(0, int(part)) if part.isdecimal() else (1, part) for part in re.split(r"([0-9]+)", text) if part]


# Conditions and behaviors


def truth(item: Condition | Behavior, origin: Instance) -> Truth:
    """The truth of a condition or behavior for an origin instance."""
    match item:
        case Compare():
            return compare(item.op, item.left, item.right, origin)
        case IsDefined():
            return _defined(item.formula, origin)
        case Not():
            return truth(item.operand, origin).negate()
        case And():
            return all_of(truth(operand, origin) for operand in item.operands)
        case Or():
            return any_of(truth(operand, origin) for operand in item.operands)
        case Constant(value=bool() as value):
            return Truth.of(value)
        case Constant():
            raise ValueError(f"the constant {item.value} is not a condition")
        case Require():
            return _guarded(item, origin, lambda: truth(item.condition, origin))
        case Imply():
            # an imply whose formula faults cannot derive its value, a default with such a formula is not applied
            return _guarded(item, origin, lambda: _holds(item.target, item.value, origin, Truth.FALSE))
        case Default():
            return _guarded(item, origin, lambda: _holds(item.target, item.value, origin, Truth.TRUE))
        case Combinations():
            return _guarded(item, origin, lambda: _table(item, origin))
        case Optimize() | Visibility():
            return Truth.TRUE
        case _:
            assert_never(item)


def _defined(formula: Formula, origin: Instance) -> Truth:
    """Whether a formula has a truthy value, which excludes false and blank texts."""
    match evaluate(formula, origin):
        case Undefined.FAULT:
            return Truth.INDEFINITE
        case Undefined.OPEN:
            return Truth.OPEN
        case Undefined.EXCEEDED:
            return Truth.TRUE
        case Undefined.ABSENT:
            return Truth.FALSE
        case Sequence() as sequence:
            if any(_truthy(value) for value in sequence.values):
                return Truth.TRUE
            return Truth.FALSE if sequence.is_complete else Truth.OPEN
        case value:
            return Truth.of(_truthy(value))


def _truthy(value: Scalar) -> bool:
    if isinstance(value, bool):
        return value
    return not isinstance(value, str) or bool(value.strip())


def _guarded(behavior: Behavior, origin: Instance, statement: Callable[[], Truth]) -> Truth:
    """A behavior holds where its preconditions cannot hold, and otherwise where its statement holds."""
    guard = all_of(truth(condition, origin) for condition in behavior.conditions)
    if not guard.may_be_true:
        return Truth.TRUE
    fires = Truth.TRUE if guard == Truth.TRUE else Truth.OPEN
    return fires.negate().either(statement())


def _holds(target: Path, formula: Formula, origin: Instance, if_fault: Truth) -> Truth:
    """Whether the target holds the value of the formula, compared at the lowest precision."""
    expected = evaluate(formula, origin)
    if expected is Undefined.FAULT:
        return if_fault
    actual = access(target, origin)
    if isinstance(expected, Undefined) or isinstance(actual, Undefined):
        return Truth.OPEN
    return _decide(CompareOp.EQ, precision(PathAccess(target)), actual, precision(formula), expected)


def _table(table: Combinations, origin: Instance) -> Truth:
    """Some allow row matches, unless there is none, and no forbid row matches."""

    def matches(row: Row) -> Truth:
        cells = zip(table.columns, row.cells, strict=True)
        return all_of(
            any_of(compare(atom.op, column, atom.value, origin) for atom in cell)
            for column, cell in cells
            if cell is not None
        )

    allowed = [matches(row) for row in table.rows if row.kind is RowKind.ALLOW]
    forbidden = [matches(row).negate() for row in table.rows if row.kind is RowKind.FORBID]
    return all_of([any_of(allowed), *forbidden] if allowed else forbidden)


# Configurations


@dataclass(frozen=True, slots=True)
class Verdict:
    """The truth of a behavior for one instance of its origin."""

    behavior: Behavior
    instance: Instance
    truth: Truth

    @property
    def is_hard(self) -> bool:
        """Whether the behavior must hold in a valid configuration, which a default need not."""
        return not isinstance(self.behavior, Default)


def verdicts(configuration: Configuration) -> Iterator[Verdict]:
    """Yields the truth of every require, imply, default and table for every instance of its origin."""
    for behavior in configuration.model.behaviors:
        if isinstance(behavior, Optimize | Visibility):
            continue
        for instance in configuration.instances(behavior.origin):
            yield Verdict(behavior, instance, truth(behavior, instance))
