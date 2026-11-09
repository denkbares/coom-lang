"""Source positions shared by all parts of the model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Span:
    """A region of a source text with lines counted from one and columns from zero, as ANTLR does."""

    line: int
    column: int
    end_line: int
    end_column: int
    source: str | None = None


def span_field() -> Any:
    # Spans of values do not take part in equality, so a reparsed model equals the original.
    return field(default=None, compare=False, repr=False)
