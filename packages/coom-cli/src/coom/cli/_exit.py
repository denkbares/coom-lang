"""Exit codes of the coom command and the error that ends a command without an answer."""

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    NEGATIVE = 1
    """A negative answer such as diagnostics, failed tests, an unsatisfiable configuration or violations."""
    NO_ANSWER = 2
    """No answer is possible, for example after a usage error, a model that does not compile or a missing package."""


class CommandError(Exception):
    """Ends a command with NO_ANSWER, the message is printed on stderr."""
