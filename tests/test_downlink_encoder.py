import copy
import io
import random
from contextlib import redirect_stdout

import pytest

from oyster3.bits import read_field
from oyster3.downlinks import (
    SPEC_LENGTHS,
    encode_downlink,
    field_span,
    is_sequence_field,
    load_config,
)
from tests.conftest import REPO, load_script

GOLDEN = {
    1: "01981e8a8a1f0201",
    2: "010000000000000000",
    3: "01000000000000",
    4: "0100000000000000",
    5: "01830514644b1c03",
    6: "01000c0c0c0c00046400",
    7: "0120000000000000000000",
    8: "0170b3d57050000000",
    9: "010711ff567f00",
    10: "01000000000001c000",
    11: "0100000000000000000000",
    12: "010000",
    30: "01600088131e00",
    31: "013f",
    32: "01060a01",
    33: "01",
    34: "0100",
    35: "010400000000",
}


@pytest.fixture(scope="module")
def config():
    return load_config(REPO / "config.yaml")


def with_values(fields, **changes):
    """Copy of fields with values changed by name prefix."""
    fields = copy.deepcopy(fields)
    for prefix, value in changes.items():
        matches = [f for f in fields if f["name"].startswith(prefix)]
        assert len(matches) == 1, prefix
        matches[0]["value"] = value
    return fields


@pytest.mark.parametrize("port", sorted(GOLDEN))
def test_default_config_encodes_to_golden_payload(config, port):
    assert encode_downlink(port, config[port]).hex() == GOLDEN[port]


def test_sequence_number_one_is_0x01_in_byte_0(config):
    # Audit F01: the old encoder sent 0x02 and the device acknowledged sequence 2
    for port in GOLDEN:
        assert encode_downlink(port, config[port])[0] & 0x7F == 1


def test_sequence_override(config):
    assert encode_downlink(9, config[9], sequence=83).hex() == "530711ff567f00"


def proof(config, port, **changes):
    fields = with_values(config[port], **{k.replace("_", " "): v for k, v in changes.items()})
    return encode_downlink(port, fields).hex()


def test_dl34_reset_battery_critical_only(config):
    fields = with_values(config[34], **{"1.1 Reset just the Battery Critical indicator": 1})
    assert encode_downlink(34, fields).hex() == "0102"


def test_dl30_disable_uplink_31(config):
    fields = with_values(config[30], **{"6.1 Disable Uplink 31": 1})
    assert encode_downlink(30, fields).hex() == "01600088131e02"


def test_dl35_poll_ack_and_both_stats(config):
    fields = with_values(
        config[35],
        **{
            "0.7 Send Downlink Ack": True,
            "1.0 Send Device Statistics (Uplink 3)": True,
            "1.1 Send Device Statistics V3": True,
            "1.2 Apply Poll Position": False,
        },
    )
    assert encode_downlink(35, fields).hex() == "810300000000"


def test_dl7_channel_mask_is_little_endian(config):
    # Audit F02: channel 0 is the LSb of the first mask byte
    fields = with_values(config[7], **{"2 - 10 Uplink channel mask": 1})
    assert encode_downlink(7, fields).hex() == "0120010000000000000000"


def test_dl6_negative_margin_adjustment(config):
    fields = with_values(config[6], **{"6.0 - 6.4 Satellite detection margin": -3})
    assert encode_downlink(6, fields).hex() == "01000c0c0c0c1d046400"


def test_dl10_old_position_uplink_values(config):
    fields = with_values(config[10], **{"4 V3 Position Uplink": 1, "5 V3 Position Uplink": 1})
    assert encode_downlink(10, fields).hex() == "01000000010101c000"


def test_dl30_multi_byte_fields_are_little_endian(config):
    # Audit F02: 96 h and 5000 mWh were sent big-endian (24576 h, 34835 mWh)
    payload = encode_downlink(30, config[30])
    assert read_field(payload, 8, 16) == 96
    assert read_field(payload, 24, 16) == 5000


def test_dl8_join_eui_stays_big_endian(config):
    assert encode_downlink(8, config[8])[1:].hex() == "70b3d57050000000"


def random_value(field, rng):
    _, size = field_span(field)
    if field["type"] == "boolean":
        return rng.choice([True, False])
    if field["type"] == "signed-integer":
        low, high = -(1 << (size - 1)), (1 << (size - 1)) - 1
    else:
        low, high = 0, (1 << size) - 1
    low = max(low, field.get("min", low))
    high = min(high, field.get("max", high))
    return rng.randint(low, high)


@pytest.mark.parametrize("port", sorted(SPEC_LENGTHS))
@pytest.mark.parametrize("seed", range(5))
def test_round_trip_every_field(config, port, seed):
    rng = random.Random(port * 100 + seed)
    fields = copy.deepcopy(config[port])
    for field in fields:
        if not is_sequence_field(field):
            field["value"] = random_value(field, rng)
    payload = encode_downlink(port, fields)
    assert len(payload) == SPEC_LENGTHS[port]
    for field in fields:
        start, size = field_span(field)
        signed = field["type"] == "signed-integer"
        if field.get("endian") == "big":
            raw = read_field(payload, start, size).to_bytes(field["length"], "little")
            value = int.from_bytes(raw, "big")
        else:
            value = read_field(payload, start, size, signed=signed)
        assert value == int(field["value"]), field["name"]


def test_dl4_negative_utc_and_dst_offsets_round_trip(config):
    fields = with_values(
        config[4],
        **{
            "1.2 - 2.1 Offset of normal time zone": -20,  # UTC-5
            "4.2 - 5.2 Offset from 00.00 local time": -184,
            "6.7 - 7.7 Offset from 00:00 local DST": -184,
        },
    )
    payload = encode_downlink(4, fields)
    assert read_field(payload, 10, 8, signed=True) == -20
    assert read_field(payload, 34, 9, signed=True) == -184
    assert read_field(payload, 55, 9, signed=True) == -184


def run_cli(args):
    module = load_script("configure-using-downlinks.py", "configure_cli")
    out = io.StringIO()
    with redirect_stdout(out):
        code = module.main(args)
    return code, out.getvalue()


@pytest.mark.parametrize("port", sorted(GOLDEN))
def test_cli_dry_run_prints_golden_payload(port):
    code, out = run_cli(["--downlink", str(port), "--config", str(REPO / "config.yaml")])
    assert code == 0
    assert f"downlink{port} Byte Array: {GOLDEN[port]}" in out
    assert "WARNING" not in out


def test_cli_warns_about_non_default_values(tmp_path):
    # Audit F26: the CLI warns about every value that differs from its default
    text = (
        (REPO / "config.yaml")
        .read_text()
        .replace("      value: 6 # 94 mG", "      value: 7 # 109 mG")
    )
    path = tmp_path / "config.yaml"
    path.write_text(text)
    code, out = run_cli(["--downlink", "32", "--config", str(path)])
    assert code == 0
    assert "WARNING: not the default value (6): 1 Accelerometer wakeup threshold" in out
