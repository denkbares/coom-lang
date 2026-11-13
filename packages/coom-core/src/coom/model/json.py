"""The JSON form of models, described by spec/schema/model.schema.json.

Every entity is one object whose "kind" names its kind and whose "name" is the name selectors accept. Structures
contain their features and enumerations their attributes and options, so a selection of entities consists of the same
objects as the whole model. Entities refer to each other by name. Formulas, conditions and paths are trees of objects
whose "node" names the construct. Numbers are JSON numbers unless a float would change them, in which case they are
decimal strings. Locations count lines and columns from one.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, assert_never

from coom.model._base import Span
from coom.model.behaviors import Combinations, Default, Imply, Optimize, Require, Row, Visibility
from coom.model.formulas import (
    And,
    Binary,
    Call,
    Compare,
    Condition,
    Constant,
    Formula,
    IsDefined,
    Negate,
    Not,
    Or,
    PathAccess,
)
from coom.model.graph import Entity, Model
from coom.model.paths import AttributeStep, FeatureStep, Path
from coom.model.selection import EntityKind, entity_name, kind
from coom.model.testing import (
    IsAvailable,
    IsBlocked,
    IsEmpty,
    IsFixed,
    IsHidden,
    IsReadonly,
    IsShown,
    RemoveValue,
    ResetValue,
    SetValue,
    TestCase,
    TestStep,
)
from coom.model.types import (
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

type JSON = dict[str, Any]

_STEPS: dict[type[TestStep], str] = {
    SetValue: "set",
    RemoveValue: "remove",
    ResetValue: "reset",
    IsFixed: "isFixed",
    IsShown: "isShown",
    IsEmpty: "isEmpty",
    IsAvailable: "isAvailable",
    IsBlocked: "isBlocked",
    IsHidden: "isHidden",
    IsReadonly: "isReadonly",
}
"""The keyword of each test step."""


def write_model(model: Model) -> JSON:
    """Returns the JSON object of a whole model."""
    return {
        "root": write_entity(model.root),
        "structures": [write_entity(structure) for structure in model.structures],
        "enumerations": [write_entity(enumeration) for enumeration in model.enumerations],
        "behaviors": [write_entity(behavior) for behavior in model.behaviors],
        "tests": [write_entity(test) for test in model.tests],
    }


def write_entity(entity: Entity) -> JSON:
    """Returns the JSON object of an entity, for a structure or enumeration including its members."""
    result: JSON = {"kind": str(kind(entity)), "name": entity_name(entity)}
    match entity:
        case Structure():
            result["features"] = [write_entity(feature) for feature in entity.features]
        case Feature():
            result["structure"] = entity.owner.name
            result["min"] = entity.min
            result["max"] = entity.max
            result["type"] = write_type(entity.type)
        case Enumeration():
            result["attributes"] = [write_entity(attribute) for attribute in entity.attributes]
            result["options"] = [write_entity(option) for option in entity.options]
        case Attribute():
            result["enumeration"] = entity.owner.name
            result["type"] = write_type(entity.type)
        case Option():
            result["enumeration"] = entity.owner.name
            result["values"] = {attribute.name: _value(value) for attribute, value in entity.values.items()}
        case TestCase():
            result["origin"] = entity.origin.name
            result["steps"] = [_step(step) for step in entity.steps]
        case _:
            result.update(_behavior(entity))
    result["location"] = write_location(entity.span)
    return result


def write_location(span: Span | None) -> JSON | None:
    """Returns a span with lines and columns counted from one, the end column being exclusive."""
    if span is None:
        return None
    return {
        "source": span.source,
        "line": span.line,
        "column": span.column + 1,
        "endLine": span.end_line,
        "endColumn": span.end_column + 1,
    }


def write_type(type_: Type) -> JSON:
    match type_:
        case Structure():
            return {"type": str(EntityKind.STRUCTURE), "name": type_.name}
        case Enumeration():
            return {"type": str(EntityKind.ENUMERATION), "name": type_.name}
        case Numerical():
            return {
                "type": "number",
                "digits": type_.digits,
                "unit": type_.unit,
                "min": None if type_.min is None else write_number(type_.min),
                "max": None if type_.max is None else write_number(type_.max),
            }
        case Textual():
            return {"type": "text"}
        case Boolean():
            return {"type": "boolean"}
        case _:
            assert_never(type_)


def write_formula(formula: Formula | Condition) -> JSON:
    """Returns the tree of a formula or a condition."""
    match formula:
        case Constant():
            return _constant(formula.value)
        case PathAccess():
            return {"node": "path", "path": write_path(formula.path)}
        case Negate():
            return {"node": "negate", "operand": write_formula(formula.operand)}
        case Binary():
            return {
                "node": "binary",
                "op": str(formula.op),
                "left": write_formula(formula.left),
                "right": write_formula(formula.right),
            }
        case Call():
            return {
                "node": "call",
                "function": str(formula.function),
                "arguments": [write_formula(argument) for argument in formula.args],
            }
        case Compare():
            return {
                "node": "compare",
                "op": str(formula.op),
                "left": write_formula(formula.left),
                "right": write_formula(formula.right),
            }
        case IsDefined():
            return {"node": "defined", "formula": write_formula(formula.formula)}
        case Not():
            return {"node": "not", "operand": write_formula(formula.operand)}
        case And():
            return {"node": "and", "operands": [write_formula(operand) for operand in formula.operands]}
        case Or():
            return {"node": "or", "operands": [write_formula(operand) for operand in formula.operands]}
        case _:
            assert_never(formula)


def write_path(path: Path) -> JSON:
    steps: list[JSON] = []
    for step in path.steps:
        match step:
            case FeatureStep():
                index = None if step.index is None else {"first": step.index.first, "last": step.index.last}
                steps.append({"feature": step.feature.qualified_name, "index": index})
            case AttributeStep():
                steps.append({"attribute": step.attribute.qualified_name})
            case _:
                assert_never(step)
    return {"origin": path.origin.name, "rooted": path.rooted, "steps": steps}


def _behavior(behavior: Require | Imply | Default | Optimize | Visibility | Combinations) -> JSON:
    result: JSON = {"origin": behavior.origin.name}
    match behavior:
        case Require():
            result["statement"] = "require"
            result["condition"] = write_formula(behavior.condition)
        case Imply():
            result["statement"] = "imply"
            result["target"] = write_path(behavior.target)
            result["value"] = write_formula(behavior.value)
        case Default():
            result["statement"] = "default"
            result["target"] = write_path(behavior.target)
            result["value"] = write_formula(behavior.value)
            result["priority"] = behavior.priority
        case Optimize():
            result["statement"] = str(behavior.direction)
            result["target"] = write_path(behavior.target)
        case Visibility():
            result["statement"] = str(behavior.directive)
            result["target"] = write_path(behavior.target)
            result["options"] = [option.qualified_name for option in behavior.options]
        case Combinations():
            result["statement"] = "combinations"
            result["columns"] = [write_formula(column) for column in behavior.columns]
            result["rows"] = [_row(row) for row in behavior.rows]
        case _:
            assert_never(behavior)
    result["conditions"] = [write_formula(condition) for condition in behavior.conditions]
    result["explanation"] = behavior.explanation
    return result


def _row(row: Row) -> JSON:
    cells = [
        None if cell is None else [{"op": str(atom.op), "value": write_formula(atom.value)} for atom in cell]
        for cell in row.cells
    ]
    return {"kind": str(row.kind), "cells": cells}


def _step(step: TestStep) -> JSON:
    value = getattr(step, "value", None)
    return {
        "step": _STEPS[type(step)],
        "path": write_path(step.path),
        "value": None if value is None else write_formula(value),
    }


def _constant(value: ConstantValue) -> JSON:
    match value:
        case bool():
            return {"node": "boolean", "value": value}
        case Decimal():
            return {"node": "number", "value": write_number(value)}
        case str():
            return {"node": "text", "value": value}
        case Option():
            return {"node": "option", "option": value.qualified_name}
        case _:
            assert_never(value)


def _value(value: ConstantValue) -> Any:
    """Returns an attribute value as in configurations, options by their name."""
    match value:
        case Decimal():
            return write_number(value)
        case Option():
            return value.name
        case _:
            return value


def write_number(value: Decimal) -> int | float | str:
    """Returns a number as an int or float, or as a decimal string where a float would change it."""
    if value == value.to_integral_value():
        return int(value)
    # a float carries the exact decimal only while its shortest form is that decimal
    return float(value) if Decimal(repr(float(value))) == value else str(value)
