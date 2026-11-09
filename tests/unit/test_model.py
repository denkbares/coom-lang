"""Builds the C-OPEN CargoBike example by hand and navigates it."""

from decimal import Decimal

import pytest

from coom.model import (
    ROOT_NAME,
    Attribute,
    AttributeStep,
    Binary,
    BinaryOp,
    Call,
    Compare,
    CompareOp,
    Constant,
    Direction,
    Enumeration,
    Feature,
    FeatureStep,
    Function,
    Imply,
    Index,
    Model,
    Numerical,
    Optimize,
    Option,
    Path,
    PathAccess,
    Require,
    Structure,
    options,
    type_name,
    walk,
)


@pytest.fixture
def model() -> Model:
    color = Enumeration(name="Color", options=options("Green", "Blue", "Red"))
    max_weight = Attribute(name="maxWeight", type=Numerical())
    volume = Attribute(name="volume", type=Numerical())
    size = Enumeration(
        name="Size",
        attributes=(max_weight, volume),
        options=tuple(
            Option(name=name, values={max_weight: Decimal(w), volume: Decimal(v)})
            for name, w, v in [("small", 10, 12), ("medium", 15, 16), ("large", 25, 20)]
        ),
    )

    # Two phases, shells first, so features can refer to structures declared later.
    root = Structure(name=ROOT_NAME)
    cargo = Structure(name="CargoBike")
    bag = Structure(name="Bag")
    root.features = (Feature(name="cargoBike", type=cargo),)
    bag.features = (Feature(name="color", type=color), Feature(name="size", type=size))
    kg = Numerical(unit="kg")
    cargo.features = (
        Feature(name="totalWeight", type=kg),
        Feature(name="countBags", type=Numerical()),
        Feature(name="bags", type=bag, min=0, max=99),
    )

    bags = FeatureStep(cargo.feature("bags"))
    weights = Path(cargo, (bags, FeatureStep(bag.feature("size")), AttributeStep(max_weight)))
    total = Path(cargo, (FeatureStep(cargo.feature("totalWeight")),))
    count = Path(cargo, (FeatureStep(cargo.feature("countBags")),))
    behaviors = (
        Require(
            origin=cargo,
            condition=Compare(CompareOp.EQ, Call(Function.SUM, (PathAccess(weights),)), PathAccess(total)),
        ),
        Imply(origin=cargo, target=count, value=Call(Function.COUNT, (PathAccess(Path(cargo, (bags,))),))),
        Optimize(origin=cargo, direction=Direction.MINIMIZE, target=count),
    )
    return Model(root=root, structures=(cargo, bag), enumerations=(color, size), behaviors=behaviors)


def test_navigation(model: Model) -> None:
    bike = model.root.feature("cargoBike").type
    assert isinstance(bike, Structure)
    bags = bike.feature("bags")
    assert bags.owner is bike
    assert bags.is_optional and bags.is_multiple
    assert isinstance(bags.type, Structure)
    size = bags.type.feature("size").type
    assert isinstance(size, Enumeration)
    assert size.option("large").value("volume") == Decimal(20)
    assert size.option("medium").index == 1
    assert model["Size.large"] is size.option("large")
    assert model["Bag"] is bags.type
    assert model.features_of_type(bags.type) == (bags,)


def test_references(model: Model) -> None:
    require, imply, optimize = model.behaviors
    assert model.references(model["CargoBike.bags"]) == (require, imply)
    assert model.references(model["Size.maxWeight"]) == (require,)
    assert model.references(model["CargoBike.countBags"]) == (imply, optimize)
    assert model.behaviors_of(model.structure("CargoBike")) == model.behaviors
    assert model.behaviors_of(model.root) == ()


def test_paths(model: Model) -> None:
    require = model.behaviors[0]
    assert isinstance(require, Require)
    paths = [node for node in walk(require.condition) if isinstance(node, Path)]
    assert [str(path) for path in paths] == ["bags.size.maxWeight", "totalWeight"]
    assert paths[0].is_range and not paths[1].is_range
    assert type_name(paths[1].type) == "num /kg"
    bags = model.structure("CargoBike").feature("bags")
    single = Path(paths[0].origin, (FeatureStep(bags, Index(-2, -1)),), rooted=True)
    assert str(single) == "root.bags[last-1..last]"


def test_values_compare_by_content_and_ignore_spans(model: Model) -> None:
    one = Binary(BinaryOp.ADD, Constant(Decimal(1)), Constant(Decimal(2)))
    two = Binary(BinaryOp.ADD, Constant(Decimal(1)), Constant(Decimal(2), span=None))
    assert one == two and hash(one) == hash(two)
    assert Feature(name="x", type=Numerical()) != Feature(name="x", type=Numerical())


def test_repr_is_short(model: Model) -> None:
    assert repr(model["CargoBike.bags"]) == "<Feature CargoBike.bags: 0..99 Bag>"
    assert repr(model["CargoBike.totalWeight"]) == "<Feature CargoBike.totalWeight: num /kg>"
    assert repr(model) == "<Model 2 structures, 2 enumerations, 3 behaviors, 0 tests>"
