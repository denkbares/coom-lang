# coom-core

The model of the [COOM](https://www.coom-lang.org) product configuration language and the configurations of a model.

- `coom.model` holds structures, enumerations, behaviors and tests as a navigable graph
- `coom.configuration` holds configurations and decides the truth of every behavior in them with exact arithmetic
- `coom.check` holds the static checks and the detection of language profiles
- `coom.diagnostics` holds the messages all packages report

The package has no dependencies. To read models from COOM source text install `coom-lang`, for everything at once
install `coom-api`. Sources live in the [coom-lang repository](https://github.com/denkbares/coom-lang) under
`packages/coom-core`.
