"""Every profile model of the conformance suite compiles without diagnostics."""

from pathlib import Path

import pytest

from coom.compiler import compile_files

CONFORMANCE = Path(__file__).resolve().parents[2] / "spec" / "conformance"
MODELS = sorted(path for path in CONFORMANCE.rglob("*.model") if "syntax" not in path.relative_to(CONFORMANCE).parts)


@pytest.mark.parametrize("path", MODELS, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_profile_model_compiles(path: Path) -> None:
    result = compile_files([path])
    assert result.ok, "\n".join(map(str, result.diagnostics))
