"""All valid configurations of a small model by brute force, an oracle for the solver that does not use its encoding.

Discrete choices are enumerated exhaustively: which optional instances and discrete slots exist, filled from the front,
and which option or truth value each holds. Numbers and texts come from the inputs and from producers, the numeric and
text implies and the requires that equate a bare path with a formula. Where several producers write one slot, the one
whose value counts at the most digits gives the value, and the verdicts decide whether the others agree with it.
Defaults are ignored.

A candidate is valid if its values are founded and every hard behavior may still be true. Founded means that a fixpoint
reproduces them in which a producer fires only when its preconditions are definitely true both in the values derived
so far and in the candidate, and its formula already has the value it has in the candidate. While deriving, a slot the
candidate defines but the fixpoint has not reached yet is open, not absent, so a guard cannot rest on the absence of a
value that it produces itself. The candidates themselves
come from guessing the set of producers that hold a value, so several founded configurations of one discrete choice
are all found.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import chain, combinations, product
from typing import Any

from coom.configuration import Assignment, Configuration, Instance, Truth, truth, verdicts
from coom.configuration.arithmetic import to_decimal, to_grid
from coom.configuration.evaluate import Undefined, evaluate, precision
from coom.model import (
    Behavior,
    Boolean,
    Compare,
    CompareOp,
    Enumeration,
    Feature,
    FeatureStep,
    Formula,
    Imply,
    Model,
    Numerical,
    Option,
    Path,
    PathAccess,
    Require,
    Structure,
)

type Key = tuple[tuple[str, int], ...]
"""The place of an instance as the features and indices on the way from the product."""

type Slot = tuple[Key, Feature, int]
type Alternative = tuple[tuple[Feature, tuple[Any, ...]], ...]


@dataclass(frozen=True, slots=True)
class Producer:
    behavior: Behavior
    target: Path
    formula: Formula


def configurations(model: Model, inputs: Configuration | None = None) -> set[str]:
    """The canonical forms of all valid configurations that hold the inputs."""
    producers = _producers(model)
    found: set[str] = set()
    for alternative in _alternatives(model.root):
        discrete = Configuration(model)
        _build(discrete, discrete.root, alternative)
        given = _given(discrete, inputs)
        if given is None:
            continue
        origins = [
            (producer, _key(instance))
            for producer in producers
            for instance in discrete.instances(producer.behavior.origin)
        ]
        seen: set[str] = set()
        for chosen in chain.from_iterable(combinations(origins, size) for size in range(len(origins) + 1)):
            values = _values(model, alternative, given, chosen)
            if values is None:
                continue
            candidate = _candidate(model, alternative, given, values)
            form = canonical(candidate)
            if form in seen:
                continue
            seen.add(form)
            if _founded(model, alternative, given, origins, candidate) and _valid(candidate, origins):
                found.add(form)
    return found


def canonical(configuration: Configuration) -> str:
    """The JSON form without instance names, which identifies a configuration up to naming."""
    return json.dumps(_anonymous(configuration.to_json()), sort_keys=True)


def _anonymous(data: Any) -> Any:
    if isinstance(data, dict):
        return {name: _anonymous(value) for name, value in data.items() if name != "@id"}
    if isinstance(data, list):
        return [_anonymous(value) for value in data]
    return data


# Discrete choices


def _alternatives(structure: Structure) -> list[Alternative]:
    per_feature = []
    for feature in structure.features:
        type_ = feature.type
        elements: Sequence[Any]
        if isinstance(type_, Structure):
            elements = _alternatives(type_)
        elif isinstance(type_, Enumeration):
            elements = type_.options
        elif isinstance(type_, Boolean):
            elements = (True, False)
        else:
            continue
        assert feature.max is not None
        sequences = [seq for count in range(feature.min, feature.max + 1) for seq in product(elements, repeat=count)]
        per_feature.append([(feature, sequence) for sequence in sequences])
    return [tuple(combination) for combination in product(*per_feature)]


def _build(configuration: Configuration, instance: Instance, alternative: Alternative) -> None:
    for feature, sequence in alternative:
        for index, element in enumerate(sequence):
            if isinstance(feature.type, Structure):
                child = configuration.new(feature.type)
                instance.set(feature, child, index)
                _build(configuration, child, element)
            else:
                instance.set(feature, element, index)


def _key(instance: Instance) -> Key:
    steps: list[tuple[str, int]] = []
    while instance.parent is not None and instance.feature is not None:
        steps.append((instance.feature.name, instance.index))
        instance = instance.parent
    return tuple(reversed(steps))


def _at(configuration: Configuration, key: Key) -> Instance | None:
    instance: Instance = configuration.root
    for name, index in key:
        child = instance.get(name, index)
        if not isinstance(child, Instance):
            return None
        instance = child
    return instance


def _given(discrete: Configuration, inputs: Configuration | None) -> dict[Slot, Any] | None:
    """The numbers and texts of the inputs, None if the discrete choice contradicts the inputs."""
    given: dict[Slot, Any] = {}
    if inputs is None:
        return given
    for instance in inputs.instances():
        key = _key(instance)
        target = _at(discrete, key)
        if target is None:
            return None
        for feature in instance.type.features:
            for index, assignment in instance.assignments(feature).items():
                value = assignment.value
                if isinstance(value, Instance):
                    continue
                if isinstance(feature.type, Enumeration | Boolean):
                    if target.get(feature.name, index) != value:
                        return None
                else:
                    given[key, feature, index] = value
    return given


# Numbers and texts


def _producers(model: Model) -> list[Producer]:
    producers = []
    for behavior in model.behaviors:
        if isinstance(behavior, Imply) and _is_value(behavior.target.type):
            producers.append(Producer(behavior, behavior.target, behavior.value))
        elif isinstance(behavior, Require):
            condition = behavior.condition
            if isinstance(condition, Compare) and condition.op is CompareOp.EQ:
                for bare, other in ((condition.left, condition.right), (condition.right, condition.left)):
                    if isinstance(bare, PathAccess) and not bare.path.is_range and _is_value(bare.path.type):
                        producers.append(Producer(behavior, bare.path, other))
    return list(dict.fromkeys(producers))


def _is_value(type_: object) -> bool:
    return not isinstance(type_, Structure | Enumeration | Boolean)


def _candidate(
    model: Model, alternative: Alternative, given: dict[Slot, Any], values: dict[Slot, Any]
) -> Configuration:
    configuration = Configuration(model)
    _build(configuration, configuration.root, alternative)
    for (key, feature, index), value in chain(given.items(), values.items()):
        instance = _at(configuration, key)
        assert instance is not None
        instance.set(feature, value, index)
    return configuration


def _target(producer: Producer, origin: Instance) -> Slot | None:
    path = producer.target
    instance = origin if path.origin is origin.type else origin.root
    for step in path.steps[:-1]:
        assert isinstance(step, FeatureStep)
        child = instance.get(step.feature, 0 if step.index is None else step.index.first)
        if not isinstance(child, Instance):
            return None
        instance = child
    last = path.steps[-1]
    assert isinstance(last, FeatureStep)
    return _key(instance), last.feature, 0 if last.index is None else last.index.first


def _stored(feature: Feature, value: object) -> object | None:
    if isinstance(feature.type, Numerical) and isinstance(value, Fraction):
        return to_decimal(to_grid(value, feature.type.digits))
    if not isinstance(feature.type, Numerical) and isinstance(value, str):
        return value
    return None


def _values(
    model: Model, alternative: Alternative, given: dict[Slot, Any], chosen: Sequence[tuple[Producer, Key]]
) -> dict[Slot, Any] | None:
    """The values the chosen producers write, all of them holding a value, None if they do not.

    An input keeps its slot. Otherwise the most precise producer of a slot gives its value.
    """
    values: dict[Slot, Any] = {}
    for _ in range(len(chosen) + 2):
        configuration = _candidate(model, alternative, given, values)
        following: dict[Slot, Any] = {}
        digits: dict[Slot, int] = {}
        for producer, key in chosen:
            origin = _at(configuration, key)
            assert origin is not None
            slot = _target(producer, origin)
            if slot is None:
                return None
            stored = _stored(slot[1], evaluate(producer.formula, origin))
            if stored is None or slot in given:
                continue
            if slot not in following or _digits(producer) > digits[slot]:
                following[slot] = stored
                digits[slot] = _digits(producer)
        if following == values:
            break
        values = following
    else:
        return None
    configuration = _candidate(model, alternative, given, values)
    for producer, key in chosen:
        origin = _at(configuration, key)
        assert origin is not None
        if _stored(_feature(producer), evaluate(producer.formula, origin)) is None:
            return None
    return {slot: value for slot, value in values.items() if slot not in given}


def _digits(producer: Producer) -> int:
    """The digits at which the value of a producer counts, the fewer of its formula and its target."""
    type_ = _feature(producer).type
    target = type_.digits if isinstance(type_, Numerical) else 0
    own = precision(producer.formula)
    return target if own is None else min(own, target)


def _feature(producer: Producer) -> Feature:
    last = producer.target.steps[-1]
    assert isinstance(last, FeatureStep)
    return last.feature


def _definitely(behavior: Behavior, instance: Instance) -> bool:
    result = Truth.TRUE
    for condition in behavior.conditions:
        result = result.both(truth(condition, instance))
    return result == Truth.TRUE


def _numbers(configuration: Configuration) -> dict[Slot, Any]:
    result: dict[Slot, Any] = {}
    for instance in configuration.instances():
        for feature in instance.type.features:
            if _is_value(feature.type):
                for index, assignment in instance.assignments(feature).items():
                    result[_key(instance), feature, index] = assignment.value
    return result


def _mark_open(configuration: Configuration, slots: Iterable[Slot]) -> None:
    """Marks slots as open, defined in the candidate but without a value derived so far.

    The configuration offers no open state for an optional slot, absent being the only alternative to a value. An
    undefined result in its place makes the evaluation treat the slot as open, so a guard cannot be definitely true for
    the absence of a value the candidate holds.
    """
    for key, feature, index in slots:
        instance = _at(configuration, key)
        assert instance is not None
        instance._slots.setdefault(feature, {})[index] = Assignment(Undefined.OPEN)  # type: ignore[arg-type]


def _founded(
    model: Model,
    alternative: Alternative,
    given: dict[Slot, Any],
    origins: list[tuple[Producer, Key]],
    candidate: Configuration,
) -> bool:
    derived: dict[Slot, Any] = dict(given)
    final_numbers = _numbers(candidate)
    fired: set[tuple[Producer, Key]] = set()
    changed = True
    while changed:
        changed = False
        current = _candidate(model, alternative, {}, derived)
        _mark_open(current, (slot for slot in _numbers(candidate) if slot not in derived))
        for item in origins:
            if item in fired:
                continue
            producer, key = item
            origin, final = _at(current, key), _at(candidate, key)
            assert origin is not None and final is not None
            if not (_definitely(producer.behavior, origin) and _definitely(producer.behavior, final)):
                continue
            value = evaluate(producer.formula, origin)
            if not isinstance(value, Fraction | str) or value != evaluate(producer.formula, final):
                continue
            slot = _target(producer, origin)
            if slot is None:
                continue
            stored = _stored(slot[1], value)
            if stored is None or slot not in final_numbers:
                return False
            # a producer that only agrees with the value of its slot at a lower precision does not derive it
            if stored == final_numbers[slot]:
                derived[slot] = stored
            fired.add(item)
            changed = True
    return derived == final_numbers


def _valid(candidate: Configuration, origins: list[tuple[Producer, Key]]) -> bool:
    for verdict in verdicts(candidate):
        if verdict.is_hard and not verdict.truth.may_be_true:
            return False
    for behavior in candidate.model.behaviors:
        if isinstance(behavior, Imply) and not _is_value(behavior.target.type):
            for instance in candidate.instances(behavior.origin):
                if not _imply_holds(behavior, instance):
                    return False
    for producer, key in origins:
        origin = _at(candidate, key)
        assert origin is not None
        faulty = evaluate(producer.formula, origin) in (Undefined.FAULT, Undefined.EXCEEDED)
        if faulty and _definitely(producer.behavior, origin):
            return False
    for (_, feature, _), value in _numbers(candidate).items():
        type_ = feature.type
        if not isinstance(type_, Numerical) or not isinstance(value, Decimal):
            continue
        if (type_.min is not None and value < type_.min) or (type_.max is not None and value > type_.max):
            return False
    return True


def _imply_holds(behavior: Imply, instance: Instance) -> bool:
    """A discrete imply whose preconditions are definitely true creates its target and holds its value."""
    if not _definitely(behavior, instance):
        return True
    expected = evaluate(behavior.value, instance)
    if not isinstance(expected, Option | bool | Instance):
        return True
    producer = Producer(behavior, behavior.target, behavior.value)
    slot = _target(producer, instance)
    if slot is None:
        return True
    owner = _at(instance.configuration, slot[0])
    return owner is not None and owner.get(slot[1], slot[2]) == expected
