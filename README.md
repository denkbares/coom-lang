# COOM

COOM (COnfiguration Object Model) is a domain-specific language for product configuration knowledge bases. A
knowledge base describes a product as a hierarchy of structures and features and adds behavioral knowledge such as
constraints, defaults and calculations over them.

This repository is the home of the language definition and of its Python reference implementation.

- Language documentation: https://www.coom-lang.org
- Specification artifacts: [spec/](spec/) (grammar, conformance suite, schemas)
- Reference implementation: Python packages sharing the namespace `coom`, sources in [packages/](packages/)
- Changes to the language: [CHANGELOG.md](CHANGELOG.md)

## Status

Work in progress towards COOM 1.0. Nothing in this repository is released yet.

## Layout

```
spec/grammar/        ANTLR 4 grammar of the language
spec/conformance/    conformance suite, one folder per profile or module
spec/schema/         JSON schemas (configuration, conformance results)
packages/            Python reference implementation, one folder per package with its sources and tests
scripts/             grammar build and maintenance scripts
```

## Implementations

- Reference implementation in this repository (Python, clingo based solver).
- [COOM Suite](https://github.com/potassco/coom-suite) by Potassco, an independent Python and ASP implementation.
- The commercial denkbares platform, see https://www.denkbares.com.

## Installing the reference implementation

Not yet published. Once released:

```
pip install coom-api           # everything below in matching versions, imported from coom.api
```

| package | modules | contents | dependencies |
|---|---|---|---|
| `coom-core` | `coom.model`, `coom.configuration`, `coom.check`, `coom.diagnostics` | model, configurations, exact evaluation, static checks | none |
| `coom-lang` | `coom.parser`, `coom.compiler`, `coom.writer` | parser, compiler and writer of the COOM text syntax | coom-core, ANTLR runtime |
| `coom-clingo` | `coom.clingo` | reference solver | coom-core, clingo |
| `coom-api` | `coom.api` | all of the above with their main entry points in one module | the three above |

The packages are developed in this repository as one uv workspace, `uv sync` installs all of them for development.
They are released together with the same version and pin each other exactly. The namespace `coom` is reserved for
packages from this repository.

## License

Grammar, conformance suite, schemas and source code are licensed under the MIT License, see [LICENSE](LICENSE).
The language documentation at https://www.coom-lang.org is licensed under CC BY-ND 4.0.
Implementing the COOM language does not require a license.

## People

COOM was created by [denkbares GmbH](https://www.denkbares.com). Language development is supported by the Knowledge
Processing and Information Systems group at the University of Potsdam and by Potassco Solutions GmbH.
