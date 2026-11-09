"""The JSON form of configurations.

One object per instance with a key per feature that holds a value. A single valued feature maps to its value, a multi
valued one to an array indexed by slot with null for an empty slot. Instances are nested objects with their name under
"@id", options are written by name, truth values as true or false, and numbers as JSON numbers unless a float would
change them, in which case they are written as strings. Roles are not part of the form.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from coom.configuration._configuration import Configuration, Instance, Value
from coom.model import Feature, Option, Structure


def write(instance: Instance) -> dict[str, Any]:
    """Returns the JSON object of an instance and everything below it."""
    result: dict[str, Any] = {"@id": instance.name}
    for feature in instance.type.features:
        slots = instance.assignments(feature)
        if not slots:
            continue
        if feature.is_multiple:
            result[feature.name] = [
                _write_value(slots[index].value) if index in slots else None for index in range(max(slots) + 1)
            ]
        else:
            result[feature.name] = _write_value(slots[0].value)
    return result


def _write_value(value: Value) -> Any:
    match value:
        case Instance():
            return write(value)
        case Option():
            return value.name
        case Decimal():
            if value == value.to_integral_value():
                return int(value)
            # a float carries the exact decimal only while its shortest form is that decimal
            return float(value) if Decimal(repr(float(value))) == value else str(value)
        case _:
            return value


def read(instance: Instance, data: Mapping[str, Any]) -> None:
    """Assigns the values of a JSON object to an instance, creating the instances it nests."""
    for name, value in data.items():
        if name == "@id":
            continue
        feature = instance.type.feature(name)
        entries = value if isinstance(value, list) else [value]
        for index, entry in enumerate(entries):
            if entry is not None:
                instance.set(feature, _read_value(instance.configuration, feature, entry), index)


def _read_value(configuration: Configuration, feature: Feature, entry: Any) -> Any:
    if isinstance(feature.type, Structure) and isinstance(entry, Mapping):
        child = configuration.new(feature.type, entry.get("@id"))
        read(child, entry)
        return child
    return entry
