# coom-clingo

The reference solver of the [COOM](https://www.coom-lang.org) product configuration language, built on
[clingo](https://potassco.org/clingo/).

```python
from coom.clingo.solver import ClingoSolver
from coom.compiler import compile_files

model = compile_files(["Bike.model"]).model
configuration = ClingoSolver(model).solve()
```

The solver works on the model of `coom-core`. Reading models from COOM source text needs `coom-lang` as well, which
`coom-api` installs together with this package. Sources live in the
[coom-api repository](https://github.com/denkbares/coom-api) under `packages/coom-clingo`.

## Purpose

This solver is a semantic reference. It exists to show what the language means and to decide conformance questions,
so it favours a readable encoding and exact arithmetic over speed. It is not optimized for performance and not meant
for productive use. Every operation grounds the whole model again, all potential instances are unrolled up front, and
numbers are computed in Python on every candidate the search proposes. Models with many instances or deep cardinality
nesting will be slow.

## Operations

| method | result |
|---|---|
| `solve` | one completion of the inputs with defaults applied, or None if there is none |
| `satisfiable` | whether the inputs have a completion, ignoring defaults |
| `enumerate` | all completions of the inputs, ignoring defaults |
| `feasible` | the options or truth values some completion holds in a slot |

In a solved configuration, values held in every completion of the inputs take the role consequence unless they are
selected. `coom.clingo.testrun` runs the `test` blocks of a model against these operations.

## Limitations

The solver aims to implement the language specification faithfully, but it does not cover all of it yet. The points
below are known gaps, and anything not listed that disagrees with the specification is a bug.

Rejected with a diagnostic

- Unbounded cardinalities (`*`).
- Implications and defaults that assign instances, and discrete ones whose value is not an option, a truth value or a
  path.
- Writing numeric or text slots addressed from the end (`last`).

Ignored with a warning

- `minimize` and `maximize`.

Not supported by the operations or the test runner

- Optimization and explanations of conflicts.
- Tests of structures other than the product.

Semantic differences to the language specification

- Defaults are applied greedily. A domain heuristic decides higher priorities first and the first model found is
  returned. The specification asks for a maximal application of defaults under their priorities, which this
  approximates but does not guarantee. The result can depend on the search order, and equal priority defaults with
  different values are not reported as a tie. Applying a default may also force its condition to hold.
- A numeric value is only ever produced by an input, an implication, an applied default or an equality in a
  requirement with a bare path on one side. The solver never searches for numbers, so a requirement such as
  `x * x = 4` leaves `x` open.
- Only `solve` applies defaults. If a slot can only get its value from a default, `solve` may find a configuration
  where `satisfiable`, `enumerate` and `feasible` find none.
- Where several statements write one numeric slot, the one whose value counts at the most digits gives the value.
  The others only have to agree with it at the lowest precision of both sides, as an input does.
- A computed number or text is a consequence only if some producer of it writes it in every completion from values
  that are the same in every completion. Different producers that compute the same value in different completions do
  not make it a consequence.

## Open points

- The exact meaning of maximal default application, in particular whether a default may force its own condition.
  Defaults stay greedy until this is defined.
- Whether a condition may hold through the absence of a value it produces. The solver says no, so with
  `condition z || !z imply y = 3` and `imply z = y` there is no configuration.
- Unbounded cardinalities through incremental grounding.
- Optimization statements and explanations.
