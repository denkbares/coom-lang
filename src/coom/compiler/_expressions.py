"""Compilation of paths, formulas and conditions with the names that are visible at their position."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from antlr4.tree.Tree import TerminalNode

from coom.compiler._context import Abort, Compilation, children, name, need, unquote
from coom.model import (
    And,
    AttributeStep,
    Binary,
    BinaryOp,
    Call,
    Compare,
    CompareOp,
    Condition,
    Constant,
    Enumeration,
    FeatureStep,
    Formula,
    Function,
    Index,
    IsDefined,
    Negate,
    Not,
    Option,
    Or,
    Path,
    PathAccess,
    Span,
    Step,
    Structure,
    Type,
)
from coom.parser import token_span
from coom.parser._antlr.COOMParser import COOMParser

ARITY: Mapping[Function, tuple[int, int | None]] = {
    Function.COUNT: (1, None),
    Function.MIN: (1, None),
    Function.MAX: (1, None),
    Function.SUM: (1, None),
    Function.ROUND: (1, 2),
    Function.POW: (2, 2),
    Function.MOD: (2, 2),
    Function.LOG: (2, 2),
}
"""The minimum and maximum number of arguments of a function, None meaning any, one argument if not listed."""


@dataclass(frozen=True, slots=True)
class Scope:
    """The names visible at a position, searched from the innermost frame outwards.

    A frame either holds definitions, from define statements and the implicit this and root, or makes the options of
    an enumeration visible, which happens where a value is compared with or assigned to a value of that enumeration.
    """

    parent: Scope | None = None
    definitions: Mapping[str, Formula] = field(default_factory=dict)
    enumeration: Enumeration | None = None

    @staticmethod
    def of(compilation: Compilation, origin: Structure) -> Scope:
        return Scope(
            definitions={
                "this": PathAccess(Path(origin)),
                "root": PathAccess(Path(compilation.root, rooted=True)),
            }
        )

    def define(self, name: str, formula: Formula) -> Scope:
        return Scope(self, {name: formula})

    def expecting(self, type_: Type | None) -> Scope:
        return Scope(self, enumeration=type_) if isinstance(type_, Enumeration) else self

    def lookup(self, name: str) -> Formula | None:
        scope: Scope | None = self
        while scope is not None:
            if scope.enumeration is not None:
                for option in scope.enumeration.options:
                    if option.name == name:
                        return Constant(option)
            elif name in scope.definitions:
                return scope.definitions[name]
            scope = scope.parent
        return None


def value_type(formula: Formula) -> Type | None:
    """Returns the type of a formula as far as name resolution needs it, the enumeration of an option for example."""
    match formula:
        case PathAccess():
            return formula.path.type
        case Constant(value=Option() as option):
            return option.owner
        case _:
            return None


class Expressions:
    """Compiles the expressions of one behavior block or test, whose relative paths start at the origin."""

    def __init__(self, compilation: Compilation, origin: Structure) -> None:
        self.compilation = compilation
        self.origin = origin

    # Formulas

    def formula(self, node: Any, scope: Scope) -> Formula:
        match need(node):
            case COOMParser.FormulaContext():
                return self.formula(node.formula_add(), scope)
            case COOMParser.Formula_addContext() | COOMParser.Formula_mulContext():
                return self._infix(node, scope)
            case COOMParser.Formula_signContext():
                if node.neg is not None:
                    operand = self.formula(node.neg, scope)
                    if isinstance(operand, Constant) and isinstance(operand.value, Decimal):
                        return Constant(-operand.value, span=self.compilation.span(node))
                    return Negate(operand, span=self.compilation.span(node))
                if node.formula_sign() is not None:
                    return self.formula(node.formula_sign(), scope)
                return self.formula(node.formula_pow(), scope)
            case COOMParser.Formula_powContext():
                base = self.formula(node.formula_primary(), scope)
                if node.formula_sign() is None:
                    return base
                exponent = self.formula(node.formula_sign(), scope)
                return Binary(BinaryOp.POW, base, exponent, span=self.compilation.span(node))
            case COOMParser.Formula_primaryContext():
                inner = node.formula_func() or node.formula_atom() or node.formula()
                return self.formula(inner, scope)
            case COOMParser.Formula_funcContext():
                return self._call(node, scope)
            case COOMParser.Formula_atomContext():
                return self._atom(node, scope)
            case _:
                raise Abort

    def _infix(self, node: Any, scope: Scope) -> Formula:
        result: Formula | None = None
        operator = None
        for child in children(node):
            if isinstance(child, TerminalNode):
                operator = BinaryOp(child.getText())
                continue
            operand = self.formula(child, scope)
            if result is None:
                result = operand
            else:
                result = Binary(need(operator), result, operand, span=self._between(node.start, child.stop))
        if result is None:
            raise Abort
        return result

    def _call(self, node: Any, scope: Scope) -> Formula:
        function = Function(need(node.fun).text)
        args = tuple(self.formula(argument, scope) for argument in node.formula())
        low, high = ARITY.get(function, (1, 1))
        if len(args) < low or (high is not None and len(args) > high):
            expected = f"at least {low}" if high is None else str(low) if low == high else f"{low} or {high}"
            self.compilation.fail(node, f"{function} expects {expected} arguments but got {len(args)}")
        return Call(function, args, span=self.compilation.span(node))

    def _atom(self, node: Any, scope: Scope) -> Formula:
        span = self.compilation.span(node)
        if node.atom_true is not None:
            return Constant(True, span=span)
        if node.atom_false is not None:
            return Constant(False, span=span)
        if node.atom_num is not None:
            return Constant(Decimal(node.atom_num.getText()), span=span)
        return self._path_or_value(need(node.atom_path), scope)

    def _path_or_value(self, node: Any, scope: Scope) -> Formula:
        items = node.path_item()
        first = need(items[0] if items else None)
        text = need(first.name()).getText()
        if len(items) == 1 and not first.path_index():
            bound = scope.lookup(unquote(text))
            if bound is not None:
                return _respan(bound, self.compilation.span(node))
            if text.startswith('"'):
                return Constant(unquote(text), span=self.compilation.span(node))
        if len(items) >= 2 and (constant := self._static_option(items)) is not None:
            return constant
        return PathAccess(self.path(node, scope), span=self.compilation.span(node))

    def _static_option(self, items: list[Any]) -> Constant | None:
        """Resolves Type.option and its attribute values, as in Size.large.volume, to a constant."""
        enumeration = self.compilation.types.get(name(items[0].name()))
        if not isinstance(enumeration, Enumeration) or items[0].path_index() or items[1].path_index():
            return None
        try:
            value: Any = enumeration.option(name(items[1].name()))
        except KeyError:
            return None
        for item in items[2:]:
            if not isinstance(value, Option) or item.path_index():
                self.compilation.fail(item, f"cannot access {item.getText()} on the value {value}")
            try:
                value = value.value(name(item.name()))
            except KeyError:
                self.compilation.fail(item, f"{value.owner.name} has no attribute {item.getText()}")
        return Constant(value, span=self._between(items[0].start, items[-1].stop))

    # Paths

    def path(self, node: Any, scope: Scope) -> Path:
        items = need(node).path_item()
        first = need(items[0] if items else None)
        bound = scope.lookup(name(first.name()))
        if isinstance(bound, PathAccess):
            base = bound.path
            steps = list(base.steps)
            if first.path_index():
                if not steps or not isinstance(steps[-1], FeatureStep):
                    self.compilation.fail(first, f"{first.name().getText()} cannot be indexed")
                last = steps[-1]
                assert isinstance(last, FeatureStep)
                steps[-1] = FeatureStep(last.feature, self._index(first, last.feature.max), span=last.span)
            rest = items[1:]
        elif bound is not None:
            self.compilation.fail(first, f"{first.name().getText()} is a value and cannot start a path")
        else:
            base = Path(self.origin)
            steps = []
            rest = items
        for item in rest:
            steps.append(self._step(item, steps[-1].type if steps else base.origin))
        return Path(base.origin, tuple(steps), rooted=base.rooted, span=self.compilation.span(node))

    def assignable(self, node: Any, scope: Scope) -> Path:
        """Compiles a path that a statement assigns to, which must end at a feature."""
        path = self.path(node, scope)
        if not path.steps:
            self.compilation.fail(node, "cannot assign to the origin structure itself")
        if isinstance(path.steps[-1], AttributeStep):
            self.compilation.fail(node, "cannot assign to an attribute")
        return path

    def _step(self, item: Any, current: Type) -> Step:
        step_name = name(item.name())
        span = self.compilation.span(item)
        match current:
            case Structure():
                try:
                    feature = current.feature(step_name)
                except KeyError:
                    self.compilation.fail(item, f"{_display(current)} has no feature {step_name}")
                index = self._index(item, feature.max) if item.path_index() else None
                return FeatureStep(feature, index, span=span)
            case Enumeration():
                if item.path_index():
                    self.compilation.fail(item, f"the attribute {step_name} cannot be indexed")
                try:
                    return AttributeStep(current.attribute(step_name), span=span)
                except KeyError:
                    self.compilation.fail(item, f"{current.name} has no attribute {step_name}")
            case _:
                self.compilation.fail(item, f"cannot access {step_name} on a number or text")

    def _index(self, item: Any, maximum: int | None) -> Index:
        bounds = []
        for index_node in item.path_index():
            text = index_node.getText()
            value = -1 - (int(text[5:]) if len(text) > 4 else 0) if text.startswith("last") else int(text)
            if maximum is not None and (value >= maximum if value >= 0 else -value > maximum):
                self.compilation.fail(index_node, f"the index {text} exceeds the maximum cardinality {maximum}")
            bounds.append(value)
        return Index(bounds[0], bounds[-1])

    # Conditions

    def condition(self, node: Any, scope: Scope) -> Condition:
        match need(node):
            case COOMParser.ConditionContext():
                return self.condition(node.condition_or(), scope)
            case COOMParser.Condition_orContext():
                operands = tuple(self.condition(child, scope) for child in node.condition_and())
                return operands[0] if len(operands) == 1 else Or(operands, span=self.compilation.span(node))
            case COOMParser.Condition_andContext():
                operands = tuple(self.condition(child, scope) for child in node.condition_not())
                return operands[0] if len(operands) == 1 else And(operands, span=self.compilation.span(node))
            case COOMParser.Condition_notContext():
                if node.condition_not() is not None:
                    return Not(self.condition(node.condition_not(), scope), span=self.compilation.span(node))
                if node.condition() is not None:
                    return self.condition(node.condition(), scope)
                return self.condition(node.condition_compare(), scope)
            case COOMParser.Condition_compareContext():
                return self._compare(node, scope)
            case _:
                raise Abort

    def _compare(self, node: Any, scope: Scope) -> Condition:
        left = self.formula(node.formula(), scope)
        parts = node.condition_part()
        if not parts:
            if isinstance(left, Constant) and isinstance(left.value, bool):
                return left
            return IsDefined(left, span=self.compilation.span(node))
        # A chain such as a < b < c means a < b and b < c, each right side sees the options of its left side.
        compares: list[Condition] = []
        start = node.start
        for part in parts:
            right = self.formula(part.formula(), scope.expecting(value_type(left)))
            operator = CompareOp(need(part.operator).getText())
            compares.append(Compare(operator, left, right, span=self._between(start, part.stop)))
            left, start = right, need(part.formula()).start
        return compares[0] if len(compares) == 1 else And(tuple(compares), span=self.compilation.span(node))

    def compare_cell(self, column: Formula, operator_node: Any, value_node: Any, scope: Scope) -> Compare:
        """Compiles one atom of a table cell, which compares the column with the value, by equality by default."""
        operator = CompareOp.EQ if operator_node is None else CompareOp(operator_node.getText())
        value = self.formula(value_node, scope.expecting(value_type(column)))
        return Compare(operator, column, value, span=self.compilation.span(value_node))

    def _between(self, start: Any, stop: Any) -> Span:
        return token_span(start, stop, self.compilation.source)


def _respan(formula: Formula, span: Span) -> Formula:
    """Returns an option constant found by name at the position of the name, a definition unchanged."""
    if isinstance(formula, Constant) and isinstance(formula.value, Option):
        return Constant(formula.value, span=span)
    return formula


def _display(structure: Structure) -> str:
    return "the product" if structure.is_root else structure.name
