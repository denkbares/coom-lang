"""Reference implementation of the COOM product configuration language.

Importing this package must not import clingo. The ASP solver lives in coom.asp and is imported on demand.
"""

from importlib.metadata import version

from coom.model import Model

__all__ = ["LANGUAGE_VERSION", "Model", "__version__"]

__version__ = version("coom-lang")

# The language version this package implements, see CHANGELOG.md at the repository root.
LANGUAGE_VERSION = "1.0"
