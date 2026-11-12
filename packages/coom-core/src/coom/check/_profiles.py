"""Detection of the language profiles and modules a model uses."""

from enum import StrEnum

from coom.check._typing import AGGREGATES, formula_type, formulas
from coom.model import (
    Behavior,
    Binary,
    BinaryOp,
    Call,
    Combinations,
    Compare,
    Default,
    Feature,
    FeatureStep,
    Formula,
    IsDefined,
    Model,
    Numerical,
    Optimize,
    PathAccess,
    Require,
    Visibility,
    parts,
    walk,
)


class Profile(StrEnum):
    """A profile or module of the language, CORE being the one every model uses."""

    CORE = "CORE"
    N_OUT = "N-OUT"
    N_LIN = "N-LIN"
    N_FULL = "N-FULL"
    C_FIX = "C-FIX"
    C_USER = "C-USER"
    C_OPEN = "C-OPEN"
    D_BASE = "D-BASE"
    D_COND = "D-COND"
    OPTIMIZE = "O"
    UI = "UI"
    TEST = "TEST"


def detect_profiles(model: Model) -> tuple[Profile, ...]:
    """Returns the smallest profile of each family that covers the model, in the order of the enumeration.

    Numbers. N-OUT if no condition, constraint or table reads a number, so calculations stay outside the solution
    space. Otherwise N-LIN if all arithmetic is linear, that is sums, differences, products and quotients with a
    constant factor or divisor, and the aggregates. Otherwise N-FULL.

    Cardinalities. C-FIX if every cardinality is fixed. C-OPEN if a cardinality is unbounded or a behavior aggregates
    over or ranges across a feature whose number of instances varies, since then the reasoner decides that number.
    Otherwise C-USER, where the user decides it.

    Defaults. D-BASE if no default has a condition or an explicit priority, otherwise D-COND.
    """
    profiles = [Profile.CORE]
    numbers = _numbers(model)
    if numbers is not None:
        profiles.append(numbers)
    cardinalities = _cardinalities(model)
    if cardinalities is not None:
        profiles.append(cardinalities)
    defaults = [behavior for behavior in model.behaviors if isinstance(behavior, Default)]
    if defaults:
        conditioned = any(default.conditions or default.priority is not None for default in defaults)
        profiles.append(Profile.D_COND if conditioned else Profile.D_BASE)
    if any(isinstance(behavior, Optimize) for behavior in model.behaviors):
        profiles.append(Profile.OPTIMIZE)
    if any(isinstance(behavior, Visibility) for behavior in model.behaviors):
        profiles.append(Profile.UI)
    if model.tests:
        profiles.append(Profile.TEST)
    return tuple(profiles)


def _numbers(model: Model) -> Profile | None:
    declared = any(isinstance(feature.type, Numerical) for feature in model.features()) or any(
        isinstance(attribute.type, Numerical)
        for enumeration in model.enumerations
        for attribute in enumeration.attributes
    )
    if not declared:
        return None
    if not any(_reads_number(behavior) for behavior in model.behaviors):
        return Profile.N_OUT
    linear = all(_linear(formula) for behavior in model.behaviors for formula in formulas(behavior))
    return Profile.N_LIN if linear else Profile.N_FULL


def _reads_number(behavior: Behavior) -> bool:
    """Whether a condition, constraint or table of the behavior depends on a numeric value."""
    conditions = (*behavior.conditions, behavior.condition) if isinstance(behavior, Require) else behavior.conditions
    tested: list[Formula] = list(behavior.columns) if isinstance(behavior, Combinations) else []
    for node in walk(*conditions):
        if isinstance(node, Compare):
            tested += [node.left, node.right]
        elif isinstance(node, IsDefined):
            tested.append(node.formula)
    return any(_is_number(formula) for formula in tested)


def _is_number(formula: Formula) -> bool:
    typed = formula_type(formula)
    return typed is not None and isinstance(typed.base, Numerical)


def _constant(formula: Formula) -> bool:
    return not any(isinstance(node, PathAccess) for node in walk(formula))


def _linear(formula: Formula) -> bool:
    match formula:
        case Binary(op=BinaryOp.MUL):
            return _constant(formula.left) or _constant(formula.right)
        case Binary(op=BinaryOp.DIV):
            return _constant(formula.right)
        case Binary(op=BinaryOp.POW):
            return _constant(formula)
        case Call():
            return formula.function in AGGREGATES or _constant(formula)
        case _:
            return True


def _cardinalities(model: Model) -> Profile | None:
    varying = [feature for feature in model.features() if (feature.min, feature.max) != (1, 1)]
    if not varying:
        return None
    if all(feature.min == feature.max for feature in varying):
        return Profile.C_FIX
    if any(feature.max is None for feature in varying):
        return Profile.C_OPEN
    ranged = {feature for feature in varying if feature.min != feature.max}
    for behavior in model.behaviors:
        for node in walk(*parts(behavior)):
            if isinstance(node, Call) and node.function in AGGREGATES:
                for argument in walk(*node.args):
                    if isinstance(argument, PathAccess) and _ranges_over(argument, ranged):
                        return Profile.C_OPEN
    return Profile.C_USER


def _ranges_over(access: PathAccess, ranged: set[Feature]) -> bool:
    return any(isinstance(step, FeatureStep) and step.feature in ranged and step.is_range for step in access.path.steps)
