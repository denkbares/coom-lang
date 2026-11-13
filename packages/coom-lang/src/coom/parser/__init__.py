"""Parses COOM source text into an ANTLR parse tree and collects syntax errors as diagnostics."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from antlr4 import CommonTokenStream, InputStream, Token
from antlr4.atn.PredictionMode import PredictionMode
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.Errors import ParseCancellationException
from antlr4.error.ErrorStrategy import BailErrorStrategy, DefaultErrorStrategy

from coom.diagnostics import Diagnostic, DiagnosticCode, Severity
from coom.model import Span
from coom.parser._antlr.COOMLexer import COOMLexer
from coom.parser._antlr.COOMParser import COOMParser

LANGUAGE_VERSION = "1.0"
"""The version of the COOM language this parser implements."""


@dataclass(frozen=True, slots=True)
class ParseResult:
    """The parse tree of a model file with its tokens, including the hidden ones, and its syntax errors."""

    tree: Any
    """The root of the parse tree, a COOMParser.ModelContext."""
    tokens: tuple[Any, ...]
    diagnostics: tuple[Diagnostic, ...]
    source: str | None = None

    @property
    def ok(self) -> bool:
        return not any(diagnostic.severity is Severity.ERROR for diagnostic in self.diagnostics)


def parse(text: str, *, source: str | None = None) -> ParseResult:
    """Parses a model and always returns a tree, which after syntax errors holds what error recovery made of it.

    The source names the text in diagnostics and spans, typically the file path.
    """
    collector = _Collector(source)
    lexer = COOMLexer(InputStream(text))
    lexer.removeErrorListeners()
    lexer.addErrorListener(collector)
    tokens = CommonTokenStream(lexer)
    tokens.fill()

    # The fast SLL prediction suffices for almost all inputs. It may fail on valid input that needs the full context,
    # and its error recovery is weaker, so any syntax error triggers a second pass with full LL prediction.
    parser = COOMParser(tokens)
    parser.removeErrorListeners()
    parser._interp.predictionMode = PredictionMode.SLL
    parser._errHandler = BailErrorStrategy()
    try:
        tree = parser.model()
    except ParseCancellationException:
        parser.reset()
        parser._interp.predictionMode = PredictionMode.LL
        parser._errHandler = DefaultErrorStrategy()
        parser.addErrorListener(collector)
        tree = parser.model()
    return ParseResult(tree, tuple(tokens.tokens), tuple(collector.diagnostics), source)


def parse_file(path: str | Path) -> ParseResult:
    path = Path(path)
    return parse(path.read_text(encoding="utf-8"), source=str(path))


def token_span(start: Any, stop: Any | None = None, source: str | None = None) -> Span:
    """Returns the span from the start of one token to the end of another, the same token if stop is None."""
    stop = start if stop is None else stop
    lines = (stop.text or "").split("\n")
    end_line = stop.line + len(lines) - 1
    end_column = (stop.column if len(lines) == 1 else 0) + len(lines[-1])
    return Span(start.line, start.column, end_line, end_column, source)


class _Collector(ErrorListener):  # type: ignore[misc]
    def __init__(self, source: str | None) -> None:
        self.source = source
        self.diagnostics: list[Diagnostic] = []

    def syntaxError(self, recognizer: Any, offendingSymbol: Any, line: int, column: int, msg: str, e: Any) -> None:
        if offendingSymbol is None:
            span = Span(line, column, line, column + 1, self.source)
        else:
            span = token_span(offendingSymbol, source=self.source)
            if offendingSymbol.type == COOMLexer.RESERVED:
                msg = f"'{offendingSymbol.text}' is reserved and cannot be used here, quote it to use it as a name"
            elif offendingSymbol.type == Token.EOF:
                span = Span(line, column, line, column, self.source)
        self.diagnostics.append(Diagnostic(Severity.ERROR, DiagnosticCode.SYNTAX, msg, span))
