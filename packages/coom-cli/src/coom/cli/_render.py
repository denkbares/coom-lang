"""Output of the coom command, diagnostics in text and the JSON envelope shared by all commands."""

import json
import sys
from collections.abc import Iterable, Sequence
from typing import Any

from coom.diagnostics import Diagnostic, Severity
from coom.model import Span
from coom.model.json import write_location

JSON_VERSION = 1


def print_diagnostics(diagnostics: Iterable[Diagnostic]) -> None:
    for diagnostic in diagnostics:
        print(diagnostic, file=sys.stderr)


def print_json(command: str, items: Sequence[Any] = (), diagnostics: Iterable[Diagnostic] = ()) -> None:
    envelope = {
        "version": JSON_VERSION,
        "command": command,
        "items": list(items),
        "diagnostics": [diagnostic_json(diagnostic) for diagnostic in diagnostics],
    }
    print(json.dumps(envelope, indent=2, ensure_ascii=False))


def diagnostic_json(diagnostic: Diagnostic) -> dict[str, Any]:
    """Returns a diagnostic as JSON with its location as in the model schema."""
    result: dict[str, Any] = {"severity": diagnostic.severity, "code": diagnostic.code, "message": diagnostic.message}
    if diagnostic.span is not None:
        result["location"] = write_location(diagnostic.span)
    return result


def location(span: Span | None) -> str:
    """Returns a span as "file:line:col" with columns counted from one, as in diagnostics."""
    if span is None:
        return "?"
    source = f"{span.source}:" if span.source else ""
    return f"{source}{span.line}:{span.column + 1}"


def summary(diagnostics: Sequence[Diagnostic], where: str) -> str:
    """Returns a line like "2 errors, 1 warning in 3 files" or "no problems in 3 files"."""
    counts = [
        count(sum(1 for diagnostic in diagnostics if diagnostic.severity is severity), str(severity))
        for severity in Severity
        if any(diagnostic.severity is severity for diagnostic in diagnostics)
    ]
    return f"{', '.join(counts) or 'no problems'} in {where}"


def count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"
