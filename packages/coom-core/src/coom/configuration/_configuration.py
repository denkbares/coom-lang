"""Instances, their slots and the assignments that fill them."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from typing import Any

from coom.configuration.arithmetic import to_decimal, to_grid
from coom.model import (
    Boolean,
    ConstantValue,
    Enumeration,
    Feature,
    Model,
    Numerical,
    Option,
    Structure,
    Textual,
    Type,
    type_name,
)


class Role(StrEnum):
    """Why a configuration holds a value, from the weakest reason to the strongest."""

    COMPLETION = "completion"
    """Chosen by the reasoner only to complete the configuration."""
    DEFAULT = "default"
    """Assigned by a default."""
    CONSEQUENCE = "consequence"
    """The only value left given the selections."""
    SELECTED = "selected"
    """Decided by the user."""


type Value = Instance | ConstantValue


@dataclass(frozen=True, slots=True)
class Assignment:
    """A value held by a slot and the reason it is held."""

    value: Value
    role: Role = Role.SELECTED


@dataclass(eq=False, slots=True)
class Instance:
    """An instance of a structure, with the assignments of its features and its place in the configuration tree."""

    configuration: Configuration
    type: Structure
    name: str
    parent: Instance | None = field(default=None, init=False, repr=False)
    """The instance whose feature holds this one, None for the product and for instances not added yet."""
    feature: Feature | None = field(default=None, init=False, repr=False)
    index: int = field(default=0, init=False, repr=False)
    _slots: dict[Feature, dict[int, Assignment]] = field(default_factory=dict, init=False, repr=False)

    # Reading

    def assignment(self, feature: Feature | str, index: int = 0) -> Assignment | None:
        return self._slots.get(self._feature(feature), {}).get(index)

    def get(self, feature: Feature | str, index: int = 0) -> Value | None:
        assignment = self.assignment(feature, index)
        return None if assignment is None else assignment.value

    def assignments(self, feature: Feature | str) -> Mapping[int, Assignment]:
        """Returns the assignments of the filled slots of a feature, keyed and ordered by slot index."""
        return dict(sorted(self._slots.get(self._feature(feature), {}).items()))

    def values(self, feature: Feature | str) -> tuple[Value, ...]:
        """Returns the values of the filled slots of a feature in slot order."""
        return tuple(assignment.value for assignment in self.assignments(feature).values())

    def last_index(self, feature: Feature | str) -> int:
        """Returns the highest filled slot index of a feature, or -1 if no slot is filled."""
        return max(self._slots.get(self._feature(feature), {}), default=-1)

    def __getitem__(self, name: str) -> Value | tuple[Value, ...] | None:
        """Returns the value of a single valued feature, or the values of a multi valued one."""
        feature = self.type.feature(name)
        return self.values(feature) if feature.is_multiple else self.get(feature)

    # Navigation

    @property
    def root(self) -> Instance:
        instance = self
        while instance.parent is not None:
            instance = instance.parent
        return instance

    @property
    def path(self) -> str:
        """The path from the product to this instance, such as bike.bags[1], empty for the product."""
        steps: list[str] = []
        instance = self
        while instance.parent is not None and instance.feature is not None:
            index = f"[{instance.index}]" if instance.feature.is_multiple else ""
            steps.append(instance.feature.name + index)
            instance = instance.parent
        return ".".join(reversed(steps))

    def children(self) -> Iterator[Instance]:
        """Yields the instances held by the features of this instance."""
        for feature in self.type.features:
            for value in self.values(feature):
                if isinstance(value, Instance):
                    yield value

    def walk(self) -> Iterator[Instance]:
        """Yields this instance and all instances below it, parents before children."""
        yield self
        for child in self.children():
            yield from child.walk()

    # Writing

    def set(
        self,
        feature: Feature | str,
        value: Value | int | float | Fraction,
        index: int = 0,
        *,
        role: Role = Role.SELECTED,
    ) -> Value:
        """Assigns a value to a slot and returns the value as stored, replacing what the slot held before.

        Numbers may be given as int, float, str, Decimal or Fraction and are rounded to the grid of the feature. Options
        may be given by name. An instance must belong to this configuration and must not be part of the tree yet.
        """
        feature = self._feature(feature)
        if index < 0 or (feature.max is not None and index >= feature.max):
            raise IndexError(f"{feature.qualified_name} has no slot {index}")
        stored = _coerce(feature, value)
        if isinstance(stored, Instance):
            self._adopt(stored, feature, index)
        self.remove(feature, index)
        self._slots.setdefault(feature, {})[index] = Assignment(stored, role)
        return stored

    def add(
        self,
        feature: Feature | str,
        value: Value | int | float | Fraction | None = None,
        *,
        role: Role = Role.SELECTED,
    ) -> Value:
        """Assigns a value to the slot after the last filled one, a new instance for a structure feature without one."""
        feature = self._feature(feature)
        if value is None:
            if not isinstance(feature.type, Structure):
                raise ValueError(f"{feature.qualified_name} needs a value")
            value = self.configuration.new(feature.type)
        return self.set(feature, value, self.last_index(feature) + 1, role=role)

    def remove(self, feature: Feature | str, index: int = 0) -> None:
        """Empties a slot, detaching the instance it held."""
        feature = self._feature(feature)
        assignment = self._slots.get(feature, {}).pop(index, None)
        if assignment is not None and isinstance(assignment.value, Instance):
            assignment.value.parent, assignment.value.feature = None, None

    def _adopt(self, child: Instance, feature: Feature, index: int) -> None:
        if child.configuration is not self.configuration:
            raise ValueError(f"{child!r} belongs to another configuration")
        if child.parent is not None or child is self.configuration.root:
            raise ValueError(f"{child!r} is already part of the configuration at {child.path}")
        if any(ancestor is child for ancestor in self._ancestors()):
            raise ValueError(f"{child!r} cannot contain itself")
        child.parent, child.feature, child.index = self, feature, index

    def _ancestors(self) -> Iterator[Instance]:
        instance: Instance | None = self
        while instance is not None:
            yield instance
            instance = instance.parent

    def _feature(self, feature: Feature | str) -> Feature:
        if isinstance(feature, str):
            return self.type.feature(feature)
        if feature.owner is not self.type:
            raise KeyError(f"{self.type.name} has no feature {feature.qualified_name}")
        return feature

    def __repr__(self) -> str:
        where = f" at {self.path}" if self.parent is not None else ""
        return f"<Instance {self.name}{where}>"


def _coerce(feature: Feature, value: object) -> Value:
    """Converts a value to the form stored for the type of the feature, or raises if it does not fit."""
    type_ = feature.type
    match type_:
        case Structure() if isinstance(value, Instance) and value.type is type_:
            return value
        case Enumeration() if isinstance(value, Option) and value.owner is type_:
            return value
        case Enumeration() if isinstance(value, str):
            return type_.option(value)
        case Numerical() if isinstance(value, int | float | str | Decimal | Fraction) and not isinstance(value, bool):
            # a float stands for the decimal it prints as, not for its binary value
            try:
                number = Fraction(repr(value)) if isinstance(value, float) else Fraction(value)
            except ValueError:
                pass
            else:
                return to_decimal(to_grid(number, type_.digits))
        case Textual() if isinstance(value, str):
            return value
        case Boolean() if isinstance(value, bool):
            return value
        case Boolean() if value in ("true", "false"):
            return value == "true"
    raise TypeError(f"{feature.qualified_name} holds {_describe(type_)}, not {value!r}")


def _describe(type_: Type) -> str:
    return f"instances of {type_.name}" if isinstance(type_, Structure) else type_name(type_)


@dataclass(eq=False)
class Configuration:
    """The instances of a model and their assignments, starting from the instance of the product."""

    model: Model
    root: Instance = field(init=False)
    _names: dict[Structure, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.root = Instance(self, self.model.root, "root")

    def new(self, structure: Structure | str, name: str | None = None) -> Instance:
        """Creates an instance of a structure that is not part of the tree until it is assigned to a slot."""
        if isinstance(structure, str):
            structure = self.model.structure(structure)
        if name is None:
            number = self._names.get(structure, 0) + 1
            self._names[structure] = number
            name = f"{structure.name}#{number}"
        return Instance(self, structure, name)

    def instances(self, structure: Structure | str | None = None) -> Iterator[Instance]:
        """Yields the instances of the tree, only those of the given structure if one is given."""
        if isinstance(structure, str):
            structure = self.model.structure(structure)
        return (instance for instance in self.root.walk() if structure is None or instance.type is structure)

    def __getitem__(self, path: str) -> Value | tuple[Value, ...] | None:
        """Returns what a path such as bike.bags[1].size addresses, None if a slot on the way is empty."""
        current: Value | tuple[Value, ...] | None = self.root
        for name, index in _steps(path):
            if not isinstance(current, Instance):
                raise KeyError(f"{path} does not lead through instances")
            current = current[name] if index is None else current.get(name, index)
        return current

    def add_required(self) -> None:
        """Creates the instances that the minimum cardinalities of structure features demand, recursively."""
        pending = [self.root]
        while pending:
            instance = pending.pop()
            for feature in instance.type.features:
                if isinstance(feature.type, Structure):
                    for index in range(feature.min):
                        if instance.assignment(feature, index) is None:
                            instance.set(feature, self.new(feature.type), index)
            pending.extend(instance.children())

    # JSON, implemented in a module of its own that builds on this one

    def to_json(self) -> dict[str, Any]:
        from coom.configuration import _json

        return _json.write(self.root)

    @classmethod
    def from_json(cls, model: Model, data: Mapping[str, Any]) -> Configuration:
        from coom.configuration import _json

        configuration = cls(model)
        _json.read(configuration.root, data)
        return configuration

    def dumps(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_json(), indent=indent)

    @classmethod
    def loads(cls, model: Model, text: str) -> Configuration:
        """Reads the JSON form with exact decimal numbers."""
        return cls.from_json(model, json.loads(text, parse_float=Decimal))


_STEP = re.compile(r"(\w+)(?:\[(\d+)\])?")


def _steps(path: str) -> Iterator[tuple[str, int | None]]:
    for step in path.split(".") if path else ():
        match = _STEP.fullmatch(step)
        if match is None:
            raise KeyError(f"invalid path step {step!r}")
        yield match[1], None if match[2] is None else int(match[2])
