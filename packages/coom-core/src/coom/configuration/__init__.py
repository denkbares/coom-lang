"""Configurations of a model and their evaluation.

A configuration is a tree of instances below the instance of the product. Every feature of an instance has numbered
slots from 0 up to the maximum cardinality, and each slot is empty or holds an assignment, a value together with the
role that says why it is there. A structure feature holds instances, which then belong to that slot. Numbers are
stored as decimals on the grid of their feature, rounded half away from zero when they are assigned. Options, truth
values and texts are stored as the Option, bool and str objects of the model.

The evaluate module decides the truth of conditions and behaviors in a configuration, and the arithmetic module
defines the exact calculation both rely on. The visibility module says which values a user interface hides or locks.
Their main entry points are re-exported here.
"""

from coom.configuration._configuration import Assignment, Configuration, Instance, Role, Value
from coom.configuration.evaluate import Truth, Verdict, truth, verdicts
from coom.configuration.visibility import Visibilities, visibilities

__all__ = [
    "Assignment",
    "Configuration",
    "Instance",
    "Role",
    "Truth",
    "Value",
    "Verdict",
    "Visibilities",
    "truth",
    "verdicts",
    "visibilities",
]
