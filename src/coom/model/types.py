"""Structures, enumerations and the numeric and text types, the nodes the rest of the model refers to."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import assert_never

from coom.model._base import Span, span_field

ROOT_NAME = ":root"
"""Name of the structure that the product block declares."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Numerical:
    """A numeric type with a decimal grid of `digits` fraction digits, an optional unit and optional bounds."""

    digits: int = 0
    unit: str | None = None
    min: Decimal | None = None
    max: Decimal | None = None
    span: Span | None = span_field()

    @property
    def step(self) -> Decimal:
        """The distance between two neighboring grid values."""
        return Decimal(1).scaleb(-self.digits)


@dataclass(frozen=True, slots=True, kw_only=True)
class Textual:
    """The type of text values."""

    span: Span | None = span_field()


@dataclass(eq=False, slots=True, kw_only=True)
class Structure:
    """A named composite type whose values are instances with features."""

    name: str
    features: tuple[Feature, ...] = ()
    span: Span | None = None

    @property
    def is_root(self) -> bool:
        return self.name == ROOT_NAME

    def feature(self, name: str) -> Feature:
        for feature in self.features:
            if feature.name == name:
                return feature
        raise KeyError(f"{self.name} has no feature {name}")

    def __repr__(self) -> str:
        return f"<Structure {self.name}>"


@dataclass(eq=False, slots=True, kw_only=True)
class Feature:
    """A slot of a structure that holds between `min` and `max` values of its type, `max` None meaning unbounded."""

    name: str
    type: Type
    min: int = 1
    max: int | None = 1
    span: Span | None = None
    owner: Structure = field(init=False, repr=False)

    @property
    def qualified_name(self) -> str:
        return f"{self.owner.name}.{self.name}"

    @property
    def is_optional(self) -> bool:
        return self.min == 0

    @property
    def is_multiple(self) -> bool:
        return self.max is None or self.max > 1

    def __repr__(self) -> str:
        owner = self.owner.name if hasattr(self, "owner") else "?"
        cardinality = "" if (self.min, self.max) == (1, 1) else f"{_cardinality(self.min, self.max)} "
        return f"<Feature {owner}.{self.name}: {cardinality}{type_name(self.type)}>"


@dataclass(eq=False, slots=True, kw_only=True)
class Enumeration:
    """A named type with a fixed, ordered set of options that may carry attribute values."""

    name: str
    attributes: tuple[Attribute, ...] = ()
    options: tuple[Option, ...] = ()
    span: Span | None = None

    def option(self, name: str) -> Option:
        for option in self.options:
            if option.name == name:
                return option
        raise KeyError(f"{self.name} has no option {name}")

    def attribute(self, name: str) -> Attribute:
        for attribute in self.attributes:
            if attribute.name == name:
                return attribute
        raise KeyError(f"{self.name} has no attribute {name}")

    def __repr__(self) -> str:
        return f"<Enumeration {self.name}>"


@dataclass(eq=False, slots=True, kw_only=True)
class Attribute:
    """A property that every option of an enumeration defines a value for."""

    name: str
    type: Type
    span: Span | None = None
    owner: Enumeration = field(init=False, repr=False)

    @property
    def qualified_name(self) -> str:
        return f"{self.owner.name}.{self.name}"

    def __repr__(self) -> str:
        owner = self.owner.name if hasattr(self, "owner") else "?"
        return f"<Attribute {owner}.{self.name}: {type_name(self.type)}>"


@dataclass(eq=False, slots=True, kw_only=True)
class Option:
    """A value of an enumeration."""

    name: str
    values: Mapping[Attribute, ConstantValue] = field(default_factory=lambda: MappingProxyType({}))
    span: Span | None = None
    owner: Enumeration = field(init=False, repr=False)

    @property
    def qualified_name(self) -> str:
        return f"{self.owner.name}.{self.name}"

    @property
    def index(self) -> int:
        """The position of this option in its enumeration, which defines the order of options."""
        return self.owner.options.index(self)

    def value(self, attribute: Attribute | str) -> ConstantValue:
        if isinstance(attribute, str):
            attribute = self.owner.attribute(attribute)
        return self.values[attribute]

    def __repr__(self) -> str:
        owner = self.owner.name if hasattr(self, "owner") else "?"
        return f"<Option {owner}.{self.name}>"


type Type = Structure | Enumeration | Numerical | Textual
type ConstantValue = Decimal | bool | str | Option


def type_name(type_: Type) -> str:
    """Returns the type as it is written in a feature declaration."""
    match type_:
        case Structure() | Enumeration():
            return type_.name
        case Numerical():
            text = "num"
            if type_.digits:
                text += "." + "#" * type_.digits
            if type_.unit is not None:
                text += f" /{type_.unit}"
            if type_.min is not None or type_.max is not None:
                text += f" {_bound(type_.min)}-{_bound(type_.max)}"
            return text
        case Textual():
            return "string"
        case _:
            assert_never(type_)


def _bound(value: Decimal | None) -> str:
    return "*" if value is None else str(value)


def _cardinality(low: int, high: int | None) -> str:
    return f"{low}..{'*' if high is None else high}"


def options(*names: str) -> tuple[Option, ...]:
    """Creates options without attribute values, which is the common case when building models by hand."""
    return tuple(Option(name=name) for name in names)
