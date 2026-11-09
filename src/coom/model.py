"""The compiled COOM model as a navigable graph.

The model distinguishes two kinds of objects.

Entities are the nodes of the graph (structures, features, enumerations, options, attributes, behaviors, tests). They
compare by identity, refer to each other directly and in both directions, and can be used as dictionary keys.

Values are immutable data that compare by content (numeric types, paths, formulas, conditions, test steps). They may
refer to entities, for example a path step holds the feature it follows.

The compiler builds the graph and hands it over as finished. Collections are tuples or read only mappings, and nothing
should be assigned after the model is constructed, because the model derives back references and lookup indexes once.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import KW_ONLY, dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import assert_never

ROOT_NAME = ":root"
"""Name of the structure that the product block declares."""


@dataclass(frozen=True, slots=True)
class Span:
    """A region of a source text with lines counted from one and columns from zero, as ANTLR does."""

    line: int
    column: int
    end_line: int
    end_column: int
    source: str | None = None


def _span() -> Span | None:
    return field(default=None, compare=False, repr=False)  # type: ignore[no-any-return]


# Types


@dataclass(frozen=True, slots=True, kw_only=True)
class Numerical:
    """A numeric type with a decimal grid of `digits` fraction digits, an optional unit and optional bounds."""

    digits: int = 0
    unit: str | None = None
    min: Decimal | None = None
    max: Decimal | None = None
    span: Span | None = _span()

    @property
    def step(self) -> Decimal:
        """The distance between two neighboring grid values."""
        return Decimal(1).scaleb(-self.digits)


@dataclass(frozen=True, slots=True, kw_only=True)
class Textual:
    """The type of text values."""

    span: Span | None = _span()


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


# Paths


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
    span: Span | None = _span()

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
    span: Span | None = _span()

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
    span: Span | None = _span()

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


# Formulas and conditions


class BinaryOp(StrEnum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    POW = "^"


class CompareOp(StrEnum):
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "="
    NE = "!="


class Function(StrEnum):
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    POW = "pow"
    SQRT = "sqrt"
    CEIL = "ceil"
    FLOOR = "floor"
    ROUND = "round"
    MOD = "mod"
    LOG = "log"
    LN = "ln"
    SIN = "sin"
    ASIN = "asin"
    SINH = "sinh"
    COS = "cos"
    ACOS = "acos"
    COSH = "cosh"
    TAN = "tan"
    ATAN = "atan"
    TANH = "tanh"


@dataclass(frozen=True, slots=True)
class Constant:
    """A literal number, truth value, text or option, also usable as a condition if it is a truth value."""

    value: ConstantValue
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class PathAccess:
    """The value or, for a range path, the sequence of values a path addresses."""

    path: Path
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class Negate:
    operand: Formula
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class Binary:
    op: BinaryOp
    left: Formula
    right: Formula
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class Call:
    function: Function
    args: tuple[Formula, ...]
    _: KW_ONLY
    span: Span | None = _span()


type Formula = Constant | PathAccess | Negate | Binary | Call


@dataclass(frozen=True, slots=True)
class Compare:
    op: CompareOp
    left: Formula
    right: Formula
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class IsDefined:
    """Holds if the formula has a value, which is how a bare formula reads as a condition."""

    formula: Formula
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class Not:
    operand: Condition
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class And:
    operands: tuple[Condition, ...]
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class Or:
    operands: tuple[Condition, ...]
    _: KW_ONLY
    span: Span | None = _span()


type Condition = Compare | IsDefined | Not | And | Or | Constant


# Behaviors


class Direction(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class Directive(StrEnum):
    READONLY = "readonly"
    HIDE = "hide"


class RowKind(StrEnum):
    ALLOW = "allow"
    FORBID = "forbid"


@dataclass(eq=False, slots=True, kw_only=True)
class _BehaviorBase:
    origin: Structure
    """The structure whose instances the behavior applies to, paths in it start there."""
    conditions: tuple[Condition, ...] = ()
    """The preconditions of the statement and of all blocks enclosing it."""
    explanation: str | None = None
    span: Span | None = field(default=None, repr=False)


@dataclass(eq=False, slots=True, kw_only=True)
class Require(_BehaviorBase):
    condition: Condition


@dataclass(eq=False, slots=True, kw_only=True)
class Imply(_BehaviorBase):
    target: Path
    value: Formula


@dataclass(eq=False, slots=True, kw_only=True)
class Default(_BehaviorBase):
    target: Path
    value: Formula
    priority: int | None = None
    """The explicitly written priority, None if the source gave none."""


@dataclass(eq=False, slots=True, kw_only=True)
class Optimize(_BehaviorBase):
    direction: Direction
    target: Path


@dataclass(eq=False, slots=True, kw_only=True)
class Visibility(_BehaviorBase):
    """Hides or locks the target feature or, if options are given, only these options of it."""

    directive: Directive
    target: Path
    options: tuple[Option, ...] = ()


@dataclass(frozen=True, slots=True)
class CellAtom:
    """Holds if the column value compares to `value` by `op`."""

    value: Formula
    op: CompareOp = CompareOp.EQ
    _: KW_ONLY
    span: Span | None = _span()


type Cell = tuple[CellAtom, ...]
"""A table cell that holds if any of its atoms holds."""


@dataclass(frozen=True, slots=True)
class Row:
    """A row of a combinations table, None marking a cell that matches anything."""

    kind: RowKind
    cells: tuple[Cell | None, ...]
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(eq=False, slots=True, kw_only=True)
class Combinations(_BehaviorBase):
    columns: tuple[Formula, ...]
    rows: tuple[Row, ...] = ()


type Behavior = Require | Imply | Default | Optimize | Visibility | Combinations


# Tests


@dataclass(frozen=True, slots=True)
class SetValue:
    path: Path
    value: Formula | None = None
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class RemoveValue:
    path: Path
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class ResetValue:
    path: Path
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class IsFixed:
    path: Path
    value: Formula | None = None
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class IsShown:
    path: Path
    value: Formula | None = None
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class IsEmpty:
    path: Path
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class IsAvailable:
    path: Path
    value: Formula
    _: KW_ONLY
    span: Span | None = _span()


@dataclass(frozen=True, slots=True)
class IsBlocked:
    path: Path
    value: Formula
    _: KW_ONLY
    span: Span | None = _span()


type TestStep = SetValue | RemoveValue | ResetValue | IsFixed | IsShown | IsEmpty | IsAvailable | IsBlocked


@dataclass(eq=False, slots=True, kw_only=True)
class TestCase:
    """A scripted session on the root structure."""

    name: str | None = None
    steps: tuple[TestStep, ...] = ()
    span: Span | None = field(default=None, repr=False)


# Traversal


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


# Model


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

    def __getitem__(self, qualified_name: str) -> Item:
        """Returns a type by name or a feature, attribute or option by a name such as "Bike.color"."""
        type_name_, _, member = qualified_name.partition(".")
        type_ = self.type(type_name_)
        if not member:
            return type_
        if isinstance(type_, Structure):
            return type_.feature(member)
        for candidate in (*type_.attributes, *type_.options):
            if candidate.name == member:
                return candidate
        raise KeyError(qualified_name)

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


def options(*names: str) -> tuple[Option, ...]:
    """Creates options without attribute values, which is the common case when building models by hand."""
    return tuple(Option(name=name) for name in names)


def unique(items: Iterable[Item]) -> tuple[Item, ...]:
    """Returns the items without repetitions, keeping the first occurrence."""
    return tuple(dict.fromkeys(items))
