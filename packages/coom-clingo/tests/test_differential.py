"""The solver against the brute force oracle on random small models.

Soundness and completeness are checked together: the configurations the solver enumerates must be exactly those the
oracle finds, and every configuration the solver completes with defaults must pass the evaluation oracle.
"""

import pytest
from brute_force import canonical, configurations
from model_generator import case

from coom.clingo.solver import ClingoSolver
from coom.configuration import verdicts

SEEDS = range(200)


@pytest.mark.parametrize("seed", SEEDS)
def test_solver_finds_exactly_the_valid_configurations(seed: int) -> None:
    example = case(seed)
    solver = ClingoSolver(example.model)
    found = [canonical(configuration) for configuration in solver.enumerate(example.inputs)]
    expected = configurations(example.model, example.inputs)
    inputs = None if example.inputs is None else example.inputs.dumps(indent=None)
    context = f"seed {seed}\ninputs {inputs}\n{example.text}"
    assert len(found) == len(set(found)), f"duplicate configurations\n{context}"
    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)
    assert not missing and not extra, f"missing {missing}\nextra {extra}\n{context}"


@pytest.mark.parametrize("seed", SEEDS)
def test_solved_configurations_pass_the_oracle(seed: int) -> None:
    example = case(seed)
    solved = ClingoSolver(example.model).solve(example.inputs)
    if solved is None:
        return
    broken = [verdict for verdict in verdicts(solved) if verdict.is_hard and not verdict.truth.may_be_true]
    assert not broken, f"seed {seed}\n{example.text}\n{broken}"
