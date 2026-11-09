"""Test blocks, scripted sessions with assertions on a model."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field

from coom.model._base import Span, span_field
from coom.model.formulas import Formula
from coom.model.paths import Path


@dataclass(frozen=True, slots=True)
class SetValue:
    path: Path
    value: Formula | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class RemoveValue:
    path: Path
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class ResetValue:
    path: Path
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsFixed:
    path: Path
    value: Formula | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsShown:
    path: Path
    value: Formula | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsEmpty:
    path: Path
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsAvailable:
    path: Path
    value: Formula
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsBlocked:
    path: Path
    value: Formula
    _: KW_ONLY
    span: Span | None = span_field()


type TestStep = SetValue | RemoveValue | ResetValue | IsFixed | IsShown | IsEmpty | IsAvailable | IsBlocked


@dataclass(eq=False, slots=True, kw_only=True)
class TestCase:
    """A scripted session on the root structure."""

    name: str | None = None
    steps: tuple[TestStep, ...] = ()
    span: Span | None = field(default=None, repr=False)
