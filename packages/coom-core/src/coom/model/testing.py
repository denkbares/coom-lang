"""Test blocks, scripted sessions with assertions on a model."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field

from coom.model._base import Span, span_field
from coom.model.formulas import Constant
from coom.model.paths import Path
from coom.model.types import Structure


@dataclass(frozen=True, slots=True)
class SetValue:
    path: Path
    value: Constant | None = None
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
    value: Constant | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsShown:
    path: Path
    value: Constant | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsEmpty:
    path: Path
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsAvailable:
    """Passes if the inputs with the value set at the path, or without value its instances, have a completion."""

    path: Path
    value: Constant | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsBlocked:
    """Passes if the inputs with the value set at the path, or without value its instances, have no completion."""

    path: Path
    value: Constant | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsHidden:
    """Passes if the slot is hidden, or with an option, if this option of the slot is hidden."""

    path: Path
    value: Constant | None = None
    _: KW_ONLY
    span: Span | None = span_field()


@dataclass(frozen=True, slots=True)
class IsReadonly:
    """Passes if the slot is readonly or hidden."""

    path: Path
    _: KW_ONLY
    span: Span | None = span_field()


type TestStep = (
    SetValue | RemoveValue | ResetValue | IsFixed | IsShown | IsEmpty | IsAvailable | IsBlocked | IsHidden | IsReadonly
)


@dataclass(eq=False, slots=True, kw_only=True)
class TestCase:
    """A scripted session whose paths start at the origin structure, the root unless the test names another one."""

    origin: Structure
    steps: tuple[TestStep, ...] = ()
    span: Span | None = field(default=None, repr=False)
