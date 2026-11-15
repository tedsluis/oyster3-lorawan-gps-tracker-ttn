import pytest

from oyster3.downlinks import load_config, non_default_fields
from tests.conftest import REPO


@pytest.fixture(scope="module")
def config():
    return load_config(REPO / "config.yaml")


def test_every_field_except_the_sequence_number_has_a_default(config):
    for port, fields in config.items():
        for field in fields:
            if field["name"].startswith("0.0 - 0.6 Downlink sequence number"):
                assert "default" not in field
            else:
                assert "default" in field, (port, field["name"])


def test_shipped_config_contains_only_defaults(config):
    for port, fields in config.items():
        assert non_default_fields(fields) == [], port


@pytest.mark.parametrize(
    "port, prefix, expected",
    [
        (5, "6 Required speed accuracy", 28),  # 10 km/h, LSb 0.36 km/h
        (10, "4 V3 Position Uplink", 0),  # Auto
        (10, "5 V3 Position Uplink", 0),  # Auto
        (10, "6 GNSS fix every nth heartbeat", 1),
        (32, "1 Accelerometer wakeup threshold", 6),  # 94 mG
    ],
)
def test_audit_f26_values_are_the_spec_defaults(config, port, prefix, expected):
    field = next(f for f in config[port] if f["name"].startswith(prefix))
    assert field["value"] == expected
    assert field["default"] == expected


def test_non_default_values_are_reported():
    fields = [
        {"name": "1 A", "type": "integer", "value": 3, "default": 3},
        {"name": "2 B", "type": "integer", "value": "0101B", "default": 5},
        {"name": "3 C", "type": "boolean", "value": True, "default": False},
        {"name": "0.0 - 0.6 Downlink sequence number", "type": "integer", "value": 9},
    ]
    assert [f["name"] for f in non_default_fields(fields)] == ["3 C"]
