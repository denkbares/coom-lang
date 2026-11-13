"""The edit commands, which change the model and keep its meaning apart from the intended change."""

from coom.cli._arguments import CHANGES, CommandParser, add_format, add_workspace, not_implemented, runs


def register(coom: CommandParser) -> None:
    edit = coom.add_command(
        "edit", "Rename or remove an item", ["coom edit rename KidsBike.color paint --dry-run"], group=CHANGES
    )
    rename = edit.add_command(
        "rename",
        "Rename an item and every reference to it",
        ["coom edit rename KidsBike.color paint --dry-run", "coom edit rename Color Paint --configs 'configs/*.json'"],
    )
    rename.add_argument("item", metavar="ITEM", help="the qualified name of the item")
    rename.add_argument("name", metavar="NEW_NAME", help="the new name")
    remove = edit.add_command(
        "remove",
        "Remove an item, refused while references to it exist",
        ["coom edit remove KidsBike.supportWheels", "coom edit remove KidsBike.supportWheels --cascade --dry-run"],
    )
    remove.add_argument("item", metavar="ITEM", help="the qualified name of the item")
    remove.add_argument("--cascade", action="store_true", help="also remove the behaviors and tests that refer to it")
    for command in (rename, remove):
        command.add_argument("--dry-run", action="store_true", help="print the change as a unified diff")
        command.add_argument(
            "--configs", metavar="GLOB", help="also transform the configuration files that match the glob"
        )
        add_workspace(command)
        add_format(command, "text", "json")
        runs(command, not_implemented)
