"""Output of the coom command, diagnostics in text and the JSON envelope shared by all commands."""

import json
import sys
from collections.abc import Iterable, Sequence
from typing import Any

from coom.diagnostics import Diagnostic, Severity

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
    """Returns a diagnostic as JSON with columns counted from one, as in the text output."""
    result: dict[str, Any] = {"severity": diagnostic.severity, "code": diagnostic.code, "message": diagnostic.message}
    if diagnostic.span is not None:
        span = diagnostic.span
        result["location"] = {
            "source": span.source,
            "line": span.line,
            "column": span.column + 1,
            "endLine": span.end_line,
            "endColumn": span.end_column + 1,
        }
    return result


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
