"""The packages share the namespace coom, which none of them may turn into a regular package."""

import importlib

import coom
import coom.api


def test_coom_is_a_namespace_package() -> None:
    assert getattr(coom, "__file__", None) is None


def test_every_part_of_the_namespace_imports() -> None:
    for name in ("model", "configuration", "diagnostics", "check", "parser", "compiler", "writer", "clingo", "api"):
        importlib.import_module(f"coom.{name}")


def test_api_reexports_the_entry_points() -> None:
    model = coom.api.compile_text("product { bool lights }").model
    assert coom.api.ClingoSolver(model).solve() is not None
