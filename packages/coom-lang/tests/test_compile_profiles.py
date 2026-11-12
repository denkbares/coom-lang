"""Every profile model of the conformance suite compiles without diagnostics and is detected in its profile."""

from pathlib import Path

import pytest

from coom.check import Profile, detect_profiles
from coom.compiler import compile_files

CONFORMANCE = Path(__file__).resolve().parents[3] / "spec" / "conformance"
MODELS = sorted(path for path in CONFORMANCE.rglob("*.model") if "syntax" not in path.relative_to(CONFORMANCE).parts)


@pytest.mark.parametrize("path", MODELS, ids=lambda path: str(path.relative_to(CONFORMANCE)))
def test_profile_model_compiles(path: Path) -> None:
    # a model is compiled together with its session tests, which the TEST profile needs
    tests = path.with_suffix(".test")
    result = compile_files([path, tests] if tests.exists() else [path])
    assert result.ok, "\n".join(map(str, result.diagnostics))
    folder = path.relative_to(CONFORMANCE).parts[0]
    assert Profile(folder) in detect_profiles(result.model)
