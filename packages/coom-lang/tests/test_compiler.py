"""Name resolution, statement lowering and error reporting of the compiler."""

from decimal import Decimal
from typing import Any

from coom.compiler import compile, compile_text
from coom.model import (
    And,
    AttributeStep,
    Behavior,
    Binary,
    Boolean,
    Combinations,
    Compare,
    CompareOp,
    Constant,
    Default,
    Feature,
    FeatureStep,
    Imply,
    Index,
    IsAvailable,
    IsDefined,
    IsHidden,
    IsReadonly,
    Model,
    Not,
    Numerical,
    Option,
    Or,
    Path,
    PathAccess,
    Require,
    SetValue,
    Structure,
    Textual,
    Visibility,
)
from coom.parser import parse

BIKE = """
product {
    Bike bike
}
structure Bike {
    Color color
    0..4 Bag bags
    num.## /kg 0-100 weight
    num.* exact
    bool stand
    string note
}
structure Bag { Size size }
enumeration Color { Red; Blue }
enumeration Size {
    attribute num volume
    attribute Color tint
    small = (1 Red)
    large = (5 Blue)
}
"""


def compiled(behavior: str = "", model: str = BIKE) -> Model:
    result = compile_text(model + behavior)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    return result.model


def errors(text: str) -> list[str]:
    return [diagnostic.message for diagnostic in compile_text(BIKE + text).diagnostics]


def option(model: Model, qualified_name: str) -> Option:
    item = model[qualified_name]
    assert isinstance(item, Option)
    return item


def feature(model: Model, qualified_name: str) -> Feature:
    item = model[qualified_name]
    assert isinstance(item, Feature)
    return item


def condition(behavior: Behavior) -> Any:
    """Returns the condition of a require, typed loosely so that tests can reach into it."""
    assert isinstance(behavior, Require)
    return behavior.condition


def path(model: Model, origin: str, *names: str) -> Path:
    structure = model.structure(origin)
    steps = []
    for name in names:
        step = FeatureStep(structure.feature(name))
        steps.append(step)
        if isinstance(step.type, Structure):
            structure = step.type
    return Path(model.structure(origin), tuple(steps))


def test_declarations() -> None:
    model = compiled()
    bike = model.structure("Bike")
    assert model.root.feature("bike").type is bike
    assert (bike.feature("bags").min, bike.feature("bags").max) == (0, 4)
    assert bike.feature("weight").type == Numerical(digits=2, unit="kg", min=Decimal(0), max=Decimal(100))
    assert bike.feature("exact").type == Numerical(digits=8)
    assert bike.feature("stand").type == Boolean()
    assert bike.feature("note").type == Textual()
    size = model.enumeration("Size")
    assert size.option("large").value("volume") == Decimal(5)
    assert size.option("large").value("tint") is option(model, "Color.Blue")
    assert bike.feature("color").owner is bike


def test_cardinalities() -> None:
    model = compiled(model="product { Bag a\n 2 Bag b\n 1.. Bag c\n 0..* Bag d }\nstructure Bag { }")
    assert [(f.min, f.max) for f in model.root.features] == [(1, 1), (2, 2), (1, None), (0, None)]


def test_types_may_be_used_before_and_across_sources() -> None:
    result = compile(parse("product { Bike bike }"), parse("structure Bike { Color color }\nenumeration Color { Red }"))
    assert result.ok
    assert result.model.structure("Bike").feature("color").type is result.model.enumeration("Color")


def test_relative_and_rooted_paths() -> None:
    model = compiled("behavior Bag { require size = large || root.bike.color = Red }")
    either = condition(model.behaviors[0])
    assert isinstance(either, Or)
    operands: tuple[Any, ...] = either.operands
    relative, rooted = (compare.left.path for compare in operands)
    assert relative.origin is model.structure("Bag") and str(relative) == "size"
    assert rooted.origin is model.root and rooted.rooted and str(rooted) == "root.bike.color"


def test_options_resolve_against_the_compared_or_assigned_type() -> None:
    model = compiled("behavior Bike {\n default color = Blue\n require bags.size != small\n}")
    default, require = model.behaviors
    assert isinstance(default, Default) and default.value == Constant(option(model, "Color.Blue"))
    assert condition(require).right == Constant(option(model, "Size.small"))


def test_qualified_options_and_their_attribute_values_are_constants() -> None:
    model = compiled("behavior Bike { require weight > Size.large.volume }")
    assert condition(model.behaviors[0]).right == Constant(Decimal(5))


def test_attribute_steps_and_indices() -> None:
    model = compiled("behavior Bike { require bags[last-1..last].size.volume > bags[0].size.volume }")
    compare = condition(model.behaviors[0])
    left = compare.left.path
    assert left.steps[0] == FeatureStep(feature(model, "Bike.bags"), Index(-2, -1))
    assert isinstance(left.steps[-1], AttributeStep) and left.is_range
    assert compare.right.path.steps[0].index == Index(0, 0)


def test_definitions_are_substituted_in_order_and_scoped_to_their_block() -> None:
    model = compiled(
        "behavior Bike {\n"
        " define half = weight / 2\n"
        " define quarter = half / 2\n"
        " require quarter < 10\n"
        " condition stand = true { define b = bags\n require count(b) > 1 }\n"
        "}"
    )
    first, second = model.behaviors
    quarter = condition(first).left
    assert isinstance(quarter, Binary) and isinstance(quarter.left, Binary)
    assert second.conditions == (Compare(CompareOp.EQ, PathAccess(path(model, "Bike", "stand")), Constant(True)),)
    assert errors("behavior Bike {\n condition stand = true { define b = bags }\n require count(b) > 1\n}")


def test_nested_conditions_and_explanations_are_inherited() -> None:
    model = compiled(
        'behavior Bike {\n explanation "why" condition stand = true {\n'
        "  condition color = Red\n  require weight > 1\n }\n}"
    )
    [require] = model.behaviors
    assert require.explanation == "why"
    conditions: tuple[Any, ...] = require.conditions
    assert [str(c.left.path) for c in conditions] == ["stand", "color"]


def test_conditions() -> None:
    model = compiled("behavior Bike {\n require 1 < weight <= 5\n require note\n require !stand\n}")
    chain, defined, negation = (condition(behavior) for behavior in model.behaviors)
    assert isinstance(chain, And)
    assert [c.op for c in chain.operands if isinstance(c, Compare)] == [CompareOp.LT, CompareOp.LE]
    assert defined == IsDefined(PathAccess(path(model, "Bike", "note")))
    assert negation == Not(IsDefined(PathAccess(path(model, "Bike", "stand"))))


def test_text_constants_and_negative_numbers() -> None:
    model = compiled('behavior Bike {\n require note = "hello"\n imply exact = -3\n}')
    require, imply = model.behaviors
    assert condition(require).right == Constant("hello")
    assert isinstance(imply, Imply) and imply.value == Constant(Decimal(-3))


def test_combinations() -> None:
    model = compiled("behavior Bike {\n combinations (color stand)\n allow (Red -*-)\n forbid ((Red, Blue) false)\n}")
    [table] = model.behaviors
    assert isinstance(table, Combinations) and len(table.rows) == 2
    assert table.rows[0].cells[1] is None
    red, blue = model.enumeration("Color").options
    assert [atom.value for atom in table.rows[1].cells[0] or ()] == [Constant(red), Constant(blue)]


def test_derivation_tables_are_lowered_per_row_and_column() -> None:
    model = compiled(
        "behavior Bike {\n condition stand = true\n require (weight) condition (color)\n  (10) (Red)\n  (20) (-*-)\n"
        " default (color, stand)\n  (Blue, false)\n}"
    )
    first, second, color, stand = model.behaviors
    weight = PathAccess(path(model, "Bike", "weight"))
    assert len(first.conditions) == 2 and condition(first) == Compare(CompareOp.EQ, weight, Constant(Decimal(10)))
    assert len(second.conditions) == 1 and condition(second) == Compare(CompareOp.EQ, weight, Constant(Decimal(20)))
    assert isinstance(color, Default) and color.value == Constant(option(model, "Color.Blue"))
    assert isinstance(stand, Default) and stand.value == Constant(False)


def test_visibility() -> None:
    model = compiled("behavior Bike {\n hide color Red\n readonly weight\n}")
    hide, readonly = model.behaviors
    assert isinstance(hide, Visibility) and hide.options == (option(model, "Color.Red"),)
    assert isinstance(readonly, Visibility) and readonly.options == ()
    assert errors("behavior Bike { hide color Red Blue }") == ["cannot hide all options of Color"]
    assert errors("behavior Bike { readonly color Red }") == ["options can only be hidden, not made read only"]


def test_tests() -> None:
    model = compiled("test Bike {\n define c = color\n set c = Red\n isAvailable bags[0].size = small\n}")
    [test] = model.tests
    assert test.origin is model.structure("Bike")
    assert test.steps[0] == SetValue(path(model, "Bike", "color"), Constant(option(model, "Color.Red")))
    assert isinstance(test.steps[1], IsAvailable)
    assert errors("test Bike { isAvailable weight = 3 }") == []
    assert errors("test Bike { isBlocked weight }") == ["isBlocked needs a value unless the path holds instances"]
    assert errors("test Bike { isBlocked bags[1] }") == []


def test_visibility_tests() -> None:
    model = compiled("test Bike {\n isHidden color = Red\n isHidden weight\n isReadonly weight\n}")
    hidden, feature, readonly = model.tests[0].steps
    assert hidden == IsHidden(path(model, "Bike", "color"), Constant(option(model, "Color.Red")))
    assert feature == IsHidden(path(model, "Bike", "weight"))
    assert readonly == IsReadonly(path(model, "Bike", "weight"))
    assert errors("test Bike { isHidden weight = 3 }") == [
        "isHidden with an option needs a path to an enumeration feature"
    ]


def test_errors_skip_the_statement_and_keep_the_rest() -> None:
    result = compile_text(BIKE + "behavior Bike {\n require colour = Red\n require weight > 1\n}")
    assert [str(d) for d in result.diagnostics] == ["22:10: error: Bike has no feature colour"]
    assert len(result.model.behaviors) == 1


def test_declaration_errors() -> None:
    assert errors("structure Bike { }") == ["the type Bike is already defined"]
    assert errors("structure Car { Wheel wheel }") == ["the type Wheel is not defined"]
    assert errors("structure Car { Color c\n Color c }") == ["the feature c is already defined"]
    assert errors("enumeration bool { yes }") == ["bool is a predefined type"]
    assert errors("enumeration Empty { attribute num x }") == ["the enumeration Empty needs at least one option"]
    assert errors("enumeration E { attribute num x\n a = (1 2) }") == ["the option a has 2 values for 1 attributes"]
    assert errors("enumeration E { attribute Bike x\n a }") == ["an attribute cannot have the structure type Bike"]
    assert errors("product { }") == ["the product is already defined"]


def test_statement_errors() -> None:
    assert errors("behavior Color { }") == ["Color is an enumeration, not a structure"]
    assert errors("behavior Bike { require bags[4].size = small }") == ["the index 4 exceeds the maximum cardinality 4"]
    assert errors("behavior Bike { imply color.x = Red }") == ["Color has no attribute x"]
    assert errors("behavior Bike { imply bags.size.volume = 1 }") == ["cannot assign to an attribute"]
    assert errors("behavior Bike { imply this = 1 }") == ["cannot assign to the origin structure itself"]
    assert errors("behavior Bike { require sqrt(1, 2) > 0 }") == ["sqrt expects 1 arguments but got 2"]
    assert errors("behavior Bike { default/0 color = Red }") == ["the priority must be at least 1"]
    table = "behavior Bike {\n combinations (color stand)\n allow (Red)\n}"
    assert errors(table) == ["the row has 1 cells for 2 columns"]


def test_syntax_errors_are_reported_and_compilation_continues() -> None:
    result = compile_text(BIKE + "behavior Bike { require = }\nbehavior Bike { require weight > 1 }")
    assert not result.ok
    assert [type(b) for b in result.model.behaviors] == [Require]
