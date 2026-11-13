"""The test command, which runs the test blocks of the model."""

from coom.cli._arguments import MODEL, CommandParser, add_format, add_selectors, add_workspace, not_implemented, runs


def register(coom: CommandParser) -> None:
    test = coom.add_command(
        "test",
        "Run the test blocks of the model",
        ["coom test", "coom test KidsBike.color -x", "coom test @KidsBike.test:3", "coom test --format jsonl"],
        group=MODEL,
    )
    add_selectors(test)
    test.add_argument("-x", dest="first", action="store_true", help="stop at the first failing test")
    add_workspace(test)
    add_format(test, "text", "json", "jsonl")
    runs(test, not_implemented)
