"""The config commands, which work on configurations of the model."""

from coom.cli._arguments import (
    CONFIGURATIONS,
    CommandParser,
    add_configuration,
    add_format,
    add_workspace,
    not_implemented,
    runs,
)


def register(coom: CommandParser) -> None:
    config = coom.add_command(
        "config",
        "Apply steps to configurations, evaluate and check them",
        ["coom config apply -c bike.json 'set kidsBike.color = Red'"],
        group=CONFIGURATIONS,
    )
    apply = config.add_command(
        "apply",
        "Run steps on a configuration file and save it",
        [
            "coom config apply -c bike.json 'set kidsBike.color = Red'",
            "coom config apply -c bike.json < steps.test",
            "coom config apply -c bike.json --interactive",
        ],
    )
    apply.add_argument("steps", metavar="STEP", nargs="*", help="the steps, read from stdin when none is given")
    apply.add_argument("--interactive", action="store_true", help="read steps line by line and print each result")
    add_configuration(apply)
    add_workspace(apply)
    add_format(apply, "text", "json")
    runs(apply, not_implemented)

    show = config.add_command(
        "show",
        "Print a configuration or evaluate formulas on it",
        [
            "coom config show -c bike.json",
            "coom config show -c bike.json 'kidsBike.wheelSize = W14'",
            "coom config show -c bike.json kidsBike.wheelSize --options",
            "coom config show -c bike.json --format coom",
        ],
    )
    show.add_argument(
        "formulas", metavar="FORMULA", nargs="*", help="a formula or path, the whole configuration without"
    )
    show.add_argument("--roles", action="store_true", help="add the role of each value")
    show.add_argument("--options", action="store_true", help="add the available and blocked options")
    add_configuration(show)
    add_workspace(show)
    add_format(show, "text", "json", "coom")
    runs(show, not_implemented)

    check = config.add_command(
        "check",
        "Report violations of configurations against the model",
        ["coom config check bike.json", "coom config check configs/*.json --format json"],
    )
    check.add_argument("files", metavar="FILE", nargs="+", help="the configuration files")
    add_workspace(check)
    add_format(check, "text", "json")
    runs(check, not_implemented)
