"""Messages about a model, reported by the parser and the compiler with their source positions."""

from dataclasses import dataclass
from enum import StrEnum

from coom.model import Span


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    message: str
    span: Span | None = None

    def __str__(self) -> str:
        if self.span is None:
            return f"{self.severity}: {self.message}"
        source = f"{self.span.source}:" if self.span.source else ""
        return f"{source}{self.span.line}:{self.span.column + 1}: {self.severity}: {self.message}"
