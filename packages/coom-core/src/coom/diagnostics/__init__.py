"""Messages about a model, reported by the parser and the compiler with their source positions."""

from dataclasses import dataclass
from enum import StrEnum

from coom.model import Span


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiagnosticCode(StrEnum):
    """The family of a diagnostic, stable across changes of the message text."""

    SYNTAX = "syntax"
    NAME = "name"
    """A name that is not defined, defined twice or refers to the wrong kind of item."""
    TYPE = "type"
    STRUCTURE = "structure"
    """A rule about the shape of a declaration or statement, such as bounds, table sizes or cycles."""
    SOLVER = "solver"
    """A construct the solver does not support."""


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    code: DiagnosticCode
    message: str
    span: Span | None = None

    def __str__(self) -> str:
        if self.span is None:
            return f"{self.severity} {self.code}: {self.message}"
        source = f"{self.span.source}:" if self.span.source else ""
        return f"{source}{self.span.line}:{self.span.column + 1}: {self.severity} {self.code}: {self.message}"
