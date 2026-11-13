"""The coom command, which lints, shows, tests and solves models and works on their configurations."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version

from coom.cli import _config, _diff, _edit, _lint, _show, _solve, _test
from coom.cli._arguments import CommandParser, find, help_command, overview, runs
from coom.cli._exit import CommandError, ExitCode

__all__ = ["main"]


def parser() -> CommandParser:
    coom = CommandParser(prog="coom", description="Tools for COOM product configuration models.")
    coom.add_argument("--version", action="version", version=f"%(prog)s {version('coom-cli')}")
    for module in (_lint, _test, _show, _diff, _solve, _edit, _config):
        module.register(coom)
    help = coom.add_command("help", "Print the help of a command", ["coom help config apply", "coom help --all"])
    help.add_argument("names", metavar="COMMAND", nargs="*", help="the command, such as lint or config apply")
    help.add_argument("--all", action="store_true", help="print the complete reference of every command")
    runs(help, help_command(coom))
    return coom


def main(arguments: Sequence[str] | None = None) -> int:
    """Runs the coom command and returns its exit code."""
    arguments = sys.argv[1:] if arguments is None else arguments
    coom = parser()
    if not arguments:
        print(overview(coom))
        return ExitCode.SUCCESS
    try:
        options: argparse.Namespace
        options, unknown = coom.parse_known_args(arguments)
        if unknown:
            # argparse reports them at the top level, the usage of the command itself is more helpful
            find(coom, options.prog.split()[1:]).error(f"unrecognized arguments: {' '.join(unknown)}")
        return int(options.run(options))
    except CommandError as error:
        print(error, file=sys.stderr)
        return ExitCode.NO_ANSWER
    except SystemExit as exit:
        # --help and --version print and exit through argparse
        return exit.code if isinstance(exit.code, int) else ExitCode.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
