"""Generic walks over the values a behavior or test consists of."""

from __future__ import annotations

from collections.abc import Iterator
from typing import assert_never

from coom.model.behaviors import Behavior, CellAtom, Combinations, Default, Imply, Optimize, Require, Row, Visibility
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
from coom.model.paths import AttributeStep, FeatureStep, Path, Step
from coom.model.testing import (
    IsAvailable,
    IsBlocked,
    IsEmpty,
    IsFixed,
    IsShown,
    RemoveValue,
    ResetValue,
    SetValue,
    TestCase,
    TestStep,
)
from coom.model.types import Attribute, Feature, Option

type Node = Formula | Condition | Path | Step | Row | CellAtom | TestStep


def parts(item: Behavior | TestCase) -> tuple[Node, ...]:
    """Returns the values a behavior or test directly consists of, in source order."""
    match item:
        case Require():
            return (*item.conditions, item.condition)
        case Imply() | Default():
            return (*item.conditions, item.target, item.value)
        case Optimize() | Visibility():
            return (*item.conditions, item.target)
        case Combinations():
            return (*item.conditions, *item.columns, *item.rows)
        case TestCase():
            return item.steps
        case _:
            assert_never(item)


def children(node: Node) -> tuple[Node, ...]:
    """Returns the direct sub values of a value node."""
    match node:
        case Constant() | FeatureStep() | AttributeStep():
            return ()
        case PathAccess():
            return (node.path,)
        case Path():
            return node.steps
        case Negate() | Not():
            return (node.operand,)
        case Binary() | Compare():
            return (node.left, node.right)
        case Call():
            return node.args
        case IsDefined():
            return (node.formula,)
        case And() | Or():
            return node.operands
        case Row():
            return tuple(atom for cell in node.cells if cell is not None for atom in cell)
        case CellAtom():
            return (node.value,)
        case RemoveValue() | ResetValue() | IsEmpty():
            return (node.path,)
        case SetValue() | IsFixed() | IsShown() | IsAvailable() | IsBlocked():
            return (node.path,) if node.value is None else (node.path, node.value)
        case _:
            assert_never(node)


def walk(*nodes: Node) -> Iterator[Node]:
    """Yields the given nodes and all their descendants in depth first pre order."""
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(children(node)))


def referenced(item: Behavior | TestCase) -> Iterator[Feature | Attribute | Option]:
    """Yields the features, attributes and options a behavior or test refers to, possibly repeated."""
    for node in walk(*parts(item)):
        match node:
            case FeatureStep():
                yield node.feature
            case AttributeStep():
                yield node.attribute
            case Constant(value=Option() as option):
                yield option
    if isinstance(item, Visibility):
        yield from item.options
