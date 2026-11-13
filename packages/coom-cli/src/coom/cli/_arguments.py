"""The argument parser of the coom command with its shared options, the overview and the complete reference."""

import argparse
import difflib
from collections.abc import Callable, Iterator, Sequence
from typing import Any, NoReturn

from coom.cli._exit import CommandError, ExitCode

type Run = Callable[[argparse.Namespace], int]

MODEL = "Model"
SOLVER = "Solver"
CHANGES = "Changes of the model"
CONFIGURATIONS = "Configurations"
GROUPS = (MODEL, SOLVER, CHANGES, CONFIGURATIONS)
"""The groups of the overview in their order, each command belongs to one of them."""


class CommandParser(argparse.ArgumentParser):
    """An argument parser for a command, which knows its summary, examples and subcommands."""

    def __init__(
        self, *args: Any, summary: str = "", examples: Sequence[str] = (), group: str = "", **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.summary = summary
        self.examples = tuple(examples)
        self.group = group
        self.commands: dict[str, CommandParser] = {}
        self._commands: argparse._SubParsersAction[CommandParser] | None = None

    def add_command(self, name: str, summary: str, examples: Sequence[str], group: str = "") -> "CommandParser":
        if self._commands is None:
            self._commands = self.add_subparsers(
                title="commands", metavar="COMMAND", dest=f"{self.prog} command", required=True
            )
        epilog = "examples:\n" + "\n".join(f"  {example}" for example in examples)
        parser = self._commands.add_parser(
            name,
            help=summary,
            description=summary,
            epilog=epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            summary=summary,
            examples=examples,
            group=group or self.group,
        )
        self.commands[name] = parser
        return parser

    def leaves(self) -> Iterator["CommandParser"]:
        """Returns the commands that run something, subcommands in place of the commands that group them."""
        for command in self.commands.values():
            if command.commands:
                yield from command.leaves()
            else:
                yield command

    def error(self, message: str) -> NoReturn:
        lines = [self.format_usage().rstrip(), f"{self.prog}: error: {message}"]
        examples = self.examples or tuple(example for leaf in self.leaves() for example in leaf.examples[:1])
        if examples:
            lines.append(f"example: {examples[0]}")
        raise CommandError("\n".join(lines))


def not_implemented(options: argparse.Namespace) -> int:
    raise CommandError(f"{options.prog} is not implemented yet")


def runs(parser: CommandParser, run: Run) -> None:
    parser.set_defaults(run=run, prog=parser.prog)


def add_workspace(parser: CommandParser) -> None:
    group = parser.add_argument_group("model")
    group.add_argument(
        "-C", dest="directory", metavar="DIR", default=".", help="run as if started in DIR (default: current folder)"
    )
    group.add_argument(
        "-m",
        dest="models",
        metavar="FILE",
        nargs="+",
        action="extend",
        help="the model and test files, instead of all *.model and *.test files of the folder",
    )


def add_format(parser: CommandParser, *formats: str) -> None:
    parser.add_argument(
        "--format", choices=formats, default=formats[0], help=f"the output format (default: {formats[0]})"
    )


def add_selectors(parser: CommandParser) -> None:
    parser.add_argument(
        "selectors",
        metavar="SELECTOR",
        nargs="*",
        help="an item by qualified name such as Bike.color, a glob such as 'Bike.*', a behavior or test as @FILE:LINE",
    )
    group = parser.add_argument_group("dependencies")
    group.add_argument(
        "--dependencies",
        metavar="N",
        nargs="?",
        type=_distance,
        const=0,
        help="add what the selection depends on, up to the distance N or all without N",
    )
    group.add_argument(
        "--dependents",
        metavar="N",
        nargs="?",
        type=_distance,
        const=0,
        help="add what depends on the selection, up to the distance N or all without N",
    )


def add_configuration(parser: CommandParser) -> None:
    group = parser.add_argument_group("configuration")
    group.add_argument("-c", dest="configuration", metavar="FILE", help="the configuration (default: empty)")
    group.add_argument(
        "--set",
        dest="steps",
        metavar="STEP",
        action="append",
        default=[],
        help="a step applied to the configuration first, such as 'set bike.color = Red', repeatable",
    )


def _distance(text: str) -> int:
    distance = int(text)
    if distance < 1:
        raise argparse.ArgumentTypeError("the distance must be at least 1")
    return distance


def overview(coom: CommandParser) -> str:
    """Returns one line and one example per command, grouped as in GROUPS."""
    leaves = list(coom.leaves())
    width = max(len(_name(leaf)) for leaf in leaves)
    lines = [coom.format_usage().rstrip(), "", coom.description or ""]
    for group in GROUPS:
        lines += ["", f"{group}:"]
        for leaf in leaves:
            if leaf.group == group:
                lines.append(f"  {_name(leaf):<{width}}  {leaf.summary}")
                lines.append(f"  {'':<{width}}    {leaf.examples[0]}")
    lines += [
        "",
        "Exit codes: 0 success, 1 negative answer such as diagnostics or failed tests, 2 no answer possible.",
        "Run 'coom help COMMAND' for the options of a command and 'coom help --all' for the complete reference.",
    ]
    return "\n".join(lines)


def reference(coom: CommandParser) -> str:
    """Returns the overview followed by the help of every command."""
    sections = [overview(coom), *(command.format_help().rstrip() for command in _all(coom))]
    return f"\n\n{'=' * 80}\n\n".join(sections)


def find(coom: CommandParser, names: Sequence[str]) -> CommandParser:
    """Returns the command named by a sequence like ("config", "apply"), suggesting the nearest names otherwise."""
    command = coom
    for name in names:
        if name not in command.commands:
            message = f"unknown command {' '.join((_name(command), name)).strip()}"
            nearest = difflib.get_close_matches(name, command.commands)
            if nearest:
                message += f", did you mean {' or '.join(nearest)}?"
            raise CommandError(message)
        command = command.commands[name]
    return command


def _all(parser: CommandParser) -> Iterator[CommandParser]:
    for command in parser.commands.values():
        yield command
        yield from _all(command)


def _name(parser: CommandParser) -> str:
    return parser.prog.removeprefix("coom").strip()


def help_command(coom: CommandParser) -> Run:
    def run(options: argparse.Namespace) -> int:
        if options.all:
            print(reference(coom))
        elif options.names:
            print(find(coom, options.names).format_help().rstrip())
        else:
            print(overview(coom))
        return ExitCode.SUCCESS

    return run
