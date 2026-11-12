"""The coom command, which checks models and reports their diagnostics."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version

from coom.compiler import compile_files


def main(arguments: Sequence[str] | None = None) -> int:
    """Runs the coom command and returns its exit code."""
    parser = argparse.ArgumentParser(prog="coom", description="Tools for COOM product configuration models.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('coom-cli')}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="compile models and report their diagnostics")
    check.add_argument("files", nargs="+", help="the model files, compiled together as one model")
    options = parser.parse_args(arguments)
    if options.command == "check":
        result = compile_files(options.files)
        for diagnostic in result.diagnostics:
            print(diagnostic, file=sys.stderr)
        return 0 if result.ok else 1
    raise AssertionError(options.command)


if __name__ == "__main__":
    sys.exit(main())
