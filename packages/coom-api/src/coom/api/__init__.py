"""The COOM product configuration language with its reference implementation in one import.

The packages coom-core, coom-lang and coom-clingo provide the namespace coom with the model, configurations and their
evaluation, the parser, compiler and writer, and the clingo based reference solver. This module re-exports their main
entry points.
"""

from importlib.metadata import version

from coom.clingo.solver import ClingoSolver, ClingoSolverError
from coom.compiler import CompileResult, compile, compile_files, compile_text
from coom.configuration import Configuration
from coom.diagnostics import Diagnostic, DiagnosticCode, Severity
from coom.model import Model
from coom.parser import LANGUAGE_VERSION, ParseResult, parse, parse_file
from coom.writer import write

__all__ = [
    "LANGUAGE_VERSION",
    "ClingoSolver",
    "ClingoSolverError",
    "CompileResult",
    "Configuration",
    "Diagnostic",
    "DiagnosticCode",
    "Model",
    "ParseResult",
    "Severity",
    "__version__",
    "compile",
    "compile_files",
    "compile_text",
    "parse",
    "parse_file",
    "write",
]

__version__ = version("coom-api")
