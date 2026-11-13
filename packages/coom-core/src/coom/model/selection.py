"""Selectors, the textual names by which tools address the entities of a model.

Items are selected by their qualified name such as "Bike.color", behaviors and tests by their location such as
"@Bike.model:12". A selector with the glob characters "*", "?" or "[" selects every entity whose name matches. The
name an entity is printed with is always a selector for it.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Sequence
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import PurePath
from typing import assert_never

from coom.model.behaviors import Combinations, Default, Imply, Optimize, Require, Visibility
from coom.model.graph import Entity, Model
from coom.model.testing import TestCase
from coom.model.types import Attribute, Enumeration, Feature, Option, Structure

LOCATION = "@"
"""The prefix of a selector that addresses behaviors and tests by their source and line."""

_GLOB = frozenset("*?[")


class EntityKind(StrEnum):
    STRUCTURE = "structure"
    FEATURE = "feature"
    ENUMERATION = "enumeration"
    ATTRIBUTE = "attribute"
    OPTION = "option"
    BEHAVIOR = "behavior"
    TEST = "test"


class SelectionError(Exception):
    """A selector that names nothing in the model, with the nearest names it may have meant."""

    def __init__(self, message: str, nearest: Sequence[str] = ()) -> None:
        if nearest:
            message += f", did you mean {' or '.join(nearest)}?"
        super().__init__(message)
        self.nearest = tuple(nearest)


def kind(entity: Entity) -> EntityKind:
    match entity:
        case Structure():
            return EntityKind.STRUCTURE
        case Feature():
            return EntityKind.FEATURE
        case Enumeration():
            return EntityKind.ENUMERATION
        case Attribute():
            return EntityKind.ATTRIBUTE
        case Option():
            return EntityKind.OPTION
        case Require() | Imply() | Default() | Optimize() | Visibility() | Combinations():
            return EntityKind.BEHAVIOR
        case TestCase():
            return EntityKind.TEST
        case _:
            assert_never(entity)


def entity_name(entity: Entity) -> str:
    """Returns the name an entity is printed with, the qualified name of an item or the location of a statement."""
    match entity:
        case Structure() | Enumeration():
            return entity.name
        case Feature() | Attribute() | Option():
            return entity.qualified_name
        case _:
            span = entity.span
            if span is None:
                return f"{LOCATION}?"
            source = "?" if span.source is None else PurePath(span.source).name
            return f"{LOCATION}{source}:{span.line}"


def select(model: Model, selectors: Iterable[str]) -> tuple[Entity, ...]:
    """Returns the entities the selectors name, each once and in declaration order.

    Raises SelectionError for a selector without glob characters that names nothing. A glob that matches nothing
    selects nothing.
    """
    names: dict[str, list[Entity]] = {}
    for entity in model.entities():
        names.setdefault(entity_name(entity), []).append(entity)
    selected: dict[Entity, None] = {}
    for selector in selectors:
        selected.update(dict.fromkeys(_resolve(model, names, selector)))
    order = {entity: position for position, entity in enumerate(model.entities())}
    return tuple(sorted(selected, key=order.__getitem__))


def _resolve(model: Model, names: dict[str, list[Entity]], selector: str) -> list[Entity]:
    if selector in names:
        return names[selector]
    if not _GLOB.isdisjoint(selector):
        return [entity for name, entities in names.items() if fnmatchcase(name, selector) for entity in entities]
    if selector.startswith(LOCATION):
        return _locate(model, selector)
    nearest = difflib.get_close_matches(selector, [name for name in names if not name.startswith(LOCATION)])
    raise SelectionError(f"unknown item {selector}", nearest)


def _locate(model: Model, selector: str) -> list[Entity]:
    """Resolves "@FILE" to the behaviors and tests of a source and "@FILE:LINE" to those whose span covers the line."""
    file, separator, line_text = selector.removeprefix(LOCATION).rpartition(":")
    if not separator or not line_text.isdigit():
        file, line_text = selector.removeprefix(LOCATION), ""
    statements: list[Entity] = [*model.behaviors, *model.tests]
    sources = {entity.span.source for entity in statements if entity.span is not None and entity.span.source}
    in_file = [
        entity
        for entity in statements
        if entity.span is not None and entity.span.source is not None and _same_file(entity.span.source, file)
    ]
    if not in_file:
        files = sorted({PurePath(source).name for source in sources})
        raise SelectionError(f"no behavior or test in {file}", difflib.get_close_matches(file, files))
    if not line_text:
        return in_file
    line = int(line_text)
    found = [
        entity for entity in in_file if entity.span is not None and entity.span.line <= line <= entity.span.end_line
    ]
    if found:
        return found
    by_distance = sorted(in_file, key=lambda entity: abs(entity.span.line - line) if entity.span else 0)
    raise SelectionError(
        f"no behavior or test at {file}:{line}", list(dict.fromkeys(map(entity_name, by_distance)))[:3]
    )


def _same_file(source: str, file: str) -> bool:
    """Whether the file names the source, as the same path or as its last path components."""
    source_parts, file_parts = PurePath(source).parts, PurePath(file).parts
    return bool(file_parts) and source_parts[-len(file_parts) :] == file_parts
