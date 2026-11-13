"""The lint command, which reports the diagnostics of the model or of a snippet compiled against it."""

import argparse

from coom.cli._arguments import MODEL, CommandParser, add_format, add_selectors, add_workspace, runs
from coom.cli._exit import CommandError, ExitCode
from coom.cli._render import count, print_diagnostics, print_json, summary
from coom.cli._workspace import Workspace
from coom.diagnostics import Severity
from coom.parser import parse

SNIPPET = "<snippet>"
"""The source name of the text given by --snippet."""


def register(coom: CommandParser) -> None:
    lint = coom.add_command(
        "lint",
        "Compile the model and report its diagnostics",
        [
            "coom lint",
            "coom lint -m KidsBike.model KidsBike.test --format json",
            "coom lint --snippet 'behavior KidsBike { require color = Red }'",
        ],
        group=MODEL,
    )
    add_selectors(lint)
    lint.add_argument(
        "--snippet",
        metavar="TEXT",
        help="top level statements compiled as one more source of the model, only their diagnostics are reported",
    )
    add_workspace(lint)
    add_format(lint, "text", "json")
    runs(lint, run)


def run(options: argparse.Namespace) -> int:
    if options.selectors or options.dependencies is not None or options.dependents is not None:
        raise CommandError("selectors of lint are not implemented yet")
    workspace = Workspace.open(options)
    if options.snippet is None:
        result = workspace.compile()
        diagnostics = result.diagnostics
        where = count(len(workspace.sources), "file")
    else:
        result = workspace.compile(parse(options.snippet, source=SNIPPET))
        model = [d for d in result.diagnostics if d.span is None or d.span.source != SNIPPET]
        errors = sum(1 for diagnostic in model if diagnostic.severity is Severity.ERROR)
        if errors:
            raise CommandError(f"the model has {count(errors, 'error')}, run coom lint without --snippet to see them")
        diagnostics = tuple(d for d in result.diagnostics if d.span is not None and d.span.source == SNIPPET)
        where = "the snippet"
    if options.format == "json":
        print_json("lint", diagnostics=diagnostics)
    else:
        print_diagnostics(diagnostics)
        print(summary(diagnostics, where))
    failed = any(diagnostic.severity is Severity.ERROR for diagnostic in diagnostics)
    return ExitCode.NEGATIVE if failed else ExitCode.SUCCESS
