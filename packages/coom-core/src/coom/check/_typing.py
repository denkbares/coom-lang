"""Typing of formulas and the type rules of conditions, assignments, tables and tests."""

from collections.abc import Iterator
from decimal import Decimal
from typing import NamedTuple, assert_never

from coom.diagnostics import Diagnostic, DiagnosticCode, Severity
from coom.model import (
    And,
    Behavior,
    Binary,
    Boolean,
    Call,
    Combinations,
    Compare,
    CompareOp,
    Condition,
    Constant,
    ConstantValue,
    Default,
    Enumeration,
    FeatureStep,
    Formula,
    Function,
    Imply,
    IsAvailable,
    IsBlocked,
    IsDefined,
    IsEmpty,
    IsFixed,
    IsHidden,
    IsReadonly,
    IsShown,
    Model,
    Negate,
    Not,
    Numerical,
    Optimize,
    Option,
    Or,
    Path,
    PathAccess,
    RemoveValue,
    Require,
    ResetValue,
    SetValue,
    Span,
    Structure,
    TestCase,
    Textual,
    Type,
    Visibility,
    parts,
    type_name,
    walk,
)

NUMBER = Numerical()
"""The type of computed numbers, whose grid and bounds do not matter for typing."""

AGGREGATES = frozenset({Function.COUNT, Function.SUM, Function.MIN, Function.MAX})
EQUALITIES = frozenset({CompareOp.EQ, CompareOp.NE})


class Typed(NamedTuple):
    """The type of a formula, a collection if the formula may evaluate to several values."""

    base: Type
    collection: bool = False


def describe(typed: Typed) -> str:
    """Names the type for messages, such as "a number" or "a collection of options of Color"."""
    match typed.base:
        case Numerical():
            single, plural = "a number", "numbers"
        case Textual():
            single, plural = "a text", "texts"
        case Boolean():
            single, plural = "a truth value", "truth values"
        case Enumeration():
            single, plural = f"an option of {typed.base.name}", f"options of {typed.base.name}"
        case Structure():
            name = "the product" if typed.base.is_root else typed.base.name
            single, plural = f"an instance of {name}", f"instances of {name}"
        case _:
            assert_never(typed.base)
    return f"a collection of {plural}" if typed.collection else single


def comparable(op: CompareOp, left: Type, right: Type) -> bool:
    """Whether values of the two types can be compared by the operator, ignoring collections."""
    match left, right:
        case (Numerical(), Numerical()) | (Textual(), Textual()):
            return True
        case Enumeration(), Enumeration():
            return left is right
        case (Boolean(), Boolean()):
            return op in EQUALITIES
        case Structure(), Structure():
            return left is right and op in EQUALITIES
        case _:
            return False


def constant_type(value: ConstantValue) -> Type:
    match value:
        case bool():
            return Boolean()
        case Decimal():
            return NUMBER
        case str():
            return Textual()
        case Option():
            return value.owner
        case _:
            assert_never(value)


def in_range(numerical: Numerical, value: Decimal) -> bool:
    return (numerical.min is None or value >= numerical.min) and (numerical.max is None or value <= numerical.max)


class TypeChecker:
    """Infers the types of formulas and reports where the type rules of the language are violated."""

    def __init__(self) -> None:
        self.diagnostics: list[Diagnostic] = []

    def error(self, span: Span | None, code: DiagnosticCode, message: str) -> None:
        self.diagnostics.append(Diagnostic(Severity.ERROR, code, message, span))

    # Formulas

    def formula(self, formula: Formula) -> Typed | None:
        """Returns the type of a formula, or None if it has a type error that is already reported."""
        match formula:
            case Constant():
                return Typed(constant_type(formula.value))
            case PathAccess():
                self.path(formula.path)
                return Typed(formula.path.type, formula.path.is_range)
            case Negate():
                return Typed(NUMBER) if self.number(formula.operand) else None
            case Binary():
                left, right = self.number(formula.left), self.number(formula.right)
                return Typed(NUMBER) if left and right else None
            case Call():
                return self._call(formula)
            case _:
                assert_never(formula)

    def number(self, formula: Formula) -> bool:
        """Checks that a formula is a single number, as arithmetic requires."""
        typed = self.formula(formula)
        if typed is None:
            return False
        if typed.collection:
            self.error(formula.span, DiagnosticCode.TYPE, f"arithmetic needs a single number, not {describe(typed)}")
            return False
        if not isinstance(typed.base, Numerical):
            self.error(formula.span, DiagnosticCode.TYPE, f"arithmetic needs a number, not {describe(typed)}")
            return False
        return True

    def _call(self, call: Call) -> Typed | None:
        if call.function not in AGGREGATES:
            valid = [self.number(argument) for argument in call.args]
            return Typed(NUMBER) if all(valid) else None
        types = [self.formula(argument) for argument in call.args]
        if any(typed is None for typed in types):
            return None
        bases = [typed.base for typed in types if typed is not None]
        match call.function:
            case Function.COUNT:
                return Typed(NUMBER)
            case Function.SUM:
                if not all(isinstance(base, Numerical) for base in bases):
                    self.error(call.span, DiagnosticCode.TYPE, "sum needs numbers")
                    return None
                return Typed(NUMBER)
            case _:
                first = bases[0]
                if not all(comparable(CompareOp.LT, first, other) for other in bases):
                    self.error(
                        call.span,
                        DiagnosticCode.TYPE,
                        f"{call.function} needs values that can be ordered against each other",
                    )
                    return None
                return Typed(NUMBER if isinstance(first, Numerical) else first)

    def path(self, path: Path) -> None:
        for step in path.steps:
            index = step.index if isinstance(step, FeatureStep) else None
            if index is not None and (index.first >= 0) == (index.last >= 0) and index.first > index.last:
                self.error(step.span, DiagnosticCode.STRUCTURE, f"the index range [{index}] is empty")

    # Conditions

    def condition(self, condition: Condition) -> None:
        match condition:
            case Compare():
                self.compare(condition.op, condition.left, condition.right, condition.span)
            case IsDefined():
                self.formula(condition.formula)
            case Not():
                self.condition(condition.operand)
            case And() | Or():
                for operand in condition.operands:
                    self.condition(operand)
            case Constant():
                pass
            case _:
                assert_never(condition)

    def compare(self, op: CompareOp, left: Formula, right: Formula, span: Span | None) -> None:
        left_type, right_type = self.formula(left), self.formula(right)
        if left_type is None or right_type is None:
            return
        if left_type.collection and right_type.collection:
            self.error(span, DiagnosticCode.TYPE, "cannot compare two collections with each other")
        elif not comparable(op, left_type.base, right_type.base):
            self.error(
                span, DiagnosticCode.TYPE, f"cannot compare {describe(left_type)} with {describe(right_type)} by {op}"
            )

    # Assignments

    def assignment(self, target: Path, value: Formula, span: Span | None) -> None:
        """Checks a value written to a feature, by imply, default or a test step."""
        self.path(target)
        if isinstance(target.type, Structure):
            self.error(span, DiagnosticCode.TYPE, f"cannot assign a value to the structure feature {target}")
            return
        typed = self.formula(value)
        if typed is None:
            return
        if typed.collection:
            self.error(value.span, DiagnosticCode.TYPE, f"cannot assign {describe(typed)} to {target}")
        elif not comparable(CompareOp.EQ, target.type, typed.base):
            self.error(
                value.span,
                DiagnosticCode.TYPE,
                f"cannot assign {describe(typed)} to {target}, which holds {type_name(target.type)}",
            )
        elif (
            isinstance(value, Constant)
            and isinstance(value.value, Decimal)
            and isinstance(target.type, Numerical)
            and not in_range(target.type, value.value)
        ):
            self.error(
                value.span,
                DiagnosticCode.TYPE,
                f"{value.value} is outside the range {type_name(target.type)} of {target}",
            )

    # Model items

    def behavior(self, behavior: Behavior) -> None:
        for condition in behavior.conditions:
            self.condition(condition)
        match behavior:
            case Require():
                self.condition(behavior.condition)
            case Imply() | Default():
                self.assignment(behavior.target, behavior.value, behavior.span)
            case Optimize():
                self.path(behavior.target)
                if not isinstance(behavior.target.type, Numerical):
                    self.error(
                        behavior.span,
                        DiagnosticCode.TYPE,
                        f"{behavior.direction} needs a numeric feature, not {behavior.target}",
                    )
            case Visibility():
                self.path(behavior.target)
            case Combinations():
                for column in behavior.columns:
                    self.formula(column)
                for row in behavior.rows:
                    for column, cell in zip(behavior.columns, row.cells, strict=True):
                        for atom in cell or ():
                            self.compare(atom.op, column, atom.value, atom.span)
            case _:
                assert_never(behavior)

    def test(self, test: TestCase) -> None:
        for step in test.steps:
            match step:
                case SetValue() | IsFixed() | IsShown() | IsAvailable() | IsBlocked() | IsHidden():
                    if step.value is None:
                        self.path(step.path)
                    else:
                        self.assignment(step.path, step.value, step.span)
                case RemoveValue() | ResetValue() | IsEmpty() | IsReadonly():
                    self.path(step.path)
                case _:
                    assert_never(step)

    def options(self, enumeration: Enumeration) -> None:
        for option in enumeration.options:
            for attribute, value in option.values.items():
                numerical = attribute.type
                if isinstance(numerical, Numerical) and isinstance(value, Decimal) and not in_range(numerical, value):
                    self.error(
                        option.span,
                        DiagnosticCode.TYPE,
                        f"{value} is outside the range {type_name(numerical)} of the attribute {attribute.name}",
                    )


def check_types(model: Model) -> Iterator[Diagnostic]:
    checker = TypeChecker()
    for enumeration in model.enumerations:
        checker.options(enumeration)
    for behavior in model.behaviors:
        checker.behavior(behavior)
    for test in model.tests:
        checker.test(test)
    yield from checker.diagnostics


def formula_type(formula: Formula) -> Typed | None:
    """Returns the type of a formula without reporting, None if the formula has a type error."""
    return TypeChecker().formula(formula)


def formulas(item: Behavior | TestCase) -> Iterator[Formula]:
    """Yields every formula of a behavior or test, nested ones included."""
    for node in walk(*parts(item)):
        if isinstance(node, Constant | PathAccess | Negate | Binary | Call):
            yield node
