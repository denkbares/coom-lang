"""The models of the conformance suite parse, and every snippet in the invalid syntax corpus is rejected."""

from pathlib import Path

import pytest

from coom.parser import parse_file

CONFORMANCE = Path(__file__).resolve().parent.parent / "spec" / "conformance"
INVALID = CONFORMANCE / "syntax" / "invalid"
VALID = sorted(path for path in CONFORMANCE.rglob("*.model") if INVALID not in path.parents)


@pytest.mark.parametrize("path", VALID, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_valid_model_parses(path: Path) -> None:
    result = parse_file(path)
    assert result.ok, "\n".join(map(str, result.diagnostics))


@pytest.mark.parametrize("path", sorted(INVALID.glob("*.model")), ids=lambda path: path.name)
def test_invalid_snippet_is_rejected(path: Path) -> None:
    assert not parse_file(path).ok
