"""Static checks of a compiled model and detection of the profiles it uses.

The checks decide whether a model is valid regardless of any configuration. They cover the typing of formulas,
comparisons, assignments, table cells and test steps, values outside declared ranges, empty index ranges and
structures that contain themselves.
"""

from coom.check._profiles import Profile, detect_profiles
from coom.check._structure import check_structure
from coom.check._typing import check_types
from coom.diagnostics import Diagnostic
from coom.model import Model

__all__ = ["Profile", "check", "detect_profiles"]


def check(model: Model) -> tuple[Diagnostic, ...]:
    return (*check_structure(model), *check_types(model))
