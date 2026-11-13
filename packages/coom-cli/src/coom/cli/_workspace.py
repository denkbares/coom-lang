"""The sources that form the model of a command, found in a folder or named by -m, and their compilation."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from coom.cli._exit import CommandError
from coom.cli._render import count
from coom.compiler import CompileResult, compile
from coom.diagnostics import Severity
from coom.model import Model
from coom.parser import ParseResult, parse_file

PATTERNS = ("*.model", "*.test")
"""The sources found in a folder, which is not searched recursively."""


@dataclass(frozen=True, slots=True)
class Workspace:
    sources: tuple[ParseResult, ...]

    @classmethod
    def open(cls, options: argparse.Namespace) -> "Workspace":
        """Parses the files named by -m, or the sources of the folder given by -C, relative to that folder."""
        directory = Path(options.directory)
        if not directory.is_dir():
            raise CommandError(f"{directory} is no folder")
        if options.models:
            files = [directory / name for name in options.models]
            for file in files:
                if not file.is_file():
                    raise CommandError(f"{file} does not exist")
            return cls(tuple(parse_file(file) for file in files))
        files = sorted({file for pattern in PATTERNS for file in directory.glob(pattern) if file.is_file()})
        if not files:
            raise CommandError(
                f"found no {' or '.join(PATTERNS)} files in {directory}, name them with -m or change the folder with -C"
            )
        sources = tuple(parse_file(file) for file in files)
        products = [source.source for source in sources if source.declares_product]
        if len(products) > 1:
            raise CommandError(
                f"found {len(products)} products in {directory}, name the files of one model with -m:\n"
                + "\n".join(f"  {product}" for product in products)
            )
        return cls(sources)

    def compile(self, *extra: ParseResult) -> CompileResult:
        """Compiles the sources together with further ones, which are compiled last."""
        return compile(*self.sources, *extra)

    def model(self) -> Model:
        """Compiles the sources and returns the model, refusing a model with errors."""
        result = self.compile()
        errors = sum(1 for diagnostic in result.diagnostics if diagnostic.severity is Severity.ERROR)
        if errors:
            raise CommandError(f"the model has {count(errors, 'error')}, run coom lint to see them")
        return result.model
