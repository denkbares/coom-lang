"""Reference implementation of the COOM product configuration language.

Importing this package must not import clingo. The ASP solver lives in coom.asp and is imported on demand.
"""

from importlib.metadata import version

from coom.compiler import CompileResult, compile, compile_files, compile_text
from coom.configuration import Configuration
from coom.diagnostics import Diagnostic, Severity
from coom.model import Model
from coom.parser import ParseResult, parse, parse_file

__all__ = [
    "LANGUAGE_VERSION",
    "CompileResult",
    "Configuration",
    "Diagnostic",
    "Model",
    "ParseResult",
    "Severity",
    "__version__",
    "compile",
    "compile_files",
    "compile_text",
    "parse",
    "parse_file",
]

__version__ = version("coom-lang")

# The language version this package implements, see CHANGELOG.md at the repository root.
LANGUAGE_VERSION = "1.0"
