"""Translation of a model and the inputs of a configuration into the facts the encoding interprets.

The translation reifies the declarations, which the encoding unrolls into every potential instance up to the maximum
cardinalities, and the formulas and conditions of the behaviors as trees of numbered nodes. It keeps the model
objects behind every node, so the propagator can evaluate the parts that the encoding leaves to it.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from importlib.resources import files
from typing import assert_never

from clingo import Control, Function, Number, String, Symbol
from coom.configuration import Configuration, Instance, Value
from coom.diagnostics import Diagnostic, DiagnosticCode, Severity
from coom.model import (
    And,
    AttributeStep,
    Behavior,
    Binary,
    Boolean,
    Call,
    Combinations,
    Compare,
    CompareOp,
    Condition,
    Constant,
    ConstantValue,
    Default,
    Enumeration,
    Feature,
    FeatureStep,
    Formula,
    Imply,
    IsDefined,
    Model,
    Negate,
    Not,
    Numerical,
    Optimize,
    Option,
    Or,
    Path,
    PathAccess,
    Require,
    RowKind,
    Structure,
    Textual,
    Visibility,
    formulas,
)

ROOT = Function("root")

_OPERATORS = {
    CompareOp.LT: "lt",
    CompareOp.LE: "le",
    CompareOp.GT: "gt",
    CompareOp.GE: "ge",
    CompareOp.EQ: "eq",
    CompareOp.NE: "ne",
}

_AGGREGATES = frozenset({formulas.Function.COUNT, formulas.Function.SUM, formulas.Function.MIN, formulas.Function.MAX})

# An explicit priority beats every implicit one, which is one plus the number of distinct preconditions.
_EXPLICIT_PRIORITY = 1000


# The universe of potential instances


@dataclass(frozen=True, slots=True)
class InstanceInfo:
    term: Symbol
    structure: Structure
    parent: Symbol | None = None
    feature: Feature | None = None
    index: int = 0


@dataclass(frozen=True, slots=True)
class SlotInfo:
    term: Symbol
    instance: Symbol
    feature: Feature
    index: int

    @property
    def is_required(self) -> bool:
        return self.index < self.feature.min


class Universe:
    """The potential instances of a model, parents before children, and their slots.

    The instances are unrolled by the encoding, this class reads them from its ground atoms.
    """

    def __init__(self, model: Model, atoms: Iterable[Symbol]) -> None:
        self.instances: dict[Symbol, InstanceInfo] = {}
        self.slots: dict[Symbol, SlotInfo] = {}
        self.slots_of: dict[tuple[Symbol, Feature], tuple[Symbol, ...]] = {}
        self.of_structure: dict[Structure, list[Symbol]] = {}
        structures: dict[Symbol, Structure] = {}
        slot_atoms: list[Symbol] = []
        for atom in atoms:
            if atom.match("instance", 2):
                structures[atom.arguments[0]] = model.structure(atom.arguments[1].string)
            elif atom.match("slot", 4):
                slot_atoms.append(atom)
        by_instance: dict[Symbol, list[SlotInfo]] = {}
        for atom in slot_atoms:
            term, instance, name, index = atom.arguments
            info = SlotInfo(term, instance, structures[instance].feature(name.string), index.number)
            self.slots[term] = info
            by_instance.setdefault(instance, []).append(info)
        for term in sorted(structures, key=_depth):
            holder = self.slots.get(term)
            if holder is None:
                self.instances[term] = InstanceInfo(term, structures[term])
            else:
                self.instances[term] = InstanceInfo(
                    term, structures[term], holder.instance, holder.feature, holder.index
                )
            self.of_structure.setdefault(structures[term], []).append(term)
            for feature in structures[term].features:
                owned = sorted((slot for slot in by_instance.get(term, ()) if slot.feature is feature), key=_index)
                self.slots_of[term, feature] = tuple(slot.term for slot in owned)

    @classmethod
    def unroll(cls, model: Model, facts: Iterable[Symbol]) -> Universe:
        """Grounds the declarations with the rules that unroll instances and reads the result."""
        control = Control(logger=lambda code, message: None)
        program = "".join(f"{fact}.\n" for fact in facts if fact.match("feature", 4) or fact.match("kind", 3))
        control.add("base", [], program + encoding_file("instances.lp"))
        control.ground([("base", [])])
        return cls(model, (atom.symbol for atom in control.symbolic_atoms))

    def slot(self, instance: Symbol, feature: Feature, index: int) -> Symbol | None:
        terms = self.slots_of.get((instance, feature), ())
        return terms[index] if 0 <= index < len(terms) else None


def encoding_file(name: str) -> str:
    return (files("coom.clingo") / "encoding" / name).read_text(encoding="utf-8")


def _depth(term: Symbol) -> tuple[int, str]:
    depth = 0
    while term.match("s", 3):
        term = term.arguments[0]
        depth += 1
    return depth, str(term)


def _index(slot: SlotInfo) -> int:
    return slot.index


# Terms of values


def value_term(value: ConstantValue) -> Symbol:
    match value:
        case Option():
            return Function("o", [String(value.owner.name), String(value.name)])
        case bool():
            return Function("b", [Function("true" if value else "false")])
        case Decimal():
            return Function("n", [String(str(value))])
        case str():
            return Function("t", [String(value)])
        case _:
            assert_never(value)


def is_discrete(type_: object) -> bool:
    return isinstance(type_, Structure | Enumeration | Boolean)


def _kind(feature: Feature) -> Symbol:
    match feature.type:
        case Structure(name=name):
            return Function("struct", [String(name)])
        case Enumeration(name=name):
            return Function("enum", [String(name)])
        case Boolean():
            return Function("bool")
        case Numerical():
            return Function("num")
        case Textual():
            return Function("text")
        case _:
            assert_never(feature.type)


# Nodes the propagator works with


@dataclass(eq=False, slots=True)
class Leaf:
    """A comparison or definedness test over numbers or texts whose truth the propagator decides."""

    id: int
    node: Compare | IsDefined
    origin: Structure


@dataclass(eq=False, slots=True)
class Producer:
    """A statement that writes the value of a formula into numeric or text slots."""

    id: int
    behavior: int
    kind: str
    target: Path
    target_id: int
    formula: Formula
    origin: Structure


@dataclass(eq=False, slots=True)
class DiscreteDefault:
    behavior: int
    target: Path
    target_id: int
    origin: Structure


@dataclass(eq=False)
class Encoding:
    """The facts of a model together with the model objects behind their numbered nodes."""

    model: Model
    universe: Universe = field(init=False)
    facts: list[Symbol] = field(default_factory=list, init=False)
    leaves: dict[int, Leaf] = field(default_factory=dict, init=False)
    producers: dict[int, Producer] = field(default_factory=dict, init=False)
    discrete_defaults: list[DiscreteDefault] = field(default_factory=list, init=False)
    behaviors: dict[int, Behavior] = field(default_factory=dict, init=False)
    diagnostics: list[Diagnostic] = field(default_factory=list, init=False)
    _next: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        for feature in self.model.features():
            if feature.max is None:
                self._report(
                    Severity.ERROR, f"the solver needs a bounded cardinality for {feature.qualified_name}", feature
                )
        self._declare()
        self.universe = Universe.unroll(self.model, self.facts)
        for behavior in self.model.behaviors:
            self._behavior(behavior)

    @property
    def ok(self) -> bool:
        return not any(diagnostic.severity is Severity.ERROR for diagnostic in self.diagnostics)

    def _report(self, severity: Severity, message: str, item: Behavior | Feature) -> None:
        self.diagnostics.append(Diagnostic(severity, DiagnosticCode.SOLVER, message, item.span))

    def _fact(self, name: str, *arguments: Symbol | int | str) -> None:
        self.facts.append(Function(name, [_symbol(argument) for argument in arguments]))

    def _id(self) -> int:
        self._next += 1
        return self._next

    # Declarations and the universe

    def _declare(self) -> None:
        for structure in (self.model.root, *self.model.structures):
            for feature in structure.features:
                if feature.max is None:
                    continue
                self._fact("feature", structure.name, feature.name, feature.min, feature.max)
                self._fact("kind", structure.name, feature.name, _kind(feature))
        for enumeration in self.model.enumerations:
            for position, option in enumerate(enumeration.options):
                self._fact("option", enumeration.name, option.name, position)
                for attribute, value in option.values.items():
                    self._fact("attribute", enumeration.name, option.name, attribute.name, value_term(value))
                    if isinstance(value, str) and not value.strip():
                        self._fact("falsy", value_term(value))

    # Behaviors

    def _behavior(self, behavior: Behavior) -> None:
        if isinstance(behavior, Visibility):
            return
        if isinstance(behavior, Optimize):
            self._report(Severity.WARNING, f"the solver ignores {behavior.direction} statements", behavior)
            return
        id = self._id()
        self.behaviors[id] = behavior
        origin = behavior.origin
        try:
            match behavior:
                case Require():
                    self._require(id, behavior.condition, origin)
                case Combinations():
                    self._require(id, _table(behavior), origin)
                case Imply():
                    self._assignment(id, behavior, "imply")
                case Default():
                    self._assignment(id, behavior, "default")
                case _:
                    assert_never(behavior)
        except _Unsupported as error:
            self._report(Severity.ERROR, str(error), behavior)
            return
        self._fact("behavior", id, origin.name)
        for condition in dict.fromkeys(behavior.conditions):
            self._fact("precondition", id, self._condition(condition, origin))

    def _require(self, id: int, condition: Condition, origin: Structure) -> None:
        self._fact("require", id, self._condition(condition, origin))
        # an equality with a bare numeric or text path on one side determines that path from the other side
        if isinstance(condition, Compare) and condition.op is CompareOp.EQ:
            for bare, other in ((condition.left, condition.right), (condition.right, condition.left)):
                if isinstance(bare, PathAccess) and not bare.path.is_range and not is_discrete(bare.path.type):
                    self._producer(id, "require", bare.path, other, origin)

    def _assignment(self, id: int, behavior: Imply | Default, kind: str) -> None:
        target, value, origin = behavior.target, behavior.value, behavior.origin
        if isinstance(target.type, Structure):
            raise _Unsupported(f"the solver cannot {kind} instances of {target.type.name}")
        if is_discrete(target.type):
            if not (_is_discrete_constant(value) or _is_scalar_discrete_path(value)):
                raise _Unsupported(f"the solver needs an option, a truth value or a path as the value of an {kind}")
            target_id = self._path(target, origin, target=True)
            self._fact("assign", self._id(), id, Function(kind), target_id, self._formula(value, origin))
            if kind == "default":
                self.discrete_defaults.append(DiscreteDefault(id, target, target_id, origin))
        else:
            self._producer(id, kind, target, value, origin)
        if isinstance(behavior, Default):
            if behavior.priority is not None:
                level = _EXPLICIT_PRIORITY + behavior.priority
            else:
                level = 1 + len(set(behavior.conditions))
            self._fact("default", id, level)

    def _producer(self, behavior: int, kind: str, target: Path, formula: Formula, origin: Structure) -> None:
        for step in target.steps:
            backwards = (
                isinstance(step, FeatureStep) and step.index is not None and min(step.index.first, step.index.last) < 0
            )
            if backwards and not is_discrete(step.type):
                raise _Unsupported("the solver cannot write numeric slots addressed from the end")
        id = self._id()
        target_id = self._path(target, origin, target=True)
        formula_id = self._formula(formula, origin)
        self.producers[id] = Producer(id, behavior, kind, target, target_id, formula, origin)
        self._fact("assign", id, behavior, Function(kind), target_id, formula_id)

    # Conditions and formulas

    def _condition(self, condition: Condition, origin: Structure) -> int:
        id = self._id()
        self._fact("origin", id, origin.name)
        match condition:
            case Compare():
                left = self._formula(condition.left, origin)
                right = self._formula(condition.right, origin)
                if _is_discrete_formula(condition.left) and _is_discrete_formula(condition.right):
                    self._fact("discrete_compare", id, Function(_OPERATORS[condition.op]), left, right)
                else:
                    self._leaf(id, condition, origin, left, right)
            case IsDefined(formula=PathAccess() as access):
                self._fact("is_defined", id, self._formula(access, origin))
            case IsDefined():
                self._leaf(id, condition, origin, self._formula(condition.formula, origin))
                self._fact("definedness_test", id)
            case Not():
                self._fact("negation", id, self._condition(condition.operand, origin))
            case And():
                self._fact("and", id)
                for operand in condition.operands:
                    self._fact("and", id, self._condition(operand, origin))
            case Or():
                self._fact("or", id)
                for operand in condition.operands:
                    self._fact("or", id, self._condition(operand, origin))
            case Constant(value=bool() as value):
                self._fact("constant", id, value_term(value))
            case Constant():
                raise _Unsupported(f"the constant {condition.value} is not a condition")
            case _:
                assert_never(condition)
        return id

    def _leaf(self, id: int, node: Compare | IsDefined, origin: Structure, *operands: int) -> None:
        self.leaves[id] = Leaf(id, node, origin)
        self._fact("leaf", id)
        for operand in operands:
            self._fact("operand", id, operand)

    def _formula(self, formula: Formula, origin: Structure) -> int:
        match formula:
            case PathAccess():
                return self._path(formula.path, origin)
            case Constant():
                id = self._id()
                self._fact("origin", id, origin.name)
                self._fact("constant", id, value_term(formula.value))
                return id
            case Negate() | Binary() | Call():
                id = self._id()
                self._fact("origin", id, origin.name)
                self._fact("compound", id)
                if isinstance(formula, Call) and formula.function in _AGGREGATES:
                    self._fact("aggregate", id)
                for operand in _operands(formula):
                    self._fact("operand", id, self._formula(operand, origin))
                return id
            case _:
                assert_never(formula)

    def _path(self, path: Path, origin: Structure, *, target: bool = False) -> int:
        id = self._id()
        self._fact("origin", id, origin.name)
        self._fact("path_start", id, Function("origin" if path.origin is origin else "root"))
        self._fact("path_length", id, len(path.steps))
        self._fact("path_kind", id, Function("discrete" if is_discrete(path.type) else "numeric"))
        if path.is_range:
            self._fact("path_range", id)
        if target:
            self._fact("target", id)
        for number, step in enumerate(path.steps, start=1):
            match step:
                case FeatureStep(feature=feature, index=None):
                    self._fact("path_step", id, number, feature.name, 0, max((feature.max or 1) - 1, 0))
                case FeatureStep(feature=feature, index=index) if index is not None:
                    self._fact("path_step", id, number, feature.name, index.first, index.last)
                case AttributeStep(attribute=attribute):
                    self._fact("path_attribute", id, number, attribute.name)
        return id

    # Inputs

    def inputs(
        self, configuration: Configuration
    ) -> tuple[list[Symbol], dict[Symbol, ConstantValue], dict[Symbol, str]]:
        """Returns the facts of the values a configuration holds, the numbers and texts by slot, and instance names."""
        facts: list[Symbol] = []
        values: dict[Symbol, ConstantValue] = {}
        names: dict[Symbol, str] = {ROOT: configuration.root.name}
        for term, feature, value in self._assignments(configuration.root, ROOT):
            if isinstance(value, Instance):
                facts.append(Function("input", [term]))
                names[term] = value.name
            elif is_discrete(feature.type):
                facts.append(Function("input", [term, value_term(value)]))
            else:
                facts.append(Function("input", [term]))
                values[term] = value
        return facts, values, names

    def _assignments(self, instance: Instance, term: Symbol) -> Iterator[tuple[Symbol, Feature, Value]]:
        for feature in instance.type.features:
            for index, assignment in instance.assignments(feature).items():
                slot = self.universe.slot(term, feature, index)
                if slot is None:
                    raise ValueError(f"{instance!r} has no slot {index} of {feature.qualified_name} in the solver")
                yield slot, feature, assignment.value
                if isinstance(assignment.value, Instance):
                    yield from self._assignments(assignment.value, slot)


class _Unsupported(Exception):
    pass


def _symbol(argument: Symbol | int | str) -> Symbol:
    if isinstance(argument, int):
        return Number(argument)
    if isinstance(argument, str):
        return String(argument)
    return argument


def _operands(formula: Negate | Binary | Call) -> tuple[Formula, ...]:
    """The operands whose values a formula needs, which for a rounding excludes the digits read from a type."""
    match formula:
        case Negate():
            return (formula.operand,)
        case Binary():
            return (formula.left, formula.right)
        case Call(function=formulas.Function.ROUND):
            return formula.args[:1]
        case Call():
            return formula.args


def _is_discrete_constant(formula: Formula) -> bool:
    return isinstance(formula, Constant) and isinstance(formula.value, Option | bool)


def _is_scalar_discrete_path(formula: Formula) -> bool:
    return isinstance(formula, PathAccess) and is_discrete(formula.path.type) and not formula.path.is_range


def _is_discrete_formula(formula: Formula) -> bool:
    return _is_discrete_constant(formula) or (isinstance(formula, PathAccess) and is_discrete(formula.path.type))


def _table(table: Combinations) -> Condition:
    """The condition of a combinations table, some allow row matching unless there is none and no forbid row."""

    def row(cells: tuple[tuple[Compare, ...] | None, ...]) -> Condition:
        return And(tuple(Or(cell) for cell in cells if cell is not None))

    rows = [
        (
            item.kind,
            row(
                tuple(
                    None if cell is None else tuple(Compare(atom.op, column, atom.value) for atom in cell)
                    for column, cell in zip(table.columns, item.cells, strict=True)
                )
            ),
        )
        for item in table.rows
    ]
    allowed = [condition for kind, condition in rows if kind is RowKind.ALLOW]
    forbidden: list[Condition] = [Not(condition) for kind, condition in rows if kind is RowKind.FORBID]
    return And(tuple([Or(tuple(allowed)), *forbidden] if allowed else forbidden))
