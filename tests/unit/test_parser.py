"""Statement termination, error reporting and spans of the parser."""

from coom.diagnostics import Severity
from coom.model import Span
from coom.parser import parse, token_span


def test_statements_end_with_line_breaks_or_semicolons() -> None:
    lines = parse("enumeration Color {\n    Red\n    Green // comment\n    Blue\n}")
    semicolons = parse("enumeration Color { Red; Green; Blue }")
    assert lines.ok and semicolons.ok
    enumeration = lines.tree.enumeration(0)
    assert [option.name().getText() for option in enumeration.option()] == ["Red", "Green", "Blue"]


def test_statements_on_one_line_need_semicolons() -> None:
    assert not parse("enumeration Color { Red Green }").ok


def test_condition_cells_of_a_table_row_stay_on_its_line() -> None:
    def rows(text: str) -> int:
        result = parse(text)
        assert result.ok
        table = result.tree.behavior(0).behavior_block().conditioned(0).derivation_table()
        return len(table.derivation_table_row())

    model = "behavior {\n    require (a, b) condition (c)\n    (1, 2) (3)\n}"
    assert rows(model) == 1
    assert rows(model.replace("(1, 2) (3)", "(1, 2)\n    (3)")) == 2


def test_errors_carry_the_span_of_the_offending_token() -> None:
    result = parse("product {\n    Color c / 3\n}", source="bike.model")
    [error, *_] = result.diagnostics
    assert error.severity is Severity.ERROR
    assert error.span == Span(2, 12, 2, 13, "bike.model")
    assert str(error).startswith("bike.model:2:13: error: ")


def test_reserved_words_get_a_dedicated_message() -> None:
    [error] = parse("product { static Color c }").diagnostics
    assert "'static' is reserved" in error.message
    assert parse('product { Color "static" }').ok


def test_lexer_errors_are_reported() -> None:
    result = parse("product { num 0-∞ x }")
    assert any("token recognition error" in diagnostic.message for diagnostic in result.diagnostics)


def test_a_tree_is_returned_after_errors() -> None:
    result = parse("product { Color c / 3 }\nstructure Bike { Color color }")
    assert not result.ok
    assert result.tree.structure(0).name().getText() == "Bike"


def test_token_span_covers_multiline_tokens() -> None:
    result = parse("/* a\nbc */ product { }")
    comment = result.tokens[0]
    assert token_span(comment) == Span(1, 0, 2, 5)
