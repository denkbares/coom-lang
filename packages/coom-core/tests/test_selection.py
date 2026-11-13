"""Selectors of entities by name, glob and location."""

import pytest

from coom.model import (
    ROOT_NAME,
    Compare,
    CompareOp,
    Constant,
    Enumeration,
    Feature,
    FeatureStep,
    Model,
    Path,
    PathAccess,
    Require,
    SetValue,
    Span,
    Structure,
    options,
    testing,
)
from coom.model.json import write_entity, write_model
from coom.model.selection import EntityKind, SelectionError, entity_name, kind, select


@pytest.fixture
def model() -> Model:
    color = Enumeration(name="Color", options=options("Red", "Yellow"))
    bike = Structure(name="Bike")
    root = Structure(name=ROOT_NAME, features=(Feature(name="bike", type=bike),))
    bike.features = (Feature(name="color", type=color), Feature(name="size", type=color, min=0, max=None))
    red = Constant(color.option("Red"))
    require = Require(
        origin=bike,
        condition=Compare(CompareOp.EQ, PathAccess(Path(bike, (FeatureStep(bike.features[0]),))), red),
        span=Span(5, 4, 5, 30, "models/Bike.model"),
    )
    test = testing.TestCase(
        origin=root,
        steps=(SetValue(Path(root, (FeatureStep(root.features[0]), FeatureStep(bike.features[0]))), red),),
        span=Span(1, 0, 4, 1, "models/Bike.test"),
    )
    return Model(root=root, structures=(bike,), enumerations=(color,), behaviors=(require,), tests=(test,))


def names(entities: tuple[object, ...]) -> list[str]:
    return [entity_name(entity) for entity in entities]  # type: ignore[arg-type]


def test_entities_are_named_by_qualified_name_or_location(model: Model) -> None:
    assert names(tuple(model.entities())) == [
        ":root",
        ":root.bike",
        "Bike",
        "Bike.color",
        "Bike.size",
        "Color",
        "Color.Red",
        "Color.Yellow",
        "@Bike.model:5",
        "@Bike.test:1",
    ]
    assert [kind(entity) for entity in model.entities()][-2:] == [EntityKind.BEHAVIOR, EntityKind.TEST]


def test_every_name_selects_its_entity(model: Model) -> None:
    for entity in model.entities():
        assert select(model, [entity_name(entity)]) == (entity,)


def test_globs_select_in_declaration_order(model: Model) -> None:
    assert names(select(model, ["Color.*", "Bike.*"])) == ["Bike.color", "Bike.size", "Color.Red", "Color.Yellow"]
    assert select(model, ["Nothing.*"]) == ()


def test_locations_select_by_file_and_line(model: Model) -> None:
    assert names(select(model, ["@Bike.test:3"])) == ["@Bike.test:1"]
    assert names(select(model, ["@models/Bike.test:4"])) == ["@Bike.test:1"]
    assert names(select(model, ["@Bike.model"])) == ["@Bike.model:5"]


def test_unknown_names_suggest_the_nearest(model: Model) -> None:
    with pytest.raises(SelectionError, match=r"unknown item Bike\.colour, did you mean Bike\.color"):
        select(model, ["Bike.colour"])
    with pytest.raises(SelectionError, match=r"no behavior or test at Bike\.test:7, did you mean @Bike\.test:1"):
        select(model, ["@Bike.test:7"])
    with pytest.raises(SelectionError, match=r"no behavior or test in Bike\.tset, did you mean Bike\.test"):
        select(model, ["@Bike.tset"])


def test_json_nests_members_and_refers_by_name(model: Model) -> None:
    whole = write_model(model)
    assert whole["structures"][0]["features"][1] == write_entity(model["Bike.size"])
    assert write_entity(model["Bike.size"]) == {
        "kind": "feature",
        "name": "Bike.size",
        "structure": "Bike",
        "min": 0,
        "max": None,
        "type": {"type": "enumeration", "name": "Color"},
        "location": None,
    }
    [step] = write_entity(model.tests[0])["steps"]
    assert step == {
        "step": "set",
        "path": {
            "origin": ROOT_NAME,
            "rooted": False,
            "steps": [{"feature": ":root.bike", "index": None}, {"feature": "Bike.color", "index": None}],
        },
        "value": {"node": "option", "option": "Color.Red"},
    }
    assert write_entity(model.behaviors[0])["location"] == {
        "source": "models/Bike.model",
        "line": 5,
        "column": 5,
        "endLine": 5,
        "endColumn": 31,
    }
