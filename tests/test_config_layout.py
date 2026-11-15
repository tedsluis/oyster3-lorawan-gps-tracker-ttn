import pytest

from oyster3.downlinks import (
    SPEC_LENGTHS,
    load_config,
    name_offset,
    validate_config,
    validate_layout,
    validate_types,
)
from tests.conftest import REPO


@pytest.fixture(scope="module")
def config():
    return load_config(REPO / "config.yaml")


@pytest.mark.parametrize(
    "name, expected",
    [
        ("0.0 - 0.6 Downlink sequence number", (0, 7)),
        ("0.7 Reserved, set to zero", (7, 1)),
        ("1.2 - 2.1 Offset of normal time zone", (10, 8)),
        ("1 Max time between fix attempts", (8, 8)),
        ("2 - 10 Uplink channel mask", (16, 72)),
        ("7.5 - 8.7 Time between extra end-of-trip heartbeats", (61, 11)),
    ],
)
def test_name_offset(name, expected):
    assert name_offset(name) == expected


def test_config_yaml_matches_the_spec_layout(config):
    assert validate_config(config) == []


def test_config_contains_every_downlink_with_spec_length(config):
    assert sorted(config) == sorted(SPEC_LENGTHS)


def test_validator_detects_wrong_offset_overlap_and_gap():
    fields = [
        {"name": "0.0 - 0.6 Sequence", "byte": 0, "bit": 0, "length": 7},
        {"name": "0.7 Reserved", "byte": 0, "bit": 7, "length": 1},
        {"name": "1.0 Reset all", "byte": 1, "bit": 0, "length": 1},
        {"name": "1.1 Reset battery critical", "byte": 1, "bit": 0, "length": 1},
    ]
    problems = " ".join(validate_layout(34, fields))
    assert "name says bit 9" in problems
    assert "overlaps" in problems
    assert "not covered" in problems


def test_validator_detects_inconsistent_types():
    fields = [
        {"name": "5 Maximum Tx power limit, signed", "type": "integer", "byte": 5, "length": 1},
        {"name": "6.6 - 6.7 Reserved", "type": "boolean", "byte": 6, "bit": 6, "length": 2},
        {"name": "7 Something", "type": "float", "byte": 7, "length": 1},
        {"name": "1.0 Flag", "type": "boolean", "byte": 1, "bit": 0, "length": 1, "endian": "big"},
    ]
    problems = " ".join(validate_types(9, fields))
    assert "use type signed-integer" in problems
    assert "boolean fields must be 1 bit" in problems
    assert "unknown type" in problems
    assert "endian only applies" in problems


def test_signed_reserved_and_joineui_fields_are_typed(config):
    by_name = {(port, f["name"][:9]): f for port, fields in config.items() for f in fields}
    assert by_name[(6, "6.0 - 6.4")]["type"] == "signed-integer"
    assert by_name[(9, "5 Maximum")]["type"] == "signed-integer"
    assert by_name[(34, "1.2 - 1.7")]["type"] == "integer"
    assert by_name[(8, "1 - 8 Joi")]["endian"] == "big"
