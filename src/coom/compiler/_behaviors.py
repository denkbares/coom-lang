"""The phase that compiles behavior blocks into flat behaviors.

Definitions are substituted, preconditions of enclosing blocks are collected into each statement, and derivation
tables are lowered to one require or default per row and column.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, TypedDict

from coom.compiler._context import Abort, Compilation, children, name, need, unquote
from coom.compiler._expressions import Expressions, Scope, value_type
from coom.model import (
    AttributeStep,
    Cell,
    CellAtom,
    Combinations,
    CompareOp,
    Condition,
    Default,
    Direction,
    Directive,
    Enumeration,
    Formula,
    Imply,
    Optimize,
    Or,
    PathAccess,
    Require,
    Row,
    RowKind,
    Span,
    Structure,
    Visibility,
)
from coom.parser._antlr.COOMParser import COOMParser


def compile_behaviors(compilation: Compilation, tree: Any) -> None:
    for node in children(tree):
        if isinstance(node, COOMParser.BehaviorContext):
            try:
                origin = resolve_origin(compilation, node.name())
                block = need(node.behavior_block())
            except Abort:
                continue
            _Block(compilation, Expressions(compilation, origin)).block(block, Scope.of(compilation, origin), _Frame())


def resolve_origin(compilation: Compilation, node: Any) -> Structure:
    """Returns the structure a behavior or test block names, the product if it names none."""
    if node is None:
        return compilation.root
    type_name = name(node)
    type_ = compilation.types.get(type_name)
    if type_ is None:
        compilation.fail(node, f"the structure {type_name} is not defined")
    if not isinstance(type_, Structure):
        compilation.fail(node, f"{type_name} is an enumeration, not a structure")
    return type_


@dataclass(frozen=True, slots=True)
class _Frame:
    """What a statement inherits from its enclosing blocks."""

    conditions: tuple[Condition, ...] = ()
    explanation: str | None = None


class _Common(TypedDict):
    origin: Structure
    conditions: tuple[Condition, ...]
    explanation: str | None
    span: Span


class _Block:
    def __init__(self, compilation: Compilation, expressions: Expressions) -> None:
        self.compilation = compilation
        self.expressions = expressions
        self.origin = expressions.origin

    def block(self, node: Any, scope: Scope, frame: _Frame) -> None:
        for definition in node.define():
            try:
                formula = self.expressions.formula(definition.formula(), scope)
                scope = scope.define(name(definition.name()), formula)
            except Abort:
                pass
        for statement in node.conditioned():
            with contextlib.suppress(Abort):
                self.conditioned(statement, scope, frame)

    def conditioned(self, node: Any, scope: Scope, frame: _Frame) -> None:
        explanation = frame.explanation
        if node.explanation() is not None:
            explanation = unquote(need(node.explanation().name()).getText())
        preconditions = tuple(self.expressions.condition(p.condition(), scope) for p in node.precondition())
        frame = _Frame((*frame.conditions, *preconditions), explanation)
        if node.behavior_block() is not None:
            self.block(node.behavior_block(), scope, frame)
        elif node.require() is not None:
            self._require(node.require(), scope, frame)
        elif node.assign_imply() is not None:
            self._imply(node.assign_imply(), scope, frame)
        elif node.assign_default() is not None:
            self._default(node.assign_default(), scope, frame)
        elif node.optimize() is not None:
            self._optimize(node.optimize(), scope, frame)
        elif node.visibility() is not None:
            self._visibility(node.visibility(), scope, frame)
        elif node.combinations() is not None:
            self._combinations(node.combinations(), scope, frame)
        elif node.derivation_table() is not None:
            self._derivation_table(node.derivation_table(), scope, frame)

    def _common(self, node: Any, frame: _Frame) -> _Common:
        return _Common(
            origin=self.origin,
            conditions=frame.conditions,
            explanation=frame.explanation,
            span=self.compilation.span(node),
        )

    def _require(self, node: Any, scope: Scope, frame: _Frame) -> None:
        condition = self.expressions.condition(node.condition(), scope)
        self.compilation.behaviors.append(Require(condition=condition, **self._common(node, frame)))

    def _imply(self, node: Any, scope: Scope, frame: _Frame) -> None:
        target = self.expressions.assignable(node.path(), scope)
        value = self.expressions.formula(node.formula(), scope.expecting(target.type))
        self.compilation.behaviors.append(Imply(target=target, value=value, **self._common(node, frame)))

    def _default(self, node: Any, scope: Scope, frame: _Frame) -> None:
        priority = None
        if node.priority is not None:
            priority = int(node.priority.text)
            if priority < 1:
                self.compilation.fail(node.priority, "the priority must be at least 1")
        target = self.expressions.assignable(node.path(), scope)
        value = self.expressions.formula(node.formula(), scope.expecting(target.type))
        self.compilation.behaviors.append(
            Default(target=target, value=value, priority=priority, **self._common(node, frame))
        )

    def _optimize(self, node: Any, scope: Scope, frame: _Frame) -> None:
        target = self.expressions.assignable(node.path(), scope)
        direction = Direction(need(node.kw).text)
        self.compilation.behaviors.append(Optimize(direction=direction, target=target, **self._common(node, frame)))

    def _visibility(self, node: Any, scope: Scope, frame: _Frame) -> None:
        directive = Directive(need(node.directive).text)
        target = self.expressions.assignable(node.path(), scope)
        options = []
        if node.name():
            enumeration = target.type
            if not isinstance(enumeration, Enumeration):
                self.compilation.fail(node.path(), "only options of an enumeration can be hidden individually")
            if directive is not Directive.HIDE:
                self.compilation.fail(node.directive, "options can only be hidden, not made read only")
            for option_node in node.name():
                try:
                    option = enumeration.option(name(option_node))
                except KeyError:
                    self.compilation.fail(
                        option_node, f"{option_node.getText()} is not an option of {enumeration.name}"
                    )
                if option not in options:
                    options.append(option)
            if len(options) == len(enumeration.options):
                self.compilation.fail(node, f"cannot hide all options of {enumeration.name}")
        self.compilation.behaviors.append(
            Visibility(directive=directive, target=target, options=tuple(options), **self._common(node, frame))
        )

    def _combinations(self, node: Any, scope: Scope, frame: _Frame) -> None:
        if not node.combination_row():
            self.compilation.fail(node.kw, "a combinations table needs at least one row")
        columns = tuple(self.expressions.formula(column, scope) for column in node.formula())
        rows = []
        for row_node in node.combination_row():
            items = row_node.combination_item()
            if len(items) != len(columns):
                self.compilation.error(row_node, f"the row has {len(items)} cells for {len(columns)} columns")
                continue
            try:
                cells = tuple(self._cell(column, item, scope) for column, item in zip(columns, items, strict=True))
            except Abort:
                continue
            kind = RowKind(need(row_node.rowType).text)
            rows.append(Row(kind, cells, span=self.compilation.span(row_node)))
        self.compilation.behaviors.append(Combinations(columns=columns, rows=tuple(rows), **self._common(node, frame)))

    def _cell(self, column: Any, node: Any, scope: Scope) -> Cell | None:
        if node.any_ is not None:
            return None
        cell_scope = scope.expecting(value_type(column))
        atoms = []
        for atom in node.combination_atom():
            value = self.expressions.formula(atom.formula(), cell_scope)
            operator = CompareOp.EQ if atom.operator is None else CompareOp(atom.operator.getText())
            atoms.append(CellAtom(value, operator, span=self.compilation.span(atom)))
        return tuple(atoms)

    def _derivation_table(self, node: Any, scope: Scope, frame: _Frame) -> None:
        kind = need(node.kw).text
        targets = tuple(self.expressions.formula(f, scope) for f in need(node.assignment_columns).formula())
        columns: tuple[Formula, ...] = ()
        if node.condition_columns is not None:
            columns = tuple(self.expressions.formula(f, scope) for f in node.condition_columns.formula())
        if kind == "default":
            for target, target_node in zip(targets, node.assignment_columns.formula(), strict=True):
                path = target.path if isinstance(target, PathAccess) else None
                if path is None or not path.steps or isinstance(path.steps[-1], AttributeStep):
                    self.compilation.fail(target_node, "a column of a default table must be a path to a feature")
        for row in node.derivation_table_row():
            with contextlib.suppress(Abort):
                self._derivation_row(kind, targets, columns, row, scope, frame)

    def _derivation_row(
        self, kind: str, targets: tuple[Any, ...], columns: tuple[Any, ...], node: Any, scope: Scope, frame: _Frame
    ) -> None:
        cells = node.derivation_condition_cell()
        values = node.derivation_table_atom()
        if len(cells) != len(columns):
            self.compilation.fail(node, f"the row has {len(cells)} condition cells for {len(columns)} columns")
        if len(values) != len(targets):
            self.compilation.fail(node, f"the row has {len(values)} values for {len(targets)} columns")
        # A row reads as a set of statements that share the conditions of its cells, a cell holding if any atom holds.
        conditions = list(frame.conditions)
        for column, cell in zip(columns, cells, strict=True):
            if cell.any_ is not None or not cell.derivation_table_atom():
                continue
            atoms = tuple(
                self.expressions.compare_cell(column, atom.operator, atom.formula(), scope)
                for atom in cell.derivation_table_atom()
            )
            conditions.append(atoms[0] if len(atoms) == 1 else Or(atoms, span=self.compilation.span(cell)))
        common = self._common(node, _Frame(tuple(conditions), frame.explanation))
        for target, value_node in zip(targets, values, strict=True):
            compare = self.expressions.compare_cell(target, value_node.operator, value_node.formula(), scope)
            if kind == "require":
                self.compilation.behaviors.append(Require(condition=compare, **common))
            elif compare.op is not CompareOp.EQ:
                self.compilation.fail(value_node, "a default table only assigns values with =")
            else:
                assert isinstance(target, PathAccess)
                self.compilation.behaviors.append(Default(target=target.path, value=compare.right, **common))
