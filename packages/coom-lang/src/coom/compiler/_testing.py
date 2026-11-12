"""The phase that compiles test blocks into test cases."""

from typing import Any

from coom.compiler._behaviors import resolve_origin
from coom.compiler._context import Abort, Compilation, children, name, need
from coom.compiler._expressions import Expressions, Scope
from coom.model import (
    AttributeStep,
    Constant,
    Enumeration,
    IsAvailable,
    IsBlocked,
    IsEmpty,
    IsFixed,
    IsHidden,
    IsReadonly,
    IsShown,
    Path,
    RemoveValue,
    ResetValue,
    SetValue,
    Structure,
    TestCase,
    TestStep,
)
from coom.parser._antlr.COOMParser import COOMParser


def compile_tests(compilation: Compilation, tree: Any) -> None:
    for node in children(tree):
        if not isinstance(node, COOMParser.TestContext):
            continue
        try:
            origin = resolve_origin(compilation, node.name())
        except Abort:
            continue
        expressions = Expressions(compilation, origin)
        scope = Scope.of(compilation, origin)
        steps: list[TestStep] = []
        for child in children(node):
            try:
                if isinstance(child, COOMParser.DefineContext):
                    scope = scope.define(name(child.name()), expressions.formula(child.formula(), scope))
                elif isinstance(child, COOMParser.Test_statementContext):
                    steps.append(_step(compilation, expressions, need(child.getChild(0)), scope))
            except Abort:
                pass
        compilation.tests.append(TestCase(origin=origin, steps=tuple(steps), span=compilation.span(node)))


def _step(compilation: Compilation, expressions: Expressions, node: Any, scope: Scope) -> TestStep:
    span = compilation.span(node)
    match node:
        case COOMParser.Test_removeContext():
            return RemoveValue(_path(expressions, node, scope), span=span)
        case COOMParser.Test_resetContext():
            return ResetValue(_path(expressions, node, scope), span=span)
        case COOMParser.Test_emptyContext():
            return IsEmpty(_path(expressions, node, scope), span=span)
        case COOMParser.Test_readonlyContext():
            return IsReadonly(_path(expressions, node, scope), span=span)
        case COOMParser.Test_setContext() | COOMParser.Test_fixedContext() | COOMParser.Test_shownContext():
            path = expressions.assignable(node.path(), scope)
            value = None if node.formula_atom() is None else _value(compilation, expressions, node, path, scope)
            if isinstance(node, COOMParser.Test_setContext):
                return SetValue(path, value, span=span)
            if isinstance(node, COOMParser.Test_fixedContext):
                return IsFixed(path, value, span=span)
            return IsShown(path, value, span=span)
        case COOMParser.Test_availableContext() | COOMParser.Test_blockedContext():
            path = expressions.assignable(node.path(), scope)
            if node.formula_atom() is None and not isinstance(path.type, Structure):
                compilation.fail(node.path(), f"{need(node.kw).text} needs a value unless the path holds instances")
            value = None if node.formula_atom() is None else _value(compilation, expressions, node, path, scope)
            if isinstance(node, COOMParser.Test_availableContext):
                return IsAvailable(path, value, span=span)
            return IsBlocked(path, value, span=span)
        case COOMParser.Test_hiddenContext():
            path = expressions.assignable(node.path(), scope)
            if node.formula_atom() is None:
                return IsHidden(path, span=span)
            if not isinstance(path.type, Enumeration):
                compilation.fail(node.path(), "isHidden with an option needs a path to an enumeration feature")
            return IsHidden(path, _value(compilation, expressions, node, path, scope), span=span)
        case _:
            raise Abort


def _path(expressions: Expressions, node: Any, scope: Scope) -> Path:
    path = expressions.path(node.path(), scope)
    if path.steps and isinstance(path.steps[-1], AttributeStep):
        expressions.compilation.fail(node.path(), "a test step cannot address an attribute")
    return path


def _value(compilation: Compilation, expressions: Expressions, node: Any, path: Path, scope: Scope) -> Constant:
    atom = need(node.formula_atom())
    value = expressions.formula(atom, scope.expecting(path.type))
    if not isinstance(value, Constant):
        compilation.fail(atom, f"{atom.getText()} is not a value")
    return value
