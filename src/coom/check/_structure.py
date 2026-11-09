"""Checks of the product hierarchy."""

from collections.abc import Iterator

from coom.diagnostics import Diagnostic, Severity
from coom.model import Feature, Model, Structure


def check_structure(model: Model) -> Iterator[Diagnostic]:
    """Reports every structure that contains itself, which would require infinitely many instances to configure."""
    reported: set[Structure] = set()
    for structure in model.structures:
        cycle = _cycle(structure, structure, [])
        if cycle is None or structure in reported:
            continue
        reported.update(feature.owner for feature in cycle)
        through = " > ".join(feature.qualified_name for feature in cycle)
        yield Diagnostic(
            Severity.ERROR, f"the structure {structure.name} contains itself through {through}", cycle[0].span
        )


def _cycle(start: Structure, current: Structure, trail: list[Feature]) -> list[Feature] | None:
    """Returns the features that lead from the current structure back to the start, depth first."""
    for feature in current.features:
        if not isinstance(feature.type, Structure) or feature in trail:
            continue
        if feature.type is start:
            return [*trail, feature]
        if any(step.owner is feature.type for step in trail):
            continue
        found = _cycle(start, feature.type, [*trail, feature])
        if found is not None:
            return found
    return None
