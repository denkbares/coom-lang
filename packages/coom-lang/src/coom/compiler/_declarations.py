"""The phases that build the types, from their names over their features and options to the attribute values."""

import contextlib
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from coom.compiler._context import Abort, Compilation, children, name, need, unquote
from coom.diagnostics import DiagnosticCode
from coom.model import (
    BOOLEAN_NAME,
    Attribute,
    Boolean,
    ConstantValue,
    Enumeration,
    Feature,
    Numerical,
    Option,
    Structure,
    Textual,
    Type,
)
from coom.parser._antlr.COOMParser import COOMParser

STAR_DIGITS = 8
"""The number of fraction digits that the grid ".*" declares."""


def declare_types(compilation: Compilation, tree: Any) -> None:
    """Creates every structure and enumeration without content, so that declarations may refer to later ones."""
    for node in children(tree):
        try:
            match node:
                case COOMParser.ProductContext():
                    if compilation.product is not None:
                        compilation.fail(node.kw, DiagnosticCode.NAME, "the product is already defined")
                    compilation.product = node
                    compilation.declared[node] = compilation.root
                    compilation.root.span = compilation.span(node)
                case COOMParser.StructureContext():
                    structure = Structure(name=_type_name(compilation, node), span=compilation.span(node))
                    compilation.structures.append(structure)
                    compilation.types[structure.name] = compilation.declared[node] = structure
                case COOMParser.EnumerationContext():
                    enumeration = Enumeration(name=_type_name(compilation, node), span=compilation.span(node))
                    compilation.enumerations.append(enumeration)
                    compilation.types[enumeration.name] = compilation.declared[node] = enumeration
        except Abort:
            pass


def _type_name(compilation: Compilation, node: Any) -> str:
    type_name = name(node.name())
    if type_name == BOOLEAN_NAME:
        compilation.fail(node.name(), DiagnosticCode.NAME, f"{BOOLEAN_NAME} is a predefined type")
    if type_name in compilation.types:
        compilation.fail(node.name(), DiagnosticCode.NAME, f"the type {type_name} is already defined")
    return type_name


def declare_fields(compilation: Compilation, tree: Any) -> None:
    """Adds the features to structures and the attributes and options to enumerations."""
    for node in children(tree):
        match compilation.declared.get(node):
            case Structure() as structure:
                features: list[Feature] = []
                for feature_node in node.feature():
                    try:
                        feature = _feature(compilation, feature_node)
                    except Abort:
                        continue
                    if any(other.name == feature.name for other in features):
                        compilation.error(
                            feature_node.field().fieldName,
                            DiagnosticCode.NAME,
                            f"the feature {feature.name} is already defined",
                        )
                        continue
                    feature.owner = structure
                    features.append(feature)
                structure.features = tuple(features)
            case Enumeration() as enumeration:
                _members(compilation, enumeration, node)


def _feature(compilation: Compilation, node: Any) -> Feature:
    field = need(node.field())
    low, high = _cardinality(compilation, node.cardinality())
    return Feature(
        name=name(field.fieldName),
        type=_field_type(compilation, field),
        min=low,
        max=high,
        span=compilation.span(node),
    )


def _cardinality(compilation: Compilation, node: Any) -> tuple[int, int | None]:
    if node is None:
        return 1, 1
    low = int(need(node.min_).text)
    if node.range_ is None:
        return low, low
    if node.max_ is None or node.max_.text == "*":
        return low, None
    high = int(node.max_.text)
    if high < low:
        compilation.fail(node, DiagnosticCode.STRUCTURE, f"the maximum {high} is smaller than the minimum {low}")
    return low, high


def _field_type(compilation: Compilation, field: Any) -> Type:
    if (number := field.number_def()) is not None:
        return _numerical(compilation, number)
    if field.string_def() is not None:
        return Textual(span=compilation.span(field.string_def()))
    reference = field.type_ref if field.type_ref is not None else field.fieldName
    type_name = name(reference)
    if type_name == BOOLEAN_NAME:
        return Boolean(span=compilation.span(reference))
    type_ = compilation.types.get(type_name)
    if type_ is None:
        compilation.fail(reference, DiagnosticCode.NAME, f"the type {type_name} is not defined")
    return type_


def _numerical(compilation: Compilation, node: Any) -> Numerical:
    digits = 0
    if (fraction := node.fraction()) is not None:
        grid = need(fraction.digits).text
        digits = STAR_DIGITS if grid == "*" else len(grid)
    unit = None
    if (unit_node := node.unit()) is not None:
        unit = unquote(need(unit_node.text).text)
    low = _bound(node.min_)
    high = _bound(node.max_)
    if low is not None and high is not None and high < low:
        compilation.fail(
            node, DiagnosticCode.STRUCTURE, f"the upper bound {high} is smaller than the lower bound {low}"
        )
    return Numerical(digits=digits, unit=unit, min=low, max=high, span=compilation.span(node))


def _bound(node: Any) -> Decimal | None:
    if node is None or node.open_ is not None:
        return None
    return Decimal(need(node.floating()).getText())


def _members(compilation: Compilation, enumeration: Enumeration, node: Any) -> None:
    attributes: list[Attribute] = []
    options: list[Option] = []
    for member in children(node):
        try:
            match member:
                case COOMParser.AttributeContext():
                    field = need(member.field())
                    type_ = _field_type(compilation, field)
                    if isinstance(type_, Structure):
                        compilation.fail(
                            field, DiagnosticCode.TYPE, f"an attribute cannot have the structure type {type_.name}"
                        )
                    item: Attribute | Option = Attribute(
                        name=name(field.fieldName), type=type_, span=compilation.span(member)
                    )
                    name_node = field.fieldName
                case COOMParser.OptionContext():
                    item = Option(name=name(member.name()), span=compilation.span(member))
                    name_node = member.name()
                case _:
                    continue
        except Abort:
            continue
        if item.name in {other.name for other in attributes} | {other.name for other in options}:
            compilation.error(
                name_node, DiagnosticCode.NAME, f"the name {item.name} is already defined in {enumeration.name}"
            )
            continue
        item.owner = enumeration
        if isinstance(item, Attribute):
            attributes.append(item)
        else:
            options.append(item)
            compilation.options[member] = item
    if not options:
        compilation.error(
            node.name() or node,
            DiagnosticCode.STRUCTURE,
            f"the enumeration {enumeration.name} needs at least one option",
        )
    enumeration.attributes = tuple(attributes)
    enumeration.options = tuple(options)


def assign_attribute_values(compilation: Compilation, tree: Any) -> None:
    """Assigns to each option its values for the attributes of its enumeration, in declaration order."""
    for node in children(tree):
        enumeration = compilation.declared.get(node)
        if not isinstance(enumeration, Enumeration):
            continue
        for option_node in node.option():
            option = compilation.options.get(option_node)
            if option is None:
                continue
            constants = option_node.constant()
            if len(constants) != len(enumeration.attributes):
                compilation.error(
                    option_node,
                    DiagnosticCode.STRUCTURE,
                    f"the option {option.name} has {len(constants)} values for "
                    f"{len(enumeration.attributes)} attributes",
                )
                continue
            values: dict[Attribute, ConstantValue] = {}
            for attribute, constant in zip(enumeration.attributes, constants, strict=True):
                with contextlib.suppress(Abort):
                    values[attribute] = _attribute_value(compilation, attribute, constant)
            option.values = MappingProxyType(values)


def _attribute_value(compilation: Compilation, attribute: Attribute, node: Any) -> ConstantValue:
    match attribute.type:
        case Numerical():
            if node.floating() is None:
                compilation.fail(node, DiagnosticCode.TYPE, f"the attribute {attribute.name} expects a number")
            return Decimal(node.floating().getText())
        case Textual():
            return unquote(node.getText())
        case Boolean():
            text: str = node.getText()
            if text not in ("true", "false"):
                compilation.fail(node, DiagnosticCode.TYPE, f"the attribute {attribute.name} expects true or false")
            return text == "true"
        case Enumeration() as enumeration:
            try:
                return enumeration.option(unquote(node.getText()))
            except KeyError:
                compilation.fail(node, DiagnosticCode.NAME, f"{node.getText()} is not an option of {enumeration.name}")
        case Structure():
            raise Abort
