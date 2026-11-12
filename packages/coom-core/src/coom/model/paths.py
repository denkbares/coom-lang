"""Paths from a structure through features and attributes to the values they address."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass

from coom.model._base import Span, span_field
from coom.model.types import Attribute, Feature, Structure, Type


@dataclass(frozen=True, slots=True)
class Index:
    """An inclusive range of instance indices where negative indices count from the end, -1 being the last."""

    first: int
    last: int

    @property
    def is_single(self) -> bool:
        return self.first == self.last

    def __str__(self) -> str:
        first, last = _index(self.first), _index(self.last)
        return first if self.is_single else f"{first}..{last}"


def _index(index: int) -> str:
    if index >= 0:
        return str(index)
    return "last" if index == -1 else f"last-{-index - 1}"


@dataclass(frozen=True, slots=True)
class FeatureStep:
    """A path step into a feature, restricted to `index` or covering all instances if it is None."""

    feature: Feature
    index: Index | None = None
    _: KW_ONLY
    span: Span | None = span_field()

    @property
    def is_range(self) -> bool:
        if self.index is None:
            return self.feature.is_multiple
        return not self.index.is_single

    @property
    def type(self) -> Type:
        return self.feature.type

    def __str__(self) -> str:
        return self.feature.name if self.index is None else f"{self.feature.name}[{self.index}]"


@dataclass(frozen=True, slots=True)
class AttributeStep:
    """A path step from an option to the value of one of its attributes."""

    attribute: Attribute
    _: KW_ONLY
    span: Span | None = span_field()

    @property
    def is_range(self) -> bool:
        return False

    @property
    def type(self) -> Type:
        return self.attribute.type

    def __str__(self) -> str:
        return self.attribute.name


type Step = FeatureStep | AttributeStep


@dataclass(frozen=True, slots=True)
class Path:
    """A sequence of steps from an origin structure to the values it addresses, the empty path addressing the origin."""

    origin: Structure
    steps: tuple[Step, ...] = ()
    _: KW_ONLY
    rooted: bool = False
    """Whether the source spelled the path from root, which only matters for writing it back."""
    span: Span | None = span_field()

    @property
    def type(self) -> Type:
        return self.steps[-1].type if self.steps else self.origin

    @property
    def is_range(self) -> bool:
        """Whether the path may address more than one value."""
        return any(step.is_range for step in self.steps)

    def __str__(self) -> str:
        parts = [str(step) for step in self.steps]
        if self.rooted:
            parts.insert(0, "root")
        return ".".join(parts) if parts else "this"
