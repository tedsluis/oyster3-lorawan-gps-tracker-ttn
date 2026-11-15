import pytest

from oyster3.downlinks import encode_downlink, load_config, parse_value
from tests.conftest import REPO
from tests.test_downlink_encoder import run_cli, with_values


@pytest.fixture(scope="module")
def config():
    return load_config(REPO / "config.yaml")


@pytest.mark.parametrize(
    "port, prefix, value, message",
    [
        (9, "1 Days between network joins", 300, "does not fit"),  # was silently 300 & 0xFF
        (9, "1 Days between network joins", -1, "does not fit"),
        (9, "2.4 - 2.7 Initial frame repetitions", 0, "below the minimum 1"),
        (9, "2.4 - 2.7 Initial frame repetitions", 16, "above the maximum 15"),
        (6, "6.0 - 6.4 Satellite detection margin", -17, "does not fit"),
        (6, "6.0 - 6.4 Satellite detection margin", 16, "does not fit"),
        (4, "1.2 - 2.1 Offset of normal time zone", 128, "does not fit"),
        (8, "1 - 8 JoinEUI", "1FFFFFFFFFFFFFFFFH", "does not fit"),
        (7, "1.4 - 1.7 Maximum data rate", True, "must be a number"),
        (31, "1.0 Use GPS constellation", "10B", "boolean value"),  # was parsed as 2
        (31, "1.0 Use GPS constellation", 2, "boolean value"),
        (5, "3 Target accuracy", "twenty", "cannot parse"),
    ],
)
def test_invalid_values_are_rejected_with_the_field_name(config, port, prefix, value, message):
    fields = with_values(config[port], **{prefix: value})
    with pytest.raises(ValueError, match=message) as error:
        encode_downlink(port, fields)
    assert prefix[:20] in str(error.value)


def test_negative_values_in_signed_bit_fields_are_encoded(config):
    # Audit F16: negative signed values used to crash the encoder
    fields = with_values(config[4], **{"1.2 - 2.1 Offset of normal time zone": -4})
    assert encode_downlink(4, fields)[1] == (0b11111100 << 2) & 0xFF


@pytest.mark.parametrize(
    "value, field_type, expected",
    [
        (5, "integer", 5),
        ("0101B", "integer", 5),
        ("1F H", "integer", 31),
        (True, "boolean", 1),
        (0, "boolean", 0),
        ("70B3_D570H", "integer", 0x70B3D570),
    ],
)
def test_parse_value_accepts_documented_notations(value, field_type, expected):
    assert parse_value(value, field_type) == expected


def test_cli_reports_invalid_value_instead_of_sending_garbage(tmp_path, capsys):
    text = (REPO / "config.yaml").read_text()
    marker = "    - name: 2.4 - 2.7 Initial frame repetitions"
    head, tail = text.split(marker, 1)
    tail = tail.replace("      value: 1\n", "      value: 0\n", 1)
    path = tmp_path / "config.yaml"
    path.write_text(head + marker + tail)
    code, out = run_cli(["--downlink", "9", "--config", str(path)])
    assert code == 2
    assert "Byte Array" not in out
    assert "below the minimum 1" in capsys.readouterr().err


@pytest.mark.parametrize(
    "port, prefix, value",
    [
        (1, "1 Max time between fix attempts out of trip", 0),
        (1, "1 Max time between fix attempts out of trip", 128),
        (5, "1 Max time to wait for initial coarse", 128),
        (5, "1 Max time to wait for initial coarse", 44),
        (6, "1 V1 Daily GNSS on-time budget", 30),
        (6, "8 - 9 V1 Approximate maximum error", 5000),
        (6, "8 - 9 V1 Approximate maximum error", 3),
        (10, "3 Inactivity Alarm Heartbeat Period", 128),
    ],
)
def test_split_spec_ranges_are_enforced(config, port, prefix, value):
    # Review finding: ranges like 1-127 / 129-255 were not enforced (F16)
    fields = with_values(config[port], **{prefix: value})
    with pytest.raises(ValueError, match="is not allowed"):
        encode_downlink(port, fields)


@pytest.mark.parametrize(
    "port, prefix, value",
    [
        (1, "1 Max time between fix attempts out of trip", 129),
        (6, "1 V1 Daily GNSS on-time budget", 128),
        (6, "8 - 9 V1 Approximate maximum error", 0),
        (10, "3 Inactivity Alarm Heartbeat Period", 0),
    ],
)
def test_values_inside_split_ranges_are_accepted(config, port, prefix, value):
    encode_downlink(port, with_values(config[port], **{prefix: value}))
