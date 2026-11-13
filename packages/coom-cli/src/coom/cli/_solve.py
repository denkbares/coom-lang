"""The solver commands solve and explain."""

from coom.cli._arguments import (
    SOLVER,
    CommandParser,
    add_configuration,
    add_format,
    add_workspace,
    not_implemented,
    runs,
)


def register(coom: CommandParser) -> None:
    solve = coom.add_command(
        "solve",
        "Complete a configuration",
        [
            "coom solve",
            "coom solve --set 'set kidsBike.color = Yellow'",
            "coom solve -c bike.json -o solved.json",
            "coom solve -n 0 --format jsonl",
        ],
        group=SOLVER,
    )
    add_configuration(solve)
    solve.add_argument(
        "-n",
        dest="number",
        metavar="N",
        type=int,
        help="enumerate up to N completions without defaults, 0 for all (default: one completion with defaults)",
    )
    solve.add_argument("-o", dest="output", metavar="FILE", help="write the completion as JSON to FILE")
    add_workspace(solve)
    add_format(solve, "text", "json", "jsonl")
    runs(solve, not_implemented)

    explain = coom.add_command(
        "explain",
        "Explain why a value is excluded",
        ["coom explain 'kidsBike.wheelSize = W14' --set 'set kidsBike.color = Yellow'"],
        group=SOLVER,
    )
    explain.add_argument("query", metavar="'PATH = VALUE'", help="the excluded value")
    add_configuration(explain)
    add_workspace(explain)
    add_format(explain, "text", "json")
    runs(explain, not_implemented)
