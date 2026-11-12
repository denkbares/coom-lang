# coom-api

The [COOM](https://www.coom-lang.org) product configuration language with its reference implementation in one
package. It installs `coom-core`, `coom-lang`, `coom-clingo` and `coom-cli` in matching versions and re-exports their
main entry points from `coom.api`. The extra `coom-api[mcp]` adds the MCP server.

```
pip install coom-api
```

```python
from coom.api import ClingoSolver, compile_files

model = compile_files(["Bike.model"]).model
configuration = ClingoSolver(model).solve()
```

Sources live in the [coom-lang repository](https://github.com/denkbares/coom-lang) under `packages/coom-api`.
