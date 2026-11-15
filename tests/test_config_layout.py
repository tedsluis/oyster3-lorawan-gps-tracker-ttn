import pytest

from oyster3.downlinks import (
    SPEC_LENGTHS,
    load_config,
    name_offset,
    validate_config,
    validate_layout,
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
