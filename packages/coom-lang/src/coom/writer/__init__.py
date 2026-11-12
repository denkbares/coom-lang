"""Writing a model as COOM text."""

import json
from collections import Counter
from collections.abc import Iterator, Sequence
from decimal import Decimal
from functools import cache
from typing import assert_never

from antlr4 import InputStream
from antlr4.Token import Token

from coom.model import (
    BOOLEAN_NAME,
    And,
    Behavior,
    Binary,
    BinaryOp,
    Boolean,
    Call,
    Cell,
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
    Structure,
    TestCase,
    TestStep,
    Textual,
    Type,
    Visibility,
    value_type,
)
from coom.parser._antlr.COOMLexer import COOMLexer

INDENT = "    "

# Binding strength of formulas, the operands of an operator bind at least as strong as the grammar requires.
_SUM, _PRODUCT, _SIGN, _POWER, _ATOM = range(5)
_BINARY = {
    BinaryOp.ADD: _SUM,
    BinaryOp.SUB: _SUM,
    BinaryOp.MUL: _PRODUCT,
    BinaryOp.DIV: _PRODUCT,
    BinaryOp.POW: _POWER,
}

# Binding strength of conditions. Comparisons bind as strong as negations but are put in parentheses after a "!".
_OR, _AND, _COMPARE, _UNARY = range(4)


def write(model: Model) -> str:
    """Returns COOM text that compiles to a model equal to the given one.

    The text declares the product, structures and enumerations in the order of the model, followed by its behaviors
    and tests. Statements appear as the compiler produced them, so definitions are substituted and derivation tables
    are expanded into single statements. Comments of the source are not part of the model and are not written.
    """
    return _Writer(model).model()


class _Writer:
    def __init__(self, model: Model) -> None:
        self.model_ = model

    def model(self) -> str:
        model = self.model_
        blocks = [self.structure(model.root), *map(self.structure, model.structures)]
        blocks += map(self.enumeration, model.enumerations)
        blocks += self.behaviors(model.behaviors)
        blocks += map(self.test, model.tests)
        return "\n\n".join(blocks) + "\n"

    # Declarations

    def structure(self, structure: Structure) -> str:
        header = "product" if structure.is_root else f"structure {_name(structure.name)}"
        rows = [
            (_cardinality(feature.min, feature.max), self.type(feature.type), _name(feature.name))
            for feature in structure.features
        ]
        return _braced(header, _table(rows))

    def enumeration(self, enumeration: Enumeration) -> str:
        header = f"enumeration {_name(enumeration.name)}"
        options = [_name(option.name) for option in enumeration.options]
        if not enumeration.attributes:
            return f"{header} {{ {'; '.join(options)} }}"
        attributes = _table(
            [("attribute", self.type(attribute.type), _name(attribute.name)) for attribute in enumeration.attributes]
        )
        values = [
            f"= ({' '.join(self.attribute_value(option.values[attribute]) for attribute in enumeration.attributes)})"
            for option in enumeration.options
        ]
        return _braced(header, [*attributes, "", *_table(list(zip(options, values, strict=True)))])

    def type(self, type_: Type) -> str:
        match type_:
            case Structure() | Enumeration():
                return _name(type_.name)
            case Numerical():
                text = "num"
                if type_.digits:
                    text += "." + "#" * type_.digits
                if type_.unit is not None:
                    text += f" /{_unit(type_.unit)}"
                if type_.min is not None or type_.max is not None:
                    text += f" {_bound(type_.min)}-{_bound(type_.max)}"
                return text
            case Textual():
                return "string"
            case Boolean():
                return BOOLEAN_NAME
            case _:
                assert_never(type_)

    def attribute_value(self, value: ConstantValue) -> str:
        match value:
            case bool():
                return "true" if value else "false"
            case Decimal():
                return _number(value)
            case str():
                return _text(value)
            case Option():
                return _name(value.name)
            case _:
                assert_never(value)

    # Behaviors

    def behaviors(self, behaviors: Sequence[Behavior]) -> Iterator[str]:
        """Writes each run of behaviors with the same origin as one behavior block."""
        start = 0
        while start < len(behaviors):
            origin = behaviors[start].origin
            end = start + 1
            while end < len(behaviors) and behaviors[end].origin is origin:
                end += 1
            header = "behavior" if origin.is_root else f"behavior {_name(origin.name)}"
            yield _braced(header, list(self.statements(behaviors[start:end], 0, None)))
            start = end

    def statements(self, behaviors: Sequence[Behavior], written: int, explained: str | None) -> Iterator[str]:
        """Writes behaviors whose first preconditions and explanation are already written by enclosing blocks.

        Behaviors that share their next precondition are written in a condition block, which also states the most
        common explanation if all of them have one.
        """
        start = 0
        while start < len(behaviors):
            first = behaviors[start]
            end = start + 1
            if len(first.conditions) > written:
                shared = first.conditions[written]
                while (
                    end < len(behaviors)
                    and len(behaviors[end].conditions) > written
                    and behaviors[end].conditions[written] == shared
                ):
                    end += 1
            if end - start > 1:
                group = behaviors[start:end]
                explanations = [behavior.explanation for behavior in group]
                explanation = explained
                if None not in explanations:
                    explanation = Counter(explanations).most_common(1)[0][0]
                header = self.explanation(explanation, explained) + f"condition {self.condition(shared)}"
                inner = list(self.statements(group, written + 1, explanation))
                yield from _braced(header, inner).splitlines()
            else:
                yield self.statement(first, written, explained)
            start = end

    def explanation(self, explanation: str | None, explained: str | None) -> str:
        return "" if explanation is None or explanation == explained else f"explanation {_text(explanation)} "

    def statement(self, behavior: Behavior, written: int, explained: str | None) -> str:
        prefix = self.explanation(behavior.explanation, explained)
        prefix += "".join(f"condition {self.condition(c)} " for c in behavior.conditions[written:])
        match behavior:
            case Require():
                return f"{prefix}require {self.condition(behavior.condition)}"
            case Imply():
                return f"{prefix}imply {self.assignment(behavior.target, behavior.value)}"
            case Default():
                priority = "" if behavior.priority is None else f"/{behavior.priority}"
                return f"{prefix}default{priority} {self.assignment(behavior.target, behavior.value)}"
            case Optimize():
                return f"{prefix}{behavior.direction} {self.path(behavior.target)}"
            case Visibility():
                options = "".join(f" {_name(option.name)}" for option in behavior.options)
                return f"{prefix}{behavior.directive} {self.path(behavior.target)}{options}"
            case Combinations():
                columns = ", ".join(self.formula(column) for column in behavior.columns)
                lines = [f"{prefix}combinations ({columns})"]
                for row in behavior.rows:
                    cells = map(self.cell, behavior.columns, row.cells)
                    lines.append(f"{INDENT}{row.kind} ({', '.join(cells)})")
                return "\n".join(lines)
            case _:
                assert_never(behavior)

    def assignment(self, target: Path, value: Formula) -> str:
        return f"{self.path(target)} = {self.formula(value, target.type)}"

    def cell(self, column: Formula, cell: Cell | None) -> str:
        if cell is None:
            return "-*-"
        expected = value_type(column)
        atoms = [
            ("" if atom.op is CompareOp.EQ else f"{atom.op} ") + self.formula(atom.value, expected) for atom in cell
        ]
        return atoms[0] if len(atoms) == 1 else f"({', '.join(atoms)})"

    # Tests

    def test(self, test: TestCase) -> str:
        header = "test" if test.origin.is_root else f"test {_name(test.origin.name)}"
        return _braced(header, [self.step(step) for step in test.steps])

    def step(self, step: TestStep) -> str:
        match step:
            case SetValue():
                keyword = "set"
            case RemoveValue():
                keyword = "remove"
            case ResetValue():
                keyword = "reset"
            case IsFixed():
                keyword = "isFixed"
            case IsShown():
                keyword = "isShown"
            case IsEmpty():
                keyword = "isEmpty"
            case IsAvailable():
                keyword = "isAvailable"
            case IsBlocked():
                keyword = "isBlocked"
            case IsHidden():
                keyword = "isHidden"
            case IsReadonly():
                keyword = "isReadonly"
            case _:
                assert_never(step)
        text = f"{keyword} {self.path(step.path)}"
        value = getattr(step, "value", None)
        return text if value is None else f"{text} = {self.formula(value, step.path.type)}"

    # Conditions

    def condition(self, condition: Condition, strength: int = _OR) -> str:
        match condition:
            case Or():
                text, own = " || ".join(self.condition(c, _AND) for c in condition.operands), _OR
            case And():
                text, own = " && ".join(self.condition(c, _COMPARE) for c in condition.operands), _AND
            case Compare():
                right = self.formula(condition.right, value_type(condition.left))
                text, own = f"{self.formula(condition.left)} {condition.op} {right}", _COMPARE
            case Not():
                text, own = f"!{self.condition(condition.operand, _UNARY)}", _UNARY
            case IsDefined():
                text, own = self.formula(condition.formula), _UNARY
            case Constant():
                text, own = self.formula(condition), _UNARY
            case _:
                assert_never(condition)
        return text if own >= strength else f"({text})"

    # Formulas

    def formula(self, formula: Formula, expected: Type | None = None, strength: int = _SUM) -> str:
        """Writes a formula where the options of the expected type may be referred to by their bare names."""
        match formula:
            case Constant():
                text = self.constant(formula.value, expected)
                own = _SIGN if text.startswith("-") else _ATOM
            case PathAccess():
                text, own = self.path(formula.path, expected), _ATOM
            case Negate():
                text, own = f"-{self.formula(formula.operand, expected, _SIGN)}", _SIGN
            case Binary(op=BinaryOp.POW):
                base = self.formula(formula.left, expected, _ATOM)
                text, own = f"{base} ^ {self.formula(formula.right, expected, _SIGN)}", _POWER
            case Binary():
                own = _BINARY[formula.op]
                left = self.formula(formula.left, expected, own)
                text = f"{left} {formula.op} {self.formula(formula.right, expected, own + 1)}"
            case Call():
                text = f"{formula.function}({', '.join(self.formula(arg, expected) for arg in formula.args)})"
                own = _ATOM
            case _:
                assert_never(formula)
        return text if own >= strength else f"({text})"

    def constant(self, value: ConstantValue, expected: Type | None) -> str:
        if isinstance(value, Option) and value.owner is not expected:
            return f"{_name(value.owner.name)}.{_name(value.name)}"
        return self.attribute_value(value)

    def path(self, path: Path, expected: Type | None = None) -> str:
        """Writes a path, starting it with this where its first name would otherwise denote something else."""
        parts = []
        for step in path.steps:
            if isinstance(step, FeatureStep):
                index = "" if step.index is None else f"[{step.index}]"
                parts.append(_name(step.feature.name) + index)
            else:
                parts.append(_name(step.attribute.name))
        if path.rooted:
            return ".".join(["root", *parts])
        if not path.steps or self.shadowed(path, expected):
            return ".".join(["this", *parts])
        return ".".join(parts)

    def shadowed(self, path: Path, expected: Type | None) -> bool:
        first = path.steps[0]
        assert isinstance(first, FeatureStep)
        name = first.feature.name
        if name in ("this", "root"):
            return True
        if isinstance(expected, Enumeration) and any(option.name == name for option in expected.options):
            return True
        if isinstance(expected, Boolean) and name in ("true", "false"):
            return True
        # Two names starting with an enumeration and one of its options denote that option.
        if first.index is None and len(path.steps) > 1:
            second = path.steps[1]
            try:
                enumeration = self.model_.type(name)
            except KeyError:
                return False
            if isinstance(enumeration, Enumeration) and isinstance(second, FeatureStep):
                return any(option.name == second.feature.name for option in enumeration.options)
        return False


def _braced(header: str, lines: Sequence[str]) -> str:
    if not lines:
        return f"{header} {{ }}"
    body = "\n".join(INDENT + line if line else "" for line in "\n".join(lines).splitlines())
    return f"{header} {{\n{body}\n}}"


def _table(rows: Sequence[Sequence[str]]) -> list[str]:
    """Aligns the columns of rows, leaving out columns that are empty in every row."""
    columns = [column for column in zip(*rows, strict=True) if any(column)]
    widths = [max(map(len, column)) for column in columns]
    lines = []
    for row in zip(*columns, strict=True) if columns else ():
        lines.append(" ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip())
    return lines


def _cardinality(low: int, high: int | None) -> str:
    if high == low:
        return "" if low == 1 else str(low)
    return f"{low}..{'*' if high is None else high}"


def _number(value: Decimal) -> str:
    return format(value, "f")


def _bound(value: Decimal | None) -> str:
    return "*" if value is None else _number(value)


def _text(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _name(name: str) -> str:
    """Returns a name as it is written, in single quotes if it is not a plain name."""
    if _token(name) in (COOMLexer.NAME, COOMLexer.FUNCTION):
        return name
    return _quoted(name)


def _unit(unit: str) -> str:
    plain = (COOMLexer.NAME, COOMLexer.FUNCTION, COOMLexer.INTEGER, COOMLexer.FLOATING, COOMLexer.HASHES)
    return unit if _token(unit) in plain else _quoted(unit)


def _quoted(name: str) -> str:
    # Single quoted names know no escape for the single quote itself, so it is written as a unicode escape.
    return "'" + json.dumps(name, ensure_ascii=False)[1:-1].replace('\\"', '"').replace("'", "\\u0027") + "'"


@cache
def _token(text: str) -> int | None:
    """Returns the type of the single token the text consists of, None if it is not exactly one token."""
    lexer = COOMLexer(InputStream(text))
    lexer.removeErrorListeners()
    tokens = lexer.getAllTokens()
    if len(tokens) != 1 or tokens[0].text != text or tokens[0].channel != Token.DEFAULT_CHANNEL:
        return None
    token_type: int = tokens[0].type
    return token_type
