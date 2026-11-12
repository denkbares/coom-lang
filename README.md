# COOM

COOM (COnfiguration Object Model) is a domain-specific language for product configuration knowledge bases. A
knowledge base describes a product as a hierarchy of structures and features and adds behavioral knowledge such as
constraints, defaults and calculations over them.

This repository is the home of the language definition and of its Python reference implementation.

- Language documentation: https://www.coom-lang.org
- Specification artifacts: [spec/](spec/) (grammar, conformance suite, schemas)
- Reference implementation: Python package `coom-lang` (import name `coom`), sources in [src/coom](src/coom)
- Changes to the language: [CHANGELOG.md](CHANGELOG.md)

## Status

Work in progress towards COOM 1.0. Nothing in this repository is released yet.

## Layout

```
spec/grammar/        ANTLR 4 grammar of the language
spec/conformance/    conformance suite, one folder per profile or module
spec/schema/         JSON schemas (configuration, conformance results)
src/coom/            Python reference implementation: parser, compiler, model, evaluator, ASP solver
tests/               unit and conformance tests of the reference implementation
scripts/             grammar build and maintenance scripts
```

## Implementations

- Reference implementation in this repository (Python, clingo based solver).
- [COOM Suite](https://github.com/potassco/coom-suite) by Potassco, an independent Python and ASP implementation.
- The commercial denkbares platform, see https://www.denkbares.com.

## Installing the reference implementation

Not yet published. Once released:

```
pip install coom-lang          # parser, compiler, model, evaluator
pip install coom-lang[asp]     # plus the clingo based reference solver
```

## License

Grammar, conformance suite, schemas and source code are licensed under the MIT License, see [LICENSE](LICENSE).
The language documentation at https://www.coom-lang.org is licensed under CC BY-ND 4.0.
Implementing the COOM language does not require a license.

## People

COOM was created by [denkbares GmbH](https://www.denkbares.com). Language development is supported by the Knowledge
Processing and Information Systems group at the University of Potsdam and by Potassco Solutions GmbH.
