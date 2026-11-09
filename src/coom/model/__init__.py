"""The compiled COOM model as a navigable graph.

The model distinguishes two kinds of objects.

Entities are the nodes of the graph (structures, features, enumerations, options, attributes, behaviors, tests). They
compare by identity, refer to each other directly and in both directions, and can be used as dictionary keys.

Values are immutable data that compare by content (numeric types, paths, formulas, conditions, test steps). They may
refer to entities, for example a path step holds the feature it follows.

The compiler builds the graph and hands it over as finished. Collections are tuples or read only mappings, and nothing
should be assigned after the model is constructed, because the model derives back references and lookup indexes once.

Read the modules in the order types, paths, formulas, behaviors, testing, traversal and graph, since each one builds
only on those before it. Everything is re-exported here, so client code imports from coom.model directly.
"""

from coom.model._base import Span
from coom.model.behaviors import (
    Behavior,
    Cell,
    CellAtom,
    Combinations,
    Default,
    Direction,
    Directive,
    Imply,
    Optimize,
    Require,
    Row,
    RowKind,
    Visibility,
)
from coom.model.formulas import (
    And,
    Binary,
    BinaryOp,
    Call,
    Compare,
    CompareOp,
    Condition,
    Constant,
    Formula,
    Function,
    IsDefined,
    Negate,
    Not,
    Or,
    PathAccess,
)
from coom.model.graph import Item, Model
from coom.model.paths import AttributeStep, FeatureStep, Index, Path, Step
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
from coom.model.traversal import Node, children, parts, referenced, walk
from coom.model.types import (
    BOOLEAN_NAME,
    ROOT_NAME,
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
    options,
    type_name,
)

__all__ = [
    "BOOLEAN_NAME",
    "ROOT_NAME",
    "And",
    "Attribute",
    "AttributeStep",
    "Behavior",
    "Binary",
    "BinaryOp",
    "Boolean",
    "Call",
    "Cell",
    "CellAtom",
    "Combinations",
    "Compare",
    "CompareOp",
    "Condition",
    "Constant",
    "ConstantValue",
    "Default",
    "Direction",
    "Directive",
    "Enumeration",
    "Feature",
    "FeatureStep",
    "Formula",
    "Function",
    "Imply",
    "Index",
    "IsAvailable",
    "IsBlocked",
    "IsDefined",
    "IsEmpty",
    "IsFixed",
    "IsShown",
    "Item",
    "Model",
    "Negate",
    "Node",
    "Not",
    "Numerical",
    "Optimize",
    "Option",
    "Or",
    "Path",
    "PathAccess",
    "RemoveValue",
    "Require",
    "ResetValue",
    "Row",
    "RowKind",
    "SetValue",
    "Span",
    "Step",
    "Structure",
    "TestCase",
    "TestStep",
    "Textual",
    "Type",
    "Visibility",
    "children",
    "options",
    "parts",
    "referenced",
    "type_name",
    "walk",
]
