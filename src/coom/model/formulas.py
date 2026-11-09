"""Arithmetic formulas and the conditions built from them."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from enum import StrEnum

from coom.model._base import Span, span_field
from coom.model.paths import Path
from coom.model.types import Boolean, ConstantValue, Option, Type


class BinaryOp(StrEnum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    POW = "^"


class CompareOp(StrEnum):
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "="
    NE = "!="


class Function(StrEnum):
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    POW = "pow"
    SQRT = "sqrt"
    CEIL = "ceil"
    FLOOR = "floor"
    ROUND = "round"
    MOD = "mod"
    LOG = "log"
    LN = "ln"
    SIN = "sin"
    ASIN = "asin"
    SINH = "sinh"
    COS = "cos"
    ACOS = "acos"
    COSH = "cosh"
    TAN = "tan"
    ATAN = "atan"
    TANH = "tanh"


@dataclass(frozen=True, slots=True)
class Constant:
    """A literal number, truth value, text or option, also usable as a condition if it is a truth value."""

    value: ConstantValue
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class PathAccess:
    """The value or, for a range path, the sequence of values a path addresses."""

    path: Path
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class Negate:
    operand: Formula
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class Binary:
    op: BinaryOp
    left: Formula
    right: Formula
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class Call:
    function: Function
    args: tuple[Formula, ...]
    _: KW_ONLY
    span: Span | None = span_field()


type Formula = Constant | PathAccess | Negate | Binary | Call


def value_type(formula: Formula) -> Type | None:
    """Returns the type of the values of a formula where it is evident without type checking, otherwise None.

    This is the type a path leads to, the enumeration of an option constant, the boolean type of a truth constant, and
    for min and max the type of their first argument. Arithmetic, counts and other constants give None.
    """
    match formula:
        case PathAccess():
            return formula.path.type
        case Constant(value=Option() as option):
            return option.owner
        case Constant(value=bool()):
            return Boolean()
        case Call(function=Function.MIN | Function.MAX, args=(first, *_)):
            return value_type(first)
        case _:
            return None


@dataclass(frozen=True, slots=True)
class Compare:
    op: CompareOp
    left: Formula
    right: Formula
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsDefined:
    """Holds if the formula has a value, which is how a bare formula reads as a condition."""

    formula: Formula
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class Not:
    operand: Condition
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class And:
    operands: tuple[Condition, ...]
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class Or:
    operands: tuple[Condition, ...]
    _: KW_ONLY
    span: Span | None = span_field()


type Condition = Compare | IsDefined | Not | And | Or | Constant
