"""Downlink configuration (config.yaml): loading, validation and encoding.

Field positions follow the Digital Matter spec: ``byte`` and ``bit`` address bit ``bit``
(0 = least significant) of byte ``byte``; ``length`` is in bits when ``bit`` is given and in
bytes otherwise.
"""

import re

import yaml

# Payload length in bytes per downlink port (Integration spec rev. 1.3, §3.4-3.5).
SPEC_LENGTHS = {
    1: 8, 2: 9, 3: 7, 4: 8, 5: 8, 6: 10, 7: 11, 8: 9, 9: 7, 10: 9, 11: 11, 12: 3,
    30: 7, 31: 2, 32: 4, 33: 1, 34: 2, 35: 6,
}
VALID_PORTS = tuple(SPEC_LENGTHS)
FIELD_TYPES = ("integer", "signed-integer", "boolean")

_OFFSET = re.compile(r"^(\d+)(?:\.(\d))?(?:\s*-\s*(\d+)(?:\.(\d))?)?\s")


def load_config(path="config.yaml"):
    """Return {port: [field, ...]} from config.yaml."""
    with open(path) as handle:
        raw = yaml.safe_load(handle)
    config = {}
    for key, fields in raw.get("config", {}).items():
        config[int(key.replace("downlink", ""))] = fields
    return config


def name_offset(name):
    """Start bit and size in bits as written at the start of a field name, e.g. '1.2 - 2.1'."""
    match = _OFFSET.match(name)
    if not match:
        raise ValueError(f"field name does not start with an offset: {name!r}")
    first_byte, first_bit, last_byte, last_bit = match.groups()
    first_byte = int(first_byte)
    if last_byte is None:
        if first_bit is None:
            return first_byte * 8, 8
        return first_byte * 8 + int(first_bit), 1
    last_byte = int(last_byte)
    if (first_bit is None) != (last_bit is None):
        raise ValueError(f"mixed byte and bit offsets in field name: {name!r}")
    if first_bit is None:
        return first_byte * 8, (last_byte - first_byte + 1) * 8
    start = first_byte * 8 + int(first_bit)
    return start, last_byte * 8 + int(last_bit) - start + 1


def field_span(field):
    """Start bit and size in bits as configured by byte/bit/length."""
    if field.get("bit") is None:
        return field["byte"] * 8, field["length"] * 8
    return field["byte"] * 8 + field["bit"], field["length"]


def validate_layout(port, fields):
    """Return a list of problems with the field layout of one downlink."""
    problems = []
    if port not in SPEC_LENGTHS:
        return [f"downlink{port}: unknown downlink port"]
    used = {}
    for field in fields:
        name = field["name"]
        bit = field.get("bit")
        if bit is not None and not 0 <= bit <= 7:
            problems.append(f"downlink{port}: {name[:40]!r}: bit must be 0-7, got {bit}")
        start, size = field_span(field)
        try:
            expected = name_offset(name)
        except ValueError as error:
            problems.append(f"downlink{port}: {error}")
        else:
            if expected != (start, size):
                problems.append(
                    f"downlink{port}: {name[:40]!r}: name says bit {expected[0]} size "
                    f"{expected[1]}, byte/bit/length give bit {start} size {size}"
                )
        for position in range(start, start + size):
            if position in used:
                problems.append(
                    f"downlink{port}: {name[:40]!r} overlaps {used[position][:40]!r} at bit "
                    f"{position}"
                )
                break
            used[position] = name
    total_bits = SPEC_LENGTHS[port] * 8
    gaps = [position for position in range(total_bits) if position not in used]
    if gaps:
        problems.append(f"downlink{port}: bits not covered by any field: {gaps}")
    outside = [position for position in used if position >= total_bits]
    if outside:
        problems.append(
            f"downlink{port}: fields exceed the spec length of {SPEC_LENGTHS[port]} bytes"
        )
    return problems


def validate_types(port, fields):
    """Return a list of problems with field types and attributes of one downlink."""
    problems = []
    for field in fields:
        name = field["name"]
        label = f"downlink{port}: {name[:40]!r}"
        field_type = field.get("type")
        _, size = field_span(field)
        if field_type not in FIELD_TYPES:
            problems.append(f"{label}: unknown type {field_type!r}")
        if field_type == "boolean" and size != 1:
            problems.append(f"{label}: boolean fields must be 1 bit, use integer for {size} bits")
        if "signed" in name and field_type != "signed-integer":
            problems.append(f"{label}: the spec says signed, use type signed-integer")
        if field.get("endian", "little") not in ("little", "big"):
            problems.append(f"{label}: endian must be 'little' or 'big'")
        if field.get("endian") == "big" and field.get("bit") is not None:
            problems.append(f"{label}: endian only applies to whole-byte fields")
        low, high = field.get("min"), field.get("max")
        if low is not None and high is not None and low > high:
            problems.append(f"{label}: min {low} is greater than max {high}")
    return problems


def validate_config(config):
    problems = []
    missing = sorted(set(SPEC_LENGTHS) - set(config))
    if missing:
        problems.append(f"downlinks missing from config: {missing}")
    for port, fields in config.items():
        problems.extend(validate_layout(port, fields))
        problems.extend(validate_types(port, fields))
    return problems


def _normalise(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        if text.endswith("B"):
            return int(text[:-1], 2)
        if text.endswith("H"):
            return int(text[:-1], 16)
    return value


def non_default_fields(fields):
    """Fields whose value differs from their 'default' (the sequence number has no default)."""
    return [
        field
        for field in fields
        if "default" in field and _normalise(field["value"]) != _normalise(field["default"])
    ]
