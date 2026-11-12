"""Generate the Python parser of the coom-lang package from spec/grammar.

Copies the grammar to a temporary directory, rewrites the semantic predicates to their Python spelling and runs the
ANTLR tool through antlr4-tools. The hand written files in the output directory are kept.

Run it with "uv run scripts/build_grammar.py".
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ANTLR_VERSION = "4.13.2"
ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "spec" / "grammar"
OUTPUT = ROOT / "packages" / "coom-lang" / "src" / "coom" / "parser" / "_antlr"
KEEP = {"__init__.py", "COOMParserBase.py"}

# The grammar spells the predicates for Java, the Python target needs self and not.
PREDICATES = {
    "{!newlineBefore()}?": "{not self.newlineBefore()}?",
    "{newlineBefore()}?": "{self.newlineBefore()}?",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)
        for grammar in GRAMMAR.glob("*.g4"):
            text = grammar.read_text(encoding="utf-8")
            for java, python in PREDICATES.items():
                text = text.replace(java, python)
            (source / grammar.name).write_text(text, encoding="utf-8")

        for generated in OUTPUT.iterdir():
            if generated.is_file() and generated.name not in KEEP:
                generated.unlink()

        command = [
            "antlr4",
            "-v",
            ANTLR_VERSION,
            "-Dlanguage=Python3",
            "-visitor",
            "-no-listener",
            "-Werror",
            "-Xexact-output-dir",
            "-lib",
            str(source),
            "-o",
            str(OUTPUT),
            str(source / "COOM.g4"),
        ]
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode

    # Interpreter data and token files serve tools only, the runtime does not read them.
    for leftover in [*OUTPUT.glob("*.interp"), *OUTPUT.glob("*.tokens")]:
        leftover.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
