# coom-api

The [COOM](https://www.coom-lang.org) product configuration language with its reference implementation in one
package. It installs `coom-core`, `coom-lang`, `coom-clingo`, `coom-cli` and `coom-mcp` in matching versions and
re-exports their main entry points from `coom.api`.

```
pip install coom-api
```

```python
from coom.api import ClingoSolver, compile_files

model = compile_files(["Bike.model"]).model
configuration = ClingoSolver(model).solve()
```

Sources live in the [coom-api repository](https://github.com/denkbares/coom-api) under `packages/coom-api`.
