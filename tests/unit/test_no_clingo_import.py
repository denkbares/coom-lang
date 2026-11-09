"""Importing coom must leave clingo out of sys.modules."""

import subprocess
import sys


def test_import_coom_does_not_import_clingo() -> None:
    code = "import sys, coom; sys.exit(1 if 'clingo' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], check=False)
    assert result.returncode == 0
