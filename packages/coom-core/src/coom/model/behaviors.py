"""Behaviors, the statements of behavior blocks after preconditions are collected and defines substituted."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from enum import StrEnum

from coom.model._base import Span, span_field
from coom.model.formulas import CompareOp, Condition, Formula
from coom.model.paths import Path
from coom.model.types import Option, Structure


class Direction(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class Directive(StrEnum):
    READONLY = "readonly"
    HIDE = "hide"


class RowKind(StrEnum):
    ALLOW = "allow"
    FORBID = "forbid"


@dataclass(eq=False, slots=True, kw_only=True)
class _BehaviorBase:
    origin: Structure
    """The structure whose instances the behavior applies to, paths in it start there."""
    conditions: tuple[Condition, ...] = ()
    """The preconditions of the statement and of all blocks enclosing it."""
    explanation: str | None = None
    span: Span | None = field(default=None, repr=False)


@dataclass(eq=False, slots=True, kw_only=True)
class Require(_BehaviorBase):
    condition: Condition


@dataclass(eq=False, slots=True, kw_only=True)
class Imply(_BehaviorBase):
    target: Path
    value: Formula


@dataclass(eq=False, slots=True, kw_only=True)
class Default(_BehaviorBase):
    target: Path
    value: Formula
    priority: int | None = None
    """The explicitly written priority, None if the source gave none."""


@dataclass(eq=False, slots=True, kw_only=True)
class Optimize(_BehaviorBase):
    direction: Direction
    target: Path


@dataclass(eq=False, slots=True, kw_only=True)
class Visibility(_BehaviorBase):
    """Hides or locks the target feature or, if options are given, only these options of it."""

    directive: Directive
    target: Path
    options: tuple[Option, ...] = ()


@dataclass(frozen=True, slots=True)
class CellAtom:
    """Holds if the column value compares to `value` by `op`."""

    value: Formula
    op: CompareOp = CompareOp.EQ
    _: KW_ONLY
    span: Span | None = span_field()


type Cell = tuple[CellAtom, ...]
"""A table cell that holds if any of its atoms holds."""


@dataclass(frozen=True, slots=True)
class Row:
    """A row of a combinations table, None marking a cell that matches anything."""

    kind: RowKind
    cells: tuple[Cell | None, ...]
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(eq=False, slots=True, kw_only=True)
class Combinations(_BehaviorBase):
    columns: tuple[Formula, ...]
    rows: tuple[Row, ...] = ()


type Behavior = Require | Imply | Default | Optimize | Visibility | Combinations
