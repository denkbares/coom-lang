"""The diff command, which reports the semantic difference of two models."""

from coom.cli._arguments import MODEL, CommandParser, add_format, not_implemented, runs


def register(coom: CommandParser) -> None:
    diff = coom.add_command(
        "diff",
        "Report the semantic difference of two models",
        ["coom diff old/ new/", "coom diff old/KidsBike.model KidsBike.model --format json"],
        group=MODEL,
    )
    diff.add_argument("old", metavar="OLD", help="the old model as a file or a folder")
    diff.add_argument("new", metavar="NEW", help="the new model as a file or a folder")
    diff.add_argument(
        "-C", dest="directory", metavar="DIR", default=".", help="run as if started in DIR (default: current folder)"
    )
    add_format(diff, "text", "json")
    runs(diff, not_implemented)
