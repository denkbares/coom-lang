# coom-cli

The `coom` command for models of the [COOM](https://www.coom-lang.org) product configuration language.

```
pip install coom-cli
coom check Bike.model
```

`coom check` compiles the given files as one model and reports every diagnostic with its source position. It exits
with status 1 if there are errors. More commands follow. Sources live in the
[coom-lang repository](https://github.com/denkbares/coom-lang) under `packages/coom-cli`.
