"""Importing the compiler must leave clingo out of sys.modules."""

import subprocess
import sys


def test_import_compiler_does_not_import_clingo() -> None:
    code = "import sys, coom.compiler, coom.writer; sys.exit(1 if 'clingo' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], check=False)
    assert result.returncode == 0
