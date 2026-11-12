"""The model as a whole with lookups by name and the reverse edges of the graph."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from coom.model.behaviors import Behavior
from coom.model.testing import TestCase
from coom.model.traversal import referenced
from coom.model.types import Attribute, Enumeration, Feature, Option, Structure, Type

type Item = Structure | Feature | Enumeration | Attribute | Option


@dataclass(eq=False, slots=True, kw_only=True)
class Model:
    """A compiled COOM model with lookups by name and the reverse edges of the graph."""

    root: Structure
    structures: tuple[Structure, ...] = ()
    """The declared structures, without the root."""
    enumerations: tuple[Enumeration, ...] = ()
    behaviors: tuple[Behavior, ...] = ()
    tests: tuple[TestCase, ...] = ()
    _types: dict[str, Structure | Enumeration] = field(init=False, repr=False)
    _typed: dict[Type, list[Feature]] = field(init=False, repr=False)
    _origins: dict[Structure, list[Behavior]] = field(init=False, repr=False)
    _references: dict[Item, list[Behavior | TestCase]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._types = {}
        self._typed = {}
        self._origins = {}
        self._references = {}
        for structure in (self.root, *self.structures):
            self._types[structure.name] = structure
            for feature in structure.features:
                feature.owner = structure
                self._typed.setdefault(feature.type, []).append(feature)
        for enumeration in self.enumerations:
            self._types[enumeration.name] = enumeration
            for attribute in enumeration.attributes:
                attribute.owner = enumeration
            for option in enumeration.options:
                option.owner = enumeration
        for behavior in self.behaviors:
            self._origins.setdefault(behavior.origin, []).append(behavior)
        for item in (*self.behaviors, *self.tests):
            for target in dict.fromkeys(referenced(item)):
                self._references.setdefault(target, []).append(item)

    def type(self, name: str) -> Structure | Enumeration:
        """Returns the structure or enumeration of the given name."""
        return self._types[name]

    def structure(self, name: str) -> Structure:
        type_ = self._types[name]
        if not isinstance(type_, Structure):
            raise KeyError(f"{name} is not a structure")
        return type_

    def enumeration(self, name: str) -> Enumeration:
        type_ = self._types[name]
        if not isinstance(type_, Enumeration):
            raise KeyError(f"{name} is not an enumeration")
        return type_

    def __getitem__(self, qualified_name: str) -> Item:
        """Returns a type by name or a feature, attribute or option by a name such as "Bike.color"."""
        type_name_, _, member = qualified_name.partition(".")
        type_ = self.type(type_name_)
        if not member:
            return type_
        if isinstance(type_, Structure):
            return type_.feature(member)
        try:
            return type_.option(member)
        except KeyError:
            return type_.attribute(member)

    def features(self) -> Iterator[Feature]:
        """Yields all features of all structures, root first."""
        for structure in (self.root, *self.structures):
            yield from structure.features

    def features_of_type(self, type_: Type) -> tuple[Feature, ...]:
        """Returns the features declared with the given type, for a structure the places it is a part of."""
        return tuple(self._typed.get(type_, ()))

    def behaviors_of(self, structure: Structure) -> tuple[Behavior, ...]:
        """Returns the behaviors whose origin is the given structure."""
        return tuple(self._origins.get(structure, ()))

    def references(self, item: Item) -> tuple[Behavior | TestCase, ...]:
        """Returns the behaviors and tests that refer to a feature, attribute or option."""
        return tuple(self._references.get(item, ()))

    def __iter__(self) -> Iterator[Structure | Enumeration]:
        return iter(self._types.values())

    def __repr__(self) -> str:
        return (
            f"<Model {len(self.structures)} structures, {len(self.enumerations)} enumerations, "
            f"{len(self.behaviors)} behaviors, {len(self.tests)} tests>"
        )
