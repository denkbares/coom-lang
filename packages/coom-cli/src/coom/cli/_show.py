"""The show command, which selects items of the model and renders them."""

from coom.cli._arguments import MODEL, CommandParser, add_format, add_selectors, add_workspace, not_implemented, runs

KINDS = ("structure", "feature", "enumeration", "option", "attribute", "behavior", "test")


def register(coom: CommandParser) -> None:
    show = coom.add_command(
        "show",
        "Select items of the model and render them",
        [
            "coom show",
            "coom show KidsBike.color",
            "coom show 'KidsBike.*' --view list",
            "coom show KidsBike.color --dependents=1 --kind behavior,test",
            "coom show --format json",
        ],
        group=MODEL,
    )
    add_selectors(show)
    show.add_argument(
        "--view",
        choices=("list", "detail", "tree"),
        help="the view (default: tree without selector, detail for one match, list for several)",
    )
    show.add_argument("--kind", metavar="KIND", help=f"only items of these comma separated kinds: {', '.join(KINDS)}")
    show.add_argument("--depth", metavar="N", type=int, help="the depth of the tree view")
    show.add_argument("--limit", metavar="N", type=int, help="the maximum number of printed items")
    add_workspace(show)
    add_format(show, "text", "json", "coom")
    runs(show, not_implemented)
