"""Visibility of the values of a configuration.

A visibility behavior applies to an instance of its origin where all its preconditions are definitely true. It then
hides or locks the slots its target path addresses, or hides some options of them. Visibility never restricts which
configurations are valid, it only says how a user interface should present them.

Several directives on one slot merge to the most restrictive one. A slot is also hidden or read only where an
instance on its way from the product is, which the effective directive accounts for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from coom.configuration._configuration import Configuration, Instance
from coom.configuration.evaluate import Sequence, Truth, access, all_of, truth
from coom.model import Directive, Feature, FeatureStep, Option, Path, Visibility

_SEVERITY = (Directive.READONLY, Directive.HIDE)


def merge(*directives: Directive | None) -> Directive | None:
    """The most restrictive of the directives, None standing for a slot without restriction."""
    present = [directive for directive in directives if directive is not None]
    return max(present, key=_SEVERITY.index, default=None)


@dataclass(frozen=True, slots=True)
class _Target:
    index: int | None
    """The slot the behavior addresses, None for every slot of the feature."""
    directive: Directive | None
    options: frozenset[Option]

    def covers(self, index: int | None) -> bool:
        return self.index is None or index is None or self.index == index


@dataclass(eq=False)
class Visibilities:
    """The directives and hidden options that the visibility behaviors of a model apply to a configuration."""

    configuration: Configuration
    _targets: dict[tuple[Instance, Feature], list[_Target]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for behavior in self.configuration.model.behaviors:
            if not isinstance(behavior, Visibility):
                continue
            for origin in self.configuration.instances(behavior.origin):
                if all_of(truth(condition, origin) for condition in behavior.conditions) == Truth.TRUE:
                    self._apply(behavior, origin)

    def directive(self, instance: Instance, feature: Feature | str, index: int | None = None) -> Directive | None:
        """The directive declared for a slot of an instance, for any slot of the feature if index is None."""
        feature = instance.type.feature(feature) if isinstance(feature, str) else feature
        return merge(*(target.directive for target in self._matching(instance, feature, index)))

    def effective(self, instance: Instance, feature: Feature | str, index: int | None = None) -> Directive | None:
        """The directive of a slot merged with those of the slots holding the instances on its way from the product."""
        result = self.directive(instance, feature, index)
        while result is not Directive.HIDE and instance.parent is not None and instance.feature is not None:
            result = merge(result, self.directive(instance.parent, instance.feature, instance.index))
            instance = instance.parent
        return result

    def hidden_options(self, instance: Instance, feature: Feature | str, index: int | None = None) -> frozenset[Option]:
        """The options hidden for a slot of an enumeration feature, for any slot if index is None."""
        feature = instance.type.feature(feature) if isinstance(feature, str) else feature
        return frozenset(option for target in self._matching(instance, feature, index) for option in target.options)

    def _matching(self, instance: Instance, feature: Feature, index: int | None) -> list[_Target]:
        return [target for target in self._targets.get((instance, feature), ()) if target.covers(index)]

    def _apply(self, behavior: Visibility, origin: Instance) -> None:
        path = behavior.target
        step = path.steps[-1]
        if not isinstance(step, FeatureStep):
            raise ValueError(f"the visibility target {path} does not end at a feature")
        if behavior.options:
            target_directive, options = None, frozenset(behavior.options)
        else:
            target_directive, options = behavior.directive, frozenset()
        for holder in _holders(path, origin):
            for index in _indices(holder, step):
                target = _Target(index, target_directive, options)
                self._targets.setdefault((holder, step.feature), []).append(target)


def _holders(path: Path, origin: Instance) -> list[Instance]:
    """The instances that hold the feature of the last step of a path."""
    parent = Path(path.origin, path.steps[:-1], rooted=path.rooted)
    result = access(parent, origin)
    match result:
        case Instance():
            return [result]
        case Sequence():
            return [value for value in result.values if isinstance(value, Instance)]
        case _:
            return []


def _indices(instance: Instance, step: FeatureStep) -> list[int | None]:
    """The slots a step addresses, a single None if it addresses every slot of its feature."""
    if step.index is None:
        return [None]
    feature = step.feature
    last = max(instance.last_index(feature), min(feature.min, feature.max or feature.min) - 1)
    first, final = (bound if bound >= 0 else last + 1 + bound for bound in (step.index.first, step.index.last))
    if feature.max is not None:
        final = min(final, feature.max - 1)
    return list(range(max(first, 0), final + 1))


def visibilities(configuration: Configuration) -> Visibilities:
    """Evaluates the visibility behaviors of the model of a configuration."""
    return Visibilities(configuration)
