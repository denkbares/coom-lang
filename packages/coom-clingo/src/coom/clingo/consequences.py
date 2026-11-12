"""Consequences, the values a configuration holds in every completion of its inputs.

Instances, options and truth values are consequences when their atom is among the cautious consequences. Numbers and
texts are not atoms, so a computed value counts as a consequence by the dependency rule instead. Some producer of it
is valued and writes the slot in every model, and everything that producer reads is the same in every model. This is
sound and misses only values that different producers compute alike in different completions.
"""

from __future__ import annotations

from collections.abc import Set

from clingo import Number, Symbol
from coom.clingo.facts import ROOT, Encoding, value_term
from coom.clingo.numeric import Dependencies, Key, atom
from coom.configuration import Configuration, Instance, Role
from coom.model import Boolean, ConstantValue, Enumeration, Feature, Option, Structure


def apply(
    configuration: Configuration,
    encoding: Encoding,
    dependencies: Dependencies,
    first: Set[Symbol],
    cautious: Set[Symbol],
) -> None:
    """Raises the role of every value of the configuration that is a consequence to consequence.

    The configuration is the one of the first model, given by its atoms, and cautious are the atoms true in every model
    among exists, value, absent, undefined, on and applied. Selected values keep their role.
    """
    instances = _instances(configuration, encoding)
    selected = set()
    for term, slot in encoding.universe.slots.items():
        instance = instances.get(slot.instance)
        assignment = None if instance is None else instance.assignment(slot.feature, slot.index)
        if assignment is not None and assignment.role is Role.SELECTED:
            selected.add(term)
    fixed = _Fixed(encoding, dependencies, first, cautious, selected)
    for term, slot in encoding.universe.slots.items():
        instance = instances.get(slot.instance)
        if instance is None or term in selected:
            continue
        type_ = slot.feature.type
        if isinstance(type_, Structure):
            consequence = atom("exists", term) in cautious
        elif isinstance(type_, Enumeration | Boolean):
            value = instance.get(slot.feature, slot.index)
            consequence = isinstance(value, Option | bool) and _value_atom(term, value) in cautious
        else:
            consequence = fixed.value(term)
        if consequence:
            _promote(instance, slot.feature, slot.index)


def _value_atom(term: Symbol, value: ConstantValue) -> Symbol:
    return atom("value", term, value_term(value))


def _instances(configuration: Configuration, encoding: Encoding) -> dict[Symbol, Instance]:
    """The instances of the configuration by the terms of the potential instances they stand for."""
    result = {ROOT: configuration.root}
    for term, info in encoding.universe.instances.items():
        if info.parent is None or info.feature is None:
            continue
        parent = result.get(info.parent)
        child = None if parent is None else parent.get(info.feature, info.index)
        if isinstance(child, Instance):
            result[term] = child
    return result


def _promote(instance: Instance, feature: Feature, index: int) -> None:
    assignment = instance.assignment(feature, index)
    if assignment is None or assignment.role in (Role.SELECTED, Role.CONSEQUENCE):
        return
    # an instance can only be assigned once it is detached from its old slot
    instance.remove(feature, index)
    instance.set(feature, assignment.value, index, role=Role.CONSEQUENCE)


class _Fixed:
    """Decides which atoms and numeric values are the same in every model."""

    def __init__(
        self,
        encoding: Encoding,
        dependencies: Dependencies,
        first: Set[Symbol],
        cautious: Set[Symbol],
        selected: Set[Symbol],
    ) -> None:
        self.encoding = encoding
        self.dependencies = dependencies
        self.first = first
        self.cautious = cautious
        self.selected = selected
        self._values: dict[Symbol, bool] = {}
        self._writers: dict[Symbol, list[Key]] = {}
        for key in dependencies.producers:
            for slot in dependencies.targets[key]:
                self._writers.setdefault(slot, []).append(key)

    def value(self, slot: Symbol) -> bool:
        """Whether a numeric or text slot holds the same value in every model, cycles counting as not fixed."""
        if slot in self.selected:
            return True
        known = self._values.get(slot)
        if known is not None:
            return known
        self._values[slot] = False
        result = any(self._producer(key, slot) for key in self._writers.get(slot, ()))
        self._values[slot] = result
        return result

    def _producer(self, key: Key, slot: Symbol) -> bool:
        """Whether a producer writes the same value into the slot in every model."""
        producer = self.encoding.producers[key[0]]
        origin = key[1]
        if atom("on", Number(producer.id), origin) not in self.cautious:
            return False
        # whether an active producer has a value and which slots it writes follows from what it reads, so both are
        # the same in every model once everything it reads is
        if atom("valued", Number(producer.id), origin) not in self.first:
            return False
        if atom("target", Number(producer.target_id), origin, slot) not in self.first:
            return False
        if not all(self.atom(symbol) for symbol in self.dependencies.direct(key)):
            return False
        return all(
            self.value(read) or atom("undefined", read) in self.cautious for read in self.dependencies.reads[key]
        )

    def atom(self, symbol: Symbol) -> bool:
        """Whether an atom read by a producer has the same truth value in every model."""
        name, arguments = symbol.name, symbol.arguments
        match name:
            case "exists":
                slot = arguments[0]
                if slot == ROOT:
                    return True
                return symbol in self.cautious or atom("absent", slot) in self.cautious
            case "value":
                # an option is false in every model if the slot is absent or holds another value in every model
                slot = arguments[0]
                if symbol in self.cautious or atom("absent", slot) in self.cautious:
                    return True
                return symbol not in self.first and any(
                    _value_atom(slot, value) in self.cautious for value in self._values_of(slot)
                )
            case _:
                # definedness of read slots is decided by value, the producer's own atoms and targets above
                return True

    def _values_of(self, slot: Symbol) -> tuple[ConstantValue, ...]:
        type_ = self.encoding.universe.slots[slot].feature.type
        if isinstance(type_, Enumeration):
            return type_.options
        if isinstance(type_, Boolean):
            return (True, False)
        return ()
