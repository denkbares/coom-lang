"""The propagator that owns numbers and texts.

The encoding decides structure, options, truth values and which producers are on. This module computes the values
of numeric and text slots as the least fixpoint of the valued producers, using the exact arithmetic of the evaluate
module, and decides every atom that depends on a value: whether a producer that is on has a value, the outcome of the
comparisons the encoding leaves to it, and whether a text is blank. A failing computation is excluded by a nogood
over its dependency cone, the literals of everything the computation may read, found by walking its paths through the
potential instances.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from clingo import Function, Number, Symbol
from clingo.propagator import Assignment, PropagateControl, PropagateInit
from clingo.propagator import Propagator as ClingoPropagator
from coom.clingo.facts import ROOT, Encoding, Leaf, Producer, value_term
from coom.configuration import Configuration, Instance, Role, Truth
from coom.configuration.arithmetic import to_decimal, to_grid
from coom.configuration.evaluate import Undefined, evaluate, truth
from coom.model import (
    And,
    AttributeStep,
    Binary,
    Boolean,
    Call,
    Compare,
    Condition,
    Constant,
    ConstantValue,
    Enumeration,
    FeatureStep,
    Formula,
    IsDefined,
    Negate,
    Not,
    Numerical,
    Option,
    Or,
    Path,
    PathAccess,
    Structure,
)

type View = Callable[[Symbol], bool]
type Key = tuple[int, Symbol]
"""A producer or leaf together with the origin instance it is evaluated at."""

_OUTCOMES = {Truth.TRUE: "t", Truth.FALSE: "f", Truth.INDEFINITE: "i"}
_TRUE, _FALSE = Function("b", [Function("true")]), Function("b", [Function("false")])


def atom(name: str, *arguments: Symbol) -> Symbol:
    return Function(name, list(arguments))


# Static dependencies


@dataclass(slots=True)
class _Local:
    symbols: set[Symbol] = field(default_factory=set)
    reads: set[Symbol] = field(default_factory=set)
    """The numeric and text slots read directly."""


class Dependencies:
    """The atoms each producer and leaf may depend on, found by walking paths through the potential instances."""

    def __init__(self, encoding: Encoding) -> None:
        self.encoding = encoding
        self.universe = encoding.universe
        self.producers: list[Key] = []
        self.targets: dict[Key, tuple[Symbol, ...]] = {}
        self.reads: dict[Key, frozenset[Symbol]] = {}
        self.writers: dict[Symbol, list[Key]] = {}
        self._local: dict[Key, _Local] = {}
        for producer in encoding.producers.values():
            for origin in self.universe.of_structure.get(producer.origin, ()):
                key = (producer.id, origin)
                on, valued = atom("on", _number(producer.id), origin), atom("valued", _number(producer.id), origin)
                local = _Local({on, valued, atom("ex", origin)})
                targets: set[Symbol] = set()
                self._walk(producer.target, producer.origin, origin, local, targets)
                for slot in targets:
                    local.symbols.add(atom("tgt", _number(producer.target_id), origin, slot))
                    self.writers.setdefault(slot, []).append(key)
                self._formula(producer.formula, producer.origin, origin, local)
                self.producers.append(key)
                self.targets[key] = tuple(sorted(targets))
                self.reads[key] = frozenset(local.reads)
                self._local[key] = local
        self.default_targets: dict[Key, tuple[Symbol, ...]] = {}
        for default in encoding.discrete_defaults:
            for origin in self.universe.of_structure.get(default.origin, ()):
                targets = set()
                self._walk(default.target, default.origin, origin, _Local(), targets)
                self.default_targets[default.behavior, origin] = tuple(targets)
        self.leaves: dict[Key, _Local] = {}
        for leaf in encoding.leaves.values():
            for origin in self.universe.of_structure.get(leaf.origin, ()):
                local = _Local({atom("ex", origin)})
                self._condition(leaf.node, leaf.origin, origin, local)
                self.leaves[leaf.id, origin] = local

    def cone(self, symbols: Iterable[Symbol], reads: Iterable[Symbol]) -> tuple[set[Symbol], set[Key]]:
        """Closes symbols and read slots over the producers that may write those slots."""
        result = set(symbols)
        producers: set[Key] = set()
        pending = list(reads)
        seen: set[Symbol] = set()
        while pending:
            slot = pending.pop()
            if slot in seen:
                continue
            seen.add(slot)
            result.add(atom("defined", slot))
            for key in self.writers.get(slot, ()):
                if key in producers:
                    continue
                producers.add(key)
                result |= self._local[key].symbols
                pending.extend(self._local[key].reads)
        return result, producers

    def direct(self, key: Key) -> frozenset[Symbol]:
        """The atoms a producer reads and writes itself, without those of the producers it depends on."""
        return frozenset(self._local[key].symbols)

    def producer_cone(self, key: Key) -> tuple[set[Symbol], set[Key]]:
        local = self._local[key]
        symbols, producers = self.cone(local.symbols, local.reads)
        return symbols, producers | {key}

    def _condition(self, condition: Condition, structure: Structure, origin: Symbol, local: _Local) -> None:
        match condition:
            case Compare():
                self._formula(condition.left, structure, origin, local)
                self._formula(condition.right, structure, origin, local)
            case IsDefined():
                self._formula(condition.formula, structure, origin, local)
            case Not():
                self._condition(condition.operand, structure, origin, local)
            case And() | Or():
                for operand in condition.operands:
                    self._condition(operand, structure, origin, local)
            case Constant():
                pass

    def _formula(self, formula: Formula, structure: Structure, origin: Symbol, local: _Local) -> None:
        match formula:
            case PathAccess():
                self._walk(formula.path, structure, origin, local, None)
            case Negate():
                self._formula(formula.operand, structure, origin, local)
            case Binary():
                self._formula(formula.left, structure, origin, local)
                self._formula(formula.right, structure, origin, local)
            case Call():
                for argument in formula.args:
                    self._formula(argument, structure, origin, local)
            case Constant():
                pass

    def _walk(
        self, path: Path, structure: Structure, origin: Symbol, local: _Local, targets: set[Symbol] | None
    ) -> None:
        """Collects the atoms a path may read, or for a target path the slots it may write."""
        start = origin if path.origin is structure else ROOT
        local.symbols.add(atom("ex", start))
        current: list[Any] = [start]
        for number, step in enumerate(path.steps, start=1):
            final = number == len(path.steps)
            following: list[Any] = []
            for value in current:
                if isinstance(step, FeatureStep) and isinstance(value, Symbol):
                    slots = self.universe.slots_of.get((value, step.feature), ())
                    index = step.index
                    if index is not None and index.first >= 0 and index.last >= 0:
                        slots = slots[index.first : index.last + 1]
                    for slot in slots:
                        if targets is not None and final:
                            targets.add(slot)
                            local.symbols.add(atom("sx", slot))
                            continue
                        self._read(slot, local, following)
                elif isinstance(step, AttributeStep) and isinstance(value, Option):
                    attribute_value = value.values.get(step.attribute)
                    if isinstance(attribute_value, Option):
                        following.append(attribute_value)
            current = list(dict.fromkeys(following))

    def _read(self, slot: Symbol, local: _Local, following: list[Any]) -> None:
        local.symbols.add(atom("sx", slot))
        type_ = self.universe.slots[slot].feature.type
        match type_:
            case Structure():
                local.symbols.add(atom("ex", slot))
                following.append(slot)
            case Enumeration():
                for option in type_.options:
                    local.symbols.add(atom("val", slot, value_term(option)))
                    following.append(option)
            case Boolean():
                local.symbols.update((atom("val", slot, _TRUE), atom("val", slot, _FALSE)))
            case _:
                local.symbols.add(atom("defined", slot))
                local.reads.add(slot)


def _number(value: int) -> Symbol:
    return Number(value)


# Candidates


@dataclass(frozen=True, slots=True)
class Failure:
    """A reason to reject the candidate, blaming the cones of producers and slots."""

    message: str
    producers: tuple[Key, ...] = ()
    slots: tuple[Symbol, ...] = ()


@dataclass(eq=False)
class Candidate:
    """The configuration an assignment of the encoding stands for, with its computed numbers and texts."""

    configuration: Configuration
    instances: dict[Symbol, Instance]
    writers: dict[Symbol, Key | None] = field(default_factory=dict)
    failures: list[Failure] = field(default_factory=list)

    def value(self, slot: Symbol, encoding: Encoding) -> Any:
        info = encoding.universe.slots[slot]
        instance = self.instances.get(info.instance)
        return None if instance is None else instance.get(info.feature, info.index)


def assemble(
    encoding: Encoding,
    dependencies: Dependencies,
    view: View,
    given: dict[Symbol, ConstantValue],
    names: dict[Symbol, str],
    *,
    producers: Iterable[Key] | None = None,
) -> Candidate:
    """Builds the configuration of an assignment and computes the fixpoint of the producers that are on.

    The view tells which atoms are true. If producers are given, only these take part in the fixpoint, which is how
    partial assignments are evaluated within the cone of a leaf.
    """
    universe = encoding.universe
    configuration = Configuration(encoding.model)
    configuration.root.name = names.get(ROOT, configuration.root.name)
    instances = {ROOT: configuration.root}
    defaults = _default_slots(encoding, dependencies, view)
    for term, info in universe.instances.items():
        if info.parent is None or info.feature is None or not view(atom("ex", term)):
            continue
        parent = instances.get(info.parent)
        if parent is None:
            continue
        child = configuration.new(info.structure, names.get(term))
        role = Role.SELECTED if view(atom("given", term)) else Role.COMPLETION
        parent.set(info.feature, child, info.index, role=role)
        instances[term] = child
    for term, slot in universe.slots.items():
        instance = instances.get(slot.instance)
        if instance is None:
            continue
        type_ = slot.feature.type
        values: Iterable[ConstantValue]
        if isinstance(type_, Enumeration):
            values = type_.options
        elif isinstance(type_, Boolean):
            values = (True, False)
        else:
            continue
        for value in values:
            if view(atom("val", term, value_term(value))):
                if view(atom("given_val", term, value_term(value))):
                    role = Role.SELECTED
                elif term in defaults:
                    role = Role.DEFAULT
                else:
                    role = Role.COMPLETION
                instance.set(slot.feature, value, slot.index, role=role)
    candidate = Candidate(configuration, instances)
    _fixpoint(candidate, encoding, dependencies, view, given, producers)
    return candidate


def _default_slots(encoding: Encoding, dependencies: Dependencies, view: View) -> set[Symbol]:
    slots: set[Symbol] = set()
    for default in encoding.discrete_defaults:
        for origin in encoding.universe.of_structure.get(default.origin, ()):
            if view(atom("applied", _number(default.behavior), origin)):
                for slot in dependencies.default_targets[default.behavior, origin]:
                    if view(atom("tgt", _number(default.target_id), origin, slot)):
                        slots.add(slot)
    return slots


def _fixpoint(
    candidate: Candidate,
    encoding: Encoding,
    dependencies: Dependencies,
    view: View,
    given: dict[Symbol, ConstantValue],
    only: Iterable[Key] | None,
) -> None:
    universe = encoding.universe
    for slot, value in given.items():
        info = universe.slots[slot]
        instance = candidate.instances.get(info.instance)
        if instance is not None:
            instance.set(info.feature, value, info.index, role=Role.SELECTED)
            candidate.writers[slot] = None
    keys = dependencies.producers if only is None else [key for key in dependencies.producers if key in set(only)]
    on = [key for key in keys if view(atom("on", _number(key[0]), key[1]))]
    pending = [key for key in on if view(atom("valued", _number(key[0]), key[1]))]
    progress = True
    while pending and progress:
        progress = False
        waiting = []
        for key in pending:
            if any(
                view(atom("defined", slot)) and candidate.value(slot, encoding) is None
                for slot in dependencies.reads[key]
            ):
                waiting.append(key)
                continue
            if _produce(candidate, encoding, dependencies, view, key):
                progress = True
            else:
                waiting.append(key)
        pending = waiting
    for key in pending:
        candidate.failures.append(Failure("a valued producer has no value", (key,)))
    if pending:
        return
    # a producer that is on but not valued must have no value, and an active formula must not fault
    for key in on:
        if view(atom("valued", _number(key[0]), key[1])):
            continue
        origin = candidate.instances.get(key[1])
        result = None if origin is None else evaluate(encoding.producers[key[0]].formula, origin)
        if result in (Undefined.FAULT, Undefined.EXCEEDED):
            candidate.failures.append(Failure("the formula of an active producer has no value", (key,)))
        elif isinstance(result, Fraction | str):
            candidate.failures.append(Failure("a producer with a value is not valued", (key,)))
    for slot, writer in candidate.writers.items():
        info = universe.slots[slot]
        type_ = info.feature.type
        value = candidate.value(slot, encoding)
        if not isinstance(type_, Numerical) or value is None:
            continue
        if (type_.min is not None and value < type_.min) or (type_.max is not None and value > type_.max):
            blame = () if writer is None else (writer,)
            candidate.failures.append(Failure(f"{value} is outside the range of {info.feature.qualified_name}", blame))
    if only is None:
        for slot in universe.slots:
            if view(atom("defined", slot)) and slot not in candidate.writers:
                candidate.failures.append(Failure("a defined slot has no value", (), (slot,)))


def _produce(candidate: Candidate, encoding: Encoding, dependencies: Dependencies, view: View, key: Key) -> bool:
    """Writes the value of a producer into its targets, False if the value is not there yet."""
    producer: Producer = encoding.producers[key[0]]
    origin = candidate.instances.get(key[1])
    if origin is None:
        return False
    result = evaluate(producer.formula, origin)
    if result in (Undefined.FAULT, Undefined.EXCEEDED):
        candidate.failures.append(Failure(f"the formula of an {producer.kind} has no value", (key,)))
        return True
    if not isinstance(result, Fraction | str):
        return False
    role = Role.DEFAULT if producer.kind == "default" else Role.COMPLETION
    for slot in dependencies.targets[key]:
        if not view(atom("tgt", _number(producer.target_id), key[1], slot)):
            continue
        info = encoding.universe.slots[slot]
        instance = candidate.instances.get(info.instance)
        if instance is None:
            continue
        stored = _stored_form(info.feature.type, result)
        previous = instance.assignment(info.feature, info.index)
        if stored is None:
            candidate.failures.append(Failure(f"{result} does not fit {info.feature.qualified_name}", (key,)))
        elif previous is None:
            instance.set(info.feature, stored, info.index, role=role)
            candidate.writers[slot] = key
        elif previous.value != stored:
            writer = candidate.writers.get(slot)
            blame = (key,) if writer is None else (key, writer)
            candidate.failures.append(Failure(f"two values for {info.feature.qualified_name}", blame))
    return True


def _stored_form(type_: object, value: Fraction | str) -> ConstantValue | None:
    """The value as a slot of the type stores it, rounded to the grid for numbers, None if it does not fit."""
    if isinstance(type_, Numerical) and isinstance(value, Fraction):
        return to_decimal(to_grid(value, type_.digits))
    if not isinstance(type_, Numerical) and isinstance(value, str):
        return value
    return None


def outcome(leaf: Leaf, origin: Instance) -> str | None:
    """The outcome atom a leaf takes, None if it stays open."""
    return _OUTCOMES.get(truth(leaf.node, origin))


# The propagator


class Propagator(ClingoPropagator):
    """Computes numbers and texts on total assignments and decides comparisons as soon as their cone is assigned."""

    def __init__(
        self,
        encoding: Encoding,
        dependencies: Dependencies,
        given: dict[Symbol, ConstantValue],
        names: dict[Symbol, str],
    ) -> None:
        self.encoding = encoding
        self.dependencies = dependencies
        self.given = given
        self.names = names
        self._literals: dict[Symbol, int] = {}
        self._producer_cones: dict[Key, list[int]] = {}
        self._leaf_cones: dict[Key, list[int]] = {}
        self._leaf_producers: dict[Key, set[Key]] = {}
        self._watches: dict[int, list[Key]] = {}
        self._unassigned: dict[Key, int] = {}
        self.accepted: frozenset[Symbol] | None = None
        """The atoms the propagator knows of that are true in the last total assignment it accepted."""

    def init(self, init: PropagateInit) -> None:
        signatures = (
            ("ex", 1), ("sx", 1), ("val", 2), ("defined", 1), ("on", 2), ("valued", 2), ("tgt", 3), ("ready", 2),
            ("th", 3), ("blank", 1), ("applied", 2), ("given", 1), ("given_val", 2),
        )  # fmt: skip
        for name, arity in signatures:
            for symbolic in init.symbolic_atoms.by_signature(name, arity):
                # atoms that occur in no rule head have program literal 0 and are false
                if symbolic.literal != 0:
                    self._literals[symbolic.symbol] = init.solver_literal(symbolic.literal)
        for key in self.dependencies.producers:
            symbols, _ = self.dependencies.producer_cone(key)
            self._producer_cones[key] = self._lits(symbols)
        assignment = init.assignment
        for key, local in self.dependencies.leaves.items():
            symbols = {atom("ready", _number(key[0]), key[1]), *(_outcome(key, name) for name in "tfi")}
            if not any(symbol in self._literals for symbol in symbols):
                continue
            cone, producers = self.dependencies.cone(local.symbols, local.reads)
            literals = self._lits(cone | {atom("ready", _number(key[0]), key[1])})
            self._leaf_cones[key] = literals
            self._leaf_producers[key] = producers
            variables = {abs(literal) for literal in literals if assignment.value(literal) is None}
            self._unassigned[key] = len(variables)
            for variable in variables:
                if variable not in self._watches:
                    init.add_watch(variable)
                    init.add_watch(-variable)
                self._watches.setdefault(variable, []).append(key)

    def _lits(self, symbols: Iterable[Symbol]) -> list[int]:
        return sorted({literal for symbol in symbols if (literal := self._literals.get(symbol)) is not None})

    def _view(self, assignment: Assignment) -> View:
        literals = self._literals

        def view(symbol: Symbol) -> bool:
            literal = literals.get(symbol)
            return literal is not None and assignment.is_true(literal)

        return view

    def _current(self, assignment: Assignment, literals: Iterable[int]) -> list[int]:
        return [literal if assignment.is_true(literal) else -literal for literal in literals]

    def propagate(self, control: PropagateControl, changes: Sequence[int]) -> None:
        ready: list[Key] = []
        for literal in changes:
            for key in self._watches.get(abs(literal), ()):
                self._unassigned[key] -= 1
                if self._unassigned[key] == 0:
                    ready.append(key)
        if not ready:
            return
        assignment = control.assignment
        view = self._view(assignment)
        for key in ready:
            candidate = assemble(
                self.encoding, self.dependencies, view, self.given, self.names, producers=self._leaf_producers[key]
            )
            origin = candidate.instances.get(key[1])
            if candidate.failures or origin is None:
                continue
            if not self._decide(control, key, self._expected(view, key, origin)):
                return

    def undo(self, thread_id: int, assignment: Assignment, changes: Sequence[int]) -> None:
        for literal in changes:
            for key in self._watches.get(abs(literal), ()):
                self._unassigned[key] += 1

    def check(self, control: PropagateControl) -> None:
        assignment = control.assignment
        view = self._view(assignment)
        candidate = assemble(self.encoding, self.dependencies, view, self.given, self.names)
        if candidate.failures:
            for failure in candidate.failures:
                literals: set[int] = set()
                for key in failure.producers:
                    literals.update(self._producer_cones[key])
                if failure.slots:
                    symbols, producers = self.dependencies.cone((), failure.slots)
                    literals.update(self._lits(symbols))
                    for key in producers:
                        literals.update(self._producer_cones[key])
                if not control.add_nogood(self._current(assignment, literals)):
                    return
            return
        for slot in self.encoding.universe.slots:
            literal = self._literals.get(atom("blank", slot))
            if literal is None or not assignment.is_true(self._literals[atom("defined", slot)]):
                continue
            value = candidate.value(slot, self.encoding)
            if assignment.is_true(literal) != (isinstance(value, str) and not value.strip()):
                symbols, producers = self.dependencies.cone((), (slot,))
                literals = set(self._lits(symbols))
                for key in producers:
                    literals.update(self._producer_cones[key])
                wrong = literal if assignment.is_true(literal) else -literal
                if not control.add_nogood([*self._current(assignment, literals), wrong]):
                    return
        for key in self._leaf_cones:
            origin = candidate.instances.get(key[1])
            if origin is not None and not self._decide(control, key, self._expected(view, key, origin)):
                return
        # on a total assignment every nogood added above is violated, so reaching this point accepts it
        self.accepted = frozenset(symbol for symbol, literal in self._literals.items() if assignment.is_true(literal))

    def _expected(self, view: View, key: Key, origin: Instance) -> str | None:
        """The outcome atom a leaf must take, where only an indefinite outcome is known before it is ready."""
        expected = outcome(self.encoding.leaves[key[0]], origin)
        if view(atom("ready", _number(key[0]), key[1])) or expected == "i":
            return expected
        return None

    def _decide(self, control: PropagateControl, key: Key, expected: str | None) -> bool:
        """Adds the nogoods that fix the outcome atoms of a leaf, False if that fails the assignment."""
        assignment = control.assignment
        base = self._current(assignment, self._leaf_cones[key])
        for name in "tfi":
            literal = self._literals.get(_outcome(key, name))
            wanted = name == expected
            if literal is None:
                if wanted and not control.add_nogood(base):
                    return False
                continue
            if assignment.value(literal) is wanted:
                continue
            if not control.add_nogood([*base, -literal] if wanted else [*base, literal]) or not control.propagate():
                return False
        return True


def _outcome(key: Key, name: str) -> Symbol:
    return atom("th", _number(key[0]), key[1], Function(name))
