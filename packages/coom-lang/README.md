# coom-lang

Parser, compiler and writer of the [COOM](https://www.coom-lang.org) product configuration language.

```python
from coom.compiler import compile_files

result = compile_files(["Bike.model"])
for diagnostic in result.diagnostics:
    print(diagnostic)
model = result.model
```

The compiled model is the one of `coom-core`. Sources live in the
[coom-lang repository](https://github.com/denkbares/coom-lang) under `packages/coom-lang`.
