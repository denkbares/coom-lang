"""The show command, which selects entities of the model and renders them."""

import argparse
import difflib
import json
from collections.abc import Iterator, Sequence
from decimal import Decimal

from coom.cli._arguments import MODEL, CommandParser, add_format, add_selectors, add_workspace, runs
from coom.cli._exit import CommandError, ExitCode
from coom.cli._render import location, print_json
from coom.cli._workspace import Workspace
from coom.model import (
    Attribute,
    ConstantValue,
    Entity,
    Enumeration,
    Feature,
    Model,
    Option,
    Structure,
    TestCase,
    type_name,
)
from coom.model.json import write_entity
from coom.model.selection import EntityKind, SelectionError, entity_name, kind, select
from coom.writer import write, write_items

TREE, DETAIL, LIST = "tree", "detail", "list"
DEFAULT_LIMIT = 100
INDENT = "  "


def register(coom: CommandParser) -> None:
    show = coom.add_command(
        "show",
        "Select entities of the model and render them",
        [
            "coom show",
            "coom show KidsBike.color",
            "coom show 'KidsBike.*' --view list",
            "coom show @KidsBike.test:3",
            "coom show --kind enumeration,option",
            "coom show --format json",
        ],
        group=MODEL,
    )
    add_selectors(show)
    show.add_argument(
        "--view",
        choices=(TREE, DETAIL, LIST),
        help="the view (default: tree without selector, detail for one match, list for several)",
    )
    show.add_argument(
        "--kind", metavar="KIND", help=f"only entities of these comma separated kinds: {', '.join(EntityKind)}"
    )
    show.add_argument("--depth", metavar="N", type=int, help="the depth of the tree view (default: unlimited)")
    show.add_argument(
        "--limit",
        metavar="N",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"the maximum number of entities in the list and detail views, 0 for all (default: {DEFAULT_LIMIT})",
    )
    add_workspace(show)
    add_format(show, "text", "json", "coom")
    runs(show, run)


def run(options: argparse.Namespace) -> int:
    if options.dependencies is not None or options.dependents is not None:
        raise CommandError("--dependencies and --dependents are not implemented yet")
    kinds = _kinds(options.kind)
    model = Workspace.open(options).model()
    # None stands for the whole model, which the tree view starts at the product
    entities: tuple[Entity, ...] | None = None
    if options.selectors:
        try:
            entities = select(model, options.selectors)
        except SelectionError as error:
            raise CommandError(str(error)) from None
    elif kinds:
        entities = tuple(model.entities())
    if entities is not None and kinds:
        entities = tuple(entity for entity in entities if kind(entity) in kinds)
    if entities is not None and not entities:
        if options.format == "json":
            print_json("show")
        else:
            print(_nothing(options.selectors, kinds))
        return ExitCode.NEGATIVE
    if options.format == "json":
        print_json("show", [write_entity(entity) for entity in (_top_level(model) if entities is None else entities)])
    elif options.format == "coom":
        print(write(model) if entities is None else write_items(model, entities), end="")
    else:
        view = options.view or (TREE if entities is None else DETAIL if len(entities) == 1 else LIST)
        for line in _render(view, model, entities, options):
            print(line)
    return ExitCode.SUCCESS


def _kinds(text: str | None) -> frozenset[EntityKind]:
    kinds = set()
    for name in (part.strip() for part in (text or "").split(",")):
        if not name:
            continue
        if name not in set(EntityKind):
            message = f"unknown kind {name}, the kinds are {', '.join(EntityKind)}"
            nearest = difflib.get_close_matches(name, list(EntityKind))
            raise CommandError(message + (f", did you mean {' or '.join(nearest)}?" if nearest else ""))
        kinds.add(EntityKind(name))
    return frozenset(kinds)


def _nothing(selectors: Sequence[str], kinds: frozenset[EntityKind]) -> str:
    of_kinds = f" of kind {', '.join(k for k in EntityKind if k in kinds)}" if kinds else ""
    if not selectors:
        return f"the model has nothing{of_kinds}"
    return f"nothing{of_kinds} matches {' '.join(selectors)}"


def _top_level(model: Model) -> tuple[Entity, ...]:
    """Returns the entities that together contain the whole model."""
    return (model.root, *model.structures, *model.enumerations, *model.behaviors, *model.tests)


def _render(view: str, model: Model, entities: Sequence[Entity] | None, options: argparse.Namespace) -> Iterator[str]:
    if view == TREE:
        for entity in (model.root,) if entities is None else entities:
            yield from _tree(entity, options.depth)
        return
    if entities is None:
        entities = tuple(model.entities())
    shown = entities if options.limit <= 0 else entities[: options.limit]
    if view == LIST:
        yield from _table([(str(kind(entity)), entity_name(entity), location(entity.span)) for entity in shown])
    else:
        for position, entity in enumerate(shown):
            if position:
                yield ""
            yield from _detail(model, entity)
    if len(shown) < len(entities):
        yield f"showing {len(shown)} of {len(entities)} entities, use --limit N for more or --limit 0 for all"


def _tree(entity: Entity, depth: int | None) -> Iterator[str]:
    """Yields a structure with its features and their parts, a feature with its parts, other entities as one line."""
    match entity:
        case Structure():
            yield entity.name
            yield from _features(entity, 1, depth)
        case Feature():
            yield _feature_line(entity, 0)
            if isinstance(entity.type, Structure):
                yield from _features(entity.type, 1, depth)
        case _:
            yield f"{entity_name(entity)}  {kind(entity)}"


def _features(structure: Structure, level: int, depth: int | None) -> Iterator[str]:
    # the static checks reject cycles of structures, so the recursion ends
    if depth is not None and level > depth:
        return
    for feature in structure.features:
        yield _feature_line(feature, level)
        if isinstance(feature.type, Structure):
            yield from _features(feature.type, level + 1, depth)


def _feature_line(feature: Feature, level: int) -> str:
    return f"{INDENT * level}{feature.qualified_name}  {_feature_type(feature)}"


def _feature_type(feature: Feature) -> str:
    """Returns the type of a feature with its cardinality in front unless it is exactly one."""
    if (feature.min, feature.max) == (1, 1):
        return type_name(feature.type)
    return f"{feature.min}..{'*' if feature.max is None else feature.max} {type_name(feature.type)}"


def _detail(model: Model, entity: Entity) -> Iterator[str]:
    """Yields the name, the fields and the declaration of an entity."""
    fields: list[tuple[str, str]] = [("kind", str(kind(entity)))]
    match entity:
        case Structure() | Enumeration():
            used_by = ", ".join(feature.qualified_name for feature in model.features_of_type(entity))
            fields.append(("used by", used_by or "-"))
        case Feature():
            fields.append(("type", _feature_type(entity)))
            if isinstance(entity.type, Enumeration):
                fields.append(("options", ", ".join(option.qualified_name for option in entity.type.options)))
        case Attribute():
            fields.append(("type", type_name(entity.type)))
        case Option():
            if entity.values:
                values = [f"{attribute.name} = {_value(value)}" for attribute, value in entity.values.items()]
                fields.append(("values", ", ".join(values)))
        case TestCase():
            fields.append(("origin", entity.origin.name))
        case _:
            fields.append(("origin", entity.origin.name))
    fields.append(("location", location(entity.span)))
    yield entity_name(entity)
    yield from (INDENT + line for line in _table(fields))
    yield from (f"{INDENT * 2}{line}".rstrip() for line in write_items(model, (entity,)).splitlines())


def _value(value: ConstantValue) -> str:
    match value:
        case Option():
            return value.name
        case bool():
            return "true" if value else "false"
        case Decimal():
            return format(value, "f")
        case _:
            return json.dumps(value, ensure_ascii=False)


def _table(rows: Sequence[Sequence[str]]) -> list[str]:
    """Aligns all columns but the last one."""
    if not rows:
        return []
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]) - 1)]
    return [
        "  ".join([*(cell.ljust(width) for cell, width in zip(row, widths, strict=False)), row[-1]]) for row in rows
    ]
