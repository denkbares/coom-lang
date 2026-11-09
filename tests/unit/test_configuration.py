"""Building, navigating and serializing configurations."""

import json
from decimal import Decimal

import pytest

from coom.compiler import compile_text
from coom.configuration import Configuration, Instance, Role
from coom.model import Model

MODEL = """
product {
    Bike bike
    0..1 Bike spare
}
structure Bike {
    Color color
    0..3 Bag bags
    num.## /kg 0-100 weight
    bool stand
    0..1 string note
}
structure Bag { 0..2 Size sizes }
enumeration Color { Red; Blue }
enumeration Size { small; large }
"""


@pytest.fixture
def model() -> Model:
    result = compile_text(MODEL)
    assert result.ok, result.diagnostics
    return result.model


def bike_of(configuration: Configuration) -> Instance:
    bike = configuration["bike"]
    assert isinstance(bike, Instance)
    return bike


def test_required_instances_are_created(model: Model) -> None:
    configuration = Configuration(model)
    configuration.add_required()
    bike = bike_of(configuration)
    assert bike.type is model.structure("Bike") and bike.parent is configuration.root
    assert configuration["spare"] is None and bike.path == "bike"
    assert [instance.path for instance in configuration.instances()] == ["", "bike"]


def test_values_are_converted_to_the_type_of_the_feature(model: Model) -> None:
    bike = bike_of(_configured(model))
    assert bike["color"] is model.enumeration("Color").option("Red")
    assert bike["weight"] == Decimal("12.35")
    assert bike.get("stand") is True
    assert bike.set("weight", 0.1) == Decimal("0.10")
    assert bike.set("stand", "false") is False


def test_wrong_values_and_slots_are_rejected(model: Model) -> None:
    configuration = Configuration(model)
    configuration.add_required()
    bike = bike_of(configuration)
    with pytest.raises(TypeError):
        bike.set("weight", "heavy")
    with pytest.raises(TypeError):
        bike.set("stand", 1)
    with pytest.raises(KeyError):
        bike.set("color", "Green")
    with pytest.raises(IndexError):
        bike.set("bags", configuration.new("Bag"), 3)
    with pytest.raises(ValueError):
        configuration.root.set("spare", bike)


def test_multi_valued_features_and_navigation(model: Model) -> None:
    configuration = _configured(model)
    bike = bike_of(configuration)
    first, second = bike.values("bags")
    assert isinstance(second, Instance) and second.path == "bike.bags[1]"
    assert second.root is configuration.root and second.parent is bike
    assert bike.last_index("bags") == 1 and bike["bags"] == (first, second)
    assert configuration["bike.bags[1].sizes"] == (model.enumeration("Size").option("large"),)
    assert [instance.path for instance in configuration.instances("Bag")] == ["bike.bags[0]", "bike.bags[1]"]
    bike.remove("bags", 0)
    assert isinstance(first, Instance) and first.parent is None
    assert bike.assignments("bags").keys() == {1}


def test_roles_are_kept_per_slot(model: Model) -> None:
    configuration = _configured(model)
    bike = bike_of(configuration)
    bike.set("note", "fast", role=Role.DEFAULT)
    assignment = bike.assignment("note")
    color = bike.assignment("color")
    assert assignment is not None and assignment.role is Role.DEFAULT
    assert color is not None and color.role is Role.SELECTED


def test_json_round_trip(model: Model) -> None:
    configuration = _configured(model)
    bike_of(configuration).set("bags", configuration.new("Bag"), 2)
    bike_of(configuration).remove("bags", 1)
    data = configuration.to_json()
    assert data["bike"]["color"] == "Red" and data["bike"]["stand"] is True
    assert data["bike"]["bags"][1] is None and data["bike"]["bags"][0]["@id"] == "Bag#1"
    assert Configuration.from_json(model, data).to_json() == data
    assert Configuration.loads(model, configuration.dumps()).to_json() == data


def test_json_numbers_stay_exact(model: Model) -> None:
    text = json.dumps({"bike": {"weight": 99.99, "stand": "true"}})
    bike = bike_of(Configuration.loads(model, text))
    assert bike["weight"] == Decimal("99.99") and bike["stand"] is True


def _configured(model: Model) -> Configuration:
    configuration = Configuration(model)
    configuration.add_required()
    bike = bike_of(configuration)
    bike.set("color", "Red")
    bike.set("weight", "12.345")
    bike.set("stand", True)
    bike.add("bags")
    second = bike.add("bags")
    assert isinstance(second, Instance)
    second.add("sizes", "large")
    return configuration
