"""Compiles parse trees into a model and reports the errors it finds with their source positions.

The compiler resolves names and builds the model graph, then runs the static checks of coom.check on it. It continues
after errors, leaving out the statements that contain them, so tools still get a model.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from coom.check import check
from coom.compiler._behaviors import compile_behaviors
from coom.compiler._context import Compilation
from coom.compiler._declarations import assign_attribute_values, declare_fields, declare_types
from coom.compiler._testing import compile_tests
from coom.diagnostics import Diagnostic, Severity
from coom.model import Model
from coom.parser import ParseResult, parse, parse_file

__all__ = ["CompileResult", "compile", "compile_files", "compile_text"]

# Each phase runs over all sources before the next one starts, so declarations may refer to any type in any source.
_PHASES = (declare_types, declare_fields, assign_attribute_values, compile_behaviors, compile_tests)


@dataclass(frozen=True, slots=True)
class CompileResult:
    model: Model
    diagnostics: tuple[Diagnostic, ...]
    """The syntax errors of all sources, then the errors of compilation, then those of the static checks."""

    @property
    def ok(self) -> bool:
        return not any(diagnostic.severity is Severity.ERROR for diagnostic in self.diagnostics)


def compile(*sources: ParseResult, checks: bool = True) -> CompileResult:
    """Compiles the parse results of one or more sources that together form one model."""
    compilation = Compilation()
    for phase in _PHASES:
        for source in sources:
            compilation.source = source.source
            phase(compilation, source.tree)
    model = Model(
        root=compilation.root,
        structures=tuple(compilation.structures),
        enumerations=tuple(compilation.enumerations),
        behaviors=tuple(compilation.behaviors),
        tests=tuple(compilation.tests),
    )
    syntax = tuple(diagnostic for source in sources for diagnostic in source.diagnostics)
    checked = check(model) if checks else ()
    return CompileResult(model, (*syntax, *compilation.diagnostics, *checked))


def compile_text(text: str, *, source: str | None = None) -> CompileResult:
    return compile(parse(text, source=source))


def compile_files(paths: Iterable[str | Path]) -> CompileResult:
    return compile(*(parse_file(path) for path in paths))
