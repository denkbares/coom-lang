"""Directives and hidden options that visibility behaviors apply to configurations."""

from coom.compiler import compile_text
from coom.configuration import Configuration, Instance, visibilities
from coom.configuration.visibility import merge
from coom.model import Directive, Model

MODEL = """
product { Bike bike }
structure Bike {
    Color color
    0..3 Bag bags
    0..1 num weight
    bool sporty
    Frame frame
}
structure Bag {
    Size size
    bool closed
}
structure Frame { Color color }
enumeration Color { Red; Green; Blue }
enumeration Size { small; large }
behavior Bike {
    hide bags[1]
    readonly bags[last].size
    hide color Blue Green
    readonly frame
    hide frame.color
    condition weight > 10
    hide sporty
}
behavior Bag {
    condition size = large
    readonly closed
}
"""


def model_of(text: str) -> Model:
    result = compile_text(text)
    assert result.ok, "\n".join(map(str, result.diagnostics))
    return result.model


def bike_with_bags(*sizes: str, weight: int | None = None) -> tuple[Configuration, Instance]:
    configuration = Configuration(model_of(MODEL))
    configuration.add_required()
    bike = configuration.root.get("bike")
    assert isinstance(bike, Instance)
    bike.set("color", "Red")
    for size in sizes:
        bag = bike.add("bags")
        assert isinstance(bag, Instance)
        bag.set("size", size)
    if weight is not None:
        bike.set("weight", weight)
    return configuration, bike


def bag(bike: Instance, index: int) -> Instance:
    value = bike.get("bags", index)
    assert isinstance(value, Instance)
    return value


def test_merge_keeps_the_most_restrictive_directive() -> None:
    assert merge() is None
    assert merge(None, Directive.READONLY) is Directive.READONLY
    assert merge(Directive.HIDE, Directive.READONLY, None) is Directive.HIDE


def test_indexed_targets_address_single_slots() -> None:
    configuration, bike = bike_with_bags("small", "small", "small")
    result = visibilities(configuration)
    assert result.directive(bike, "bags", 0) is None
    assert result.directive(bike, "bags", 1) is Directive.HIDE
    assert result.directive(bike, "bags") is Directive.HIDE


def test_indices_from_the_end_follow_the_extent() -> None:
    configuration, bike = bike_with_bags("small", "small")
    result = visibilities(configuration)
    assert result.directive(bag(bike, 1), "size") is Directive.READONLY
    assert result.directive(bag(bike, 0), "size") is None


def test_hidden_options_leave_the_feature_visible() -> None:
    configuration, bike = bike_with_bags()
    result = visibilities(configuration)
    assert result.directive(bike, "color") is None
    assert {option.name for option in result.hidden_options(bike, "color")} == {"Blue", "Green"}
    assert result.hidden_options(bike, "sporty") == frozenset()


def test_instances_pass_their_directive_to_their_values() -> None:
    configuration, bike = bike_with_bags("small", "small")
    result = visibilities(configuration)
    frame = bike.get("frame")
    assert isinstance(frame, Instance)
    assert result.directive(frame, "color") is Directive.HIDE
    assert result.effective(frame, "color") is Directive.HIDE
    hidden_bag = bag(bike, 1)
    assert result.directive(hidden_bag, "closed") is None
    assert result.effective(hidden_bag, "closed") is Directive.HIDE
    assert result.effective(bag(bike, 0), "closed") is None


def test_preconditions_must_be_definitely_true() -> None:
    open_weight, bike = bike_with_bags()
    assert visibilities(open_weight).directive(bike, "sporty") is None
    light, bike = bike_with_bags(weight=5)
    assert visibilities(light).directive(bike, "sporty") is None
    heavy, bike = bike_with_bags(weight=20)
    assert visibilities(heavy).directive(bike, "sporty") is Directive.HIDE


def test_preconditions_are_evaluated_per_origin_instance() -> None:
    configuration, bike = bike_with_bags("small", "large")
    result = visibilities(configuration)
    assert result.directive(bag(bike, 0), "closed") is None
    assert result.directive(bag(bike, 1), "closed") is Directive.READONLY
