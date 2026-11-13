"""State shared by the compiler phases and helpers to report errors at parse tree positions."""

import re
from dataclasses import dataclass, field
from typing import Any, NoReturn

from antlr4 import ParserRuleContext
from antlr4.tree.Tree import ErrorNode

from coom.diagnostics import Diagnostic, DiagnosticCode, Severity
from coom.model import ROOT_NAME, Behavior, Enumeration, Option, Span, Structure, TestCase
from coom.parser import token_span


class Abort(Exception):
    """Stops compiling the current statement, whose error is already reported or is a syntax error."""


@dataclass(eq=False)
class Compilation:
    """The model under construction and the diagnostics collected so far."""

    source: str | None = None
    """The source of the parse tree the current phase works on."""
    root: Structure = field(default_factory=lambda: Structure(name=ROOT_NAME))
    structures: list[Structure] = field(default_factory=list)
    enumerations: list[Enumeration] = field(default_factory=list)
    behaviors: list[Behavior] = field(default_factory=list)
    tests: list[TestCase] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    types: dict[str, Structure | Enumeration] = field(default_factory=dict)
    declared: dict[Any, Structure | Enumeration] = field(default_factory=dict)
    """The type declared by each product, structure and enumeration block, keyed by its parse tree node."""
    options: dict[Any, Option] = field(default_factory=dict)
    """The option declared by each option node, which the attribute values phase completes."""
    product: Any = None
    """The first product block, any further one is an error."""

    def span(self, node: Any) -> Span:
        if isinstance(node, ParserRuleContext):
            stop = node.stop
            if stop is None or stop.tokenIndex < node.start.tokenIndex:
                stop = node.start
            return token_span(node.start, stop, self.source)
        return token_span(node, source=self.source)

    def error(self, node: Any, code: DiagnosticCode, message: str) -> None:
        self.diagnostics.append(Diagnostic(Severity.ERROR, code, message, self.span(node)))

    def fail(self, node: Any, code: DiagnosticCode, message: str) -> NoReturn:
        self.error(node, code, message)
        raise Abort


def need[T](node: T | None) -> T:
    """Returns a parse tree node that error recovery may have left out, aborting the statement if it is missing."""
    if node is None or isinstance(node, ErrorNode):
        raise Abort
    return node


def children(node: Any) -> list[Any]:
    return list(node.children or ()) if node is not None else []


_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)")
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def unquote(text: str) -> str:
    """Returns the text of a quoted name with its escape sequences resolved, other names unchanged."""
    if len(text) < 2 or text[0] not in "'\"" or text[-1] != text[0]:
        return text

    def resolve(match: re.Match[str]) -> str:
        escape = match.group(1)
        return chr(int(escape[1:], 16)) if escape[0] == "u" and len(escape) == 5 else _ESCAPES.get(escape, escape)

    return _ESCAPE.sub(resolve, text[1:-1])


def name(node: Any) -> str:
    return unquote(need(node).getText())
