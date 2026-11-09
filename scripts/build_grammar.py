"""Generate the Python parser in src/coom/_parser from spec/grammar.

Runs the ANTLR tool (antlr4-tools) for the Python3 target and rewrites the semantic predicate newlineBefore() to its
Python spelling self.newlineBefore(). Not implemented yet.
"""

import sys


def main() -> int:
    print("not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
