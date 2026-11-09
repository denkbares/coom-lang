"""Base class of the generated parser that implements the statement termination predicate of the grammar."""

from antlr4 import Parser, Token


class COOMParserBase(Parser):  # type: ignore[misc]
    def newlineBefore(self) -> bool:  # noqa: N802
        """Returns whether a line break separates the current token from the previous default channel token."""
        stream = self.getTokenStream()
        for index in range(stream.LT(1).tokenIndex - 1, -1, -1):
            token = stream.get(index)
            if token.channel == Token.DEFAULT_CHANNEL:
                return False
            if token.type == self.NEWLINE:
                return True
        return False
