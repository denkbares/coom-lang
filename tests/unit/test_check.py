"""Type rules, range and structure checks, and profile detection."""

import pytest

from coom.check import Profile, detect_profiles
from coom.compiler import compile_text

BIKE = """
product {
    Bike bike
}
structure Bike {
    Color color
    Size size
    0..4 Bag bags
    num 0-100 weight
    num price
    bool stand
    string note
}
structure Bag { Size size }
enumeration Color { Red; Blue }
enumeration Size {
    attribute num 0-10 volume
    small = (1)
    large = (5)
}
"""


def errors(text: str, model: str = BIKE) -> list[str]:
    return [diagnostic.message for diagnostic in compile_text(model + text).diagnostics]


def profiles(text: str, model: str = BIKE) -> set[str]:
    result = compile_text(model + text)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    return set(detect_profiles(result.model))


@pytest.mark.parametrize(
    "statement",
    [
        "require weight > price + 1",
        "require color = Red || size >= small",
        'require note = "x" && note < "y"',
        "require stand != false",
        "require sum(bags.size.volume) <= max(weight, price, 3)",
        "require count(bags) = 2 && min(bags.size) = small",
        "require bags.size = small",
        "imply price = sqrt(weight) + round(weight, 2)",
        'default note = "text"',
        "minimize price",
        "combinations (color weight)\n allow (Red <5)",
    ],
)
def test_well_typed_statements(statement: str) -> None:
    assert errors(f"behavior Bike {{\n {statement}\n}}") == []


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("require color = Size.small", "cannot compare an option of Color with an option of Size by ="),
        ("require weight = Color.Red", "cannot compare a number with an option of Color by ="),
        ('require weight = "5"', "cannot compare a number with a text by ="),
        ("require stand < true", "cannot compare a truth value with a truth value by <"),
        ("require bags.size = bags.size", "cannot compare two collections with each other"),
        ("require bags = this", "cannot compare a collection of instances of Bag with an instance of Bike by ="),
        ("imply price = bags.size.volume + 1", "arithmetic needs a single number, not a collection of numbers"),
        ("imply price = note + 1", "arithmetic needs a number, not a text"),
        ("imply price = sqrt(color)", "arithmetic needs a number, not an option of Color"),
        ("require sum(bags.size) > 1", "sum needs numbers"),
        ("require max(weight, color) > 1", "max needs values that can be ordered against each other"),
        ("imply color = Size.small", "cannot assign an option of Size to color, which holds Color"),
        ("imply price = bags.size.volume", "cannot assign a collection of numbers to price"),
        ("default weight = 200", "200 is outside the range num 0-100 of weight"),
        ("imply bags[0] = this", "cannot assign a value to the structure feature bags[0]"),
        ("minimize color", "minimize needs a numeric feature, not color"),
        ("require bags[3..1].size = small", "the index range [3..1] is empty"),
        ("combinations (color weight)\n allow (Red Size.small)", "cannot compare a number with an option of Size by ="),
    ],
)
def test_type_errors(statement: str, message: str) -> None:
    assert errors(f"behavior Bike {{\n {statement}\n}}") == [message]


def test_options_resolve_against_bool_by_quoted_names() -> None:
    assert errors('behavior Bike {\n condition stand = "true"\n default stand = "false"\n}') == []


def test_attribute_values_and_test_values_respect_ranges() -> None:
    assert errors("enumeration Tank { attribute num 0-5 liters\n big = (8) }") == [
        "8 is outside the range num 0-5 of the attribute liters"
    ]
    assert errors("test Bike { set weight = 101 }") == ["101 is outside the range num 0-100 of weight"]
    assert errors("test Bike { isAvailable color = Size.small }") == [
        "cannot assign an option of Size to color, which holds Color"
    ]


def test_structures_must_not_contain_themselves() -> None:
    model = "product { A a }\nstructure A { 0..1 B b }\nstructure B { 0..2 A a }"
    assert errors("", model) == ["the structure A contains itself through A.b > B.a"]


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [
        ("", {"CORE", "N-OUT", "C-USER"}),
        ("behavior Bike { imply price = weight * weight }", {"CORE", "N-OUT", "C-USER"}),
        ("behavior Bike { require weight > 2 * price }", {"CORE", "N-LIN", "C-USER"}),
        ("behavior Bike { require weight > price * price }", {"CORE", "N-FULL", "C-USER"}),
        ("behavior Bike { condition sqrt(weight) > 2\n require color = Red }", {"CORE", "N-FULL", "C-USER"}),
        ("behavior Bike { require count(bags) > 1 }", {"CORE", "N-LIN", "C-OPEN"}),
        ("behavior Bike { default color = Red }", {"CORE", "N-OUT", "C-USER", "D-BASE"}),
        ("behavior Bike { default/2 color = Red }", {"CORE", "N-OUT", "C-USER", "D-COND"}),
        ("behavior Bike { maximize price\n hide note }", {"CORE", "N-OUT", "C-USER", "O", "UI"}),
        ("test { }", {"CORE", "N-OUT", "C-USER", "TEST"}),
    ],
)
def test_profiles(behavior: str, expected: set[str]) -> None:
    assert profiles(behavior) == expected


def test_cardinality_profiles() -> None:
    structures = "structure Bag { }\nenumeration Color { Red }\n"
    assert profiles("", structures + "product { Color c }") == {"CORE"}
    assert profiles("", structures + "product { 2 Bag b }") == {"CORE", "C-FIX"}
    assert profiles("", structures + "product { 0..3 Bag b }") == {"CORE", "C-USER"}
    assert profiles("", structures + "product { 1..* Bag b }") == {Profile.CORE, Profile.C_OPEN}
