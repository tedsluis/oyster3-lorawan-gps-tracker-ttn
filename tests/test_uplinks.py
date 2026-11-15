from datetime import datetime, timezone

import pytest

from oyster3.uplinks import POSITION_PORTS, UplinkDecodeError, decode_uplink, resolve_timestamp15

approx = pytest.approx


def test_port1_spec_example():
    d = decode_uplink(1, bytes.fromhex("53AB783C0421F98E940AB3"))
    assert d["type"] == "position"
    assert d["latitude"] == approx(101.4541139)
    assert d["longitude"] == approx(-189.6275708)
    assert d["in_trip"] is False
    assert d["fix_failed"] is False
    assert d["heading_deg"] == approx(208.125)
    assert d["speed_kmph"] == 10
    assert d["battery_v"] == approx(4.475)


@pytest.mark.parametrize("raw", range(64))
def test_port1_heading_is_always_below_360(raw):
    payload = bytearray(11)
    payload[8] = raw << 2
    d = decode_uplink(1, bytes(payload))
    assert 0 <= d["heading_deg"] < 360
    assert d["heading_deg"] == raw * 5.625


def test_port1_heading_uses_the_top_six_bits():
    # Audit F05: 0x94 used to decode as 112 degrees
    payload = bytes.fromhex("53AB783C0421F98E940AB3")
    assert decode_uplink(1, payload)["heading_deg"] == approx(208.125)


def test_port1_failed_fix_moves_location_to_cached():
    payload = bytearray(bytes.fromhex("53AB783C0421F98E940AB3"))
    payload[8] |= 0b10
    d = decode_uplink(1, bytes(payload))
    assert d["fix_failed"] is True
    assert "latitude" not in d
    assert d["cached"]["latitude"] == approx(101.4541139)


def test_port2_spec_example():
    d = decode_uplink(2, bytes.fromhex("D3010262010A"))
    assert d == {
        "type": "downlink_ack",
        "sequence": 83,
        "accepted": True,
        "fw_major": 1,
        "fw_minor": 2,
        "product_id": 98,
        "hw_revision": 1,
        "port": 10,
        "f_port": 2,
    }


def test_port2_oyster1_short_ack():
    d = decode_uplink(2, bytes.fromhex("D30102"))
    assert d["sequence"] == 83
    assert d["port"] is None


def test_port3_spec_example():
    d = decode_uplink(3, bytes.fromhex("8BF3DC7B9438984278B85E"))
    assert d["type"] == "stats"
    assert d["initial_battery_v"] == approx(5.1)
    assert d["tx_count"] == 59136
    assert d["trip_count"] == 194336
    assert d["gnss_successes"] == 10464
    assert d["gnss_failures"] == 7232
    assert d["avg_gnss_fix_s"] == 96
    assert d["avg_gnss_fail_s"] == 133
    assert d["avg_gnss_freshen_s"] == 120
    assert d["wakeups_per_trip"] == 56
    assert d["uptime_weeks"] == 189


def test_port4_spec_example():
    d = decode_uplink(4, bytes.fromhex("53AB783C04A1F98E06"))
    assert d["type"] == "position"
    assert d["fix_failed"] is True
    assert d["inactivity_alarm"] is True
    assert d["in_trip"] is False
    assert d["battery_v"] == approx(3.55)
    assert d["battery_critical"] is None
    cached = d["cached"]
    assert cached["latitude"] == approx(202.4493824)
    assert cached["longitude"] == approx(-159.3558016)
    assert cached["heading_deg"] == 45
    assert cached["speed_kmph"] == 155


def test_port4_high_voltage_battery_scale():
    payload = bytearray(bytes.fromhex("53AB783C04A1F98E06"))
    payload[8] |= 0b1000
    assert decode_uplink(4, bytes(payload))["battery_v"] == approx(8.044)


def test_port30_spec_example():
    d = decode_uplink(30, bytes.fromhex("010A62010203017A"))
    assert d["type"] == "hello"
    assert (d["fw_major"], d["fw_minor"]) == (1, 10)
    assert (d["product_id"], d["hw_revision"]) == (98, 1)
    assert d["reset_watchdog"] is True
    assert d["reset_power_on"] is False
    assert d["watchdog_reason"] == 259
    assert d["battery_v"] == approx(7.404)


def test_port31_spec_example():
    d = decode_uplink(31, bytes.fromhex("8BF3DC7B94389842780843"))
    assert d["type"] == "stats_v3"
    assert d["ttff_s"] == 139
    assert d["wakeups_per_trip"] == 243
    assert d["initial_battery_v"] == approx(10.540)
    assert d["current_battery_v"] == approx(7.436)
    assert d["battery_critical"] is False
    assert d["battery_low"] is False
    assert d["trip_count"] == 115872
    assert d["uptime_weeks"] == 664
    assert d["energy_used_mwh"] == 5280
    assert d["percent_lorawan"] == approx(21.875)
    assert d["percent_gnss_success"] == approx(12.5)
    assert d["percent_gnss_fail"] == approx(37.5)
    assert d["percent_sleep_discharge"] == approx(25)
    assert d["percent_other"] == approx(3.125)


def test_port33_spec_example():
    d = decode_uplink(33, bytes.fromhex("E825F49B9E872B6A992AAB"))
    assert d["type"] == "position"
    assert d["fix_failed"] is False
    assert d["latitude"] == approx(-8.3333874)
    assert d["longitude"] == approx(-169.2850041)
    assert d["in_trip"] is True
    assert d["timestamp15"] == 21
    assert d["battery_critical"] is False
    assert d["inactivity_alarm"] is True
    assert d["inactivity_minutes"] == 19636
    assert d["battery_v"] == approx(4.844)
    assert d["heading_deg"] == 135
    assert d["speed_kmph"] == 105


def test_port33_timestamp_resolution_spec_example():
    rx = datetime.fromtimestamp(1646402580, tz=timezone.utc)
    assert resolve_timestamp15(21, rx).timestamp() == 1646402280
    assert resolve_timestamp15(127, rx) is None


def test_unknown_port_is_reported_not_raised():
    d = decode_uplink(99, b"\x01\x02")
    assert d["type"] == "unknown"
    assert d["warnings"]


@pytest.mark.parametrize(
    "port, length", [(1, 10), (2, 2), (3, 10), (4, 8), (30, 7), (31, 10), (33, 10)]
)
def test_short_payload_raises_a_clear_error(port, length):
    with pytest.raises(UplinkDecodeError, match="expected at least"):
        decode_uplink(port, bytes(length))


def test_only_gnss_uplinks_are_positions():
    # Audit F08: acks and statistics must never be treated as positions
    assert POSITION_PORTS == {1, 4, 33}
    assert decode_uplink(2, bytes.fromhex("D3010262010A"))["type"] != "position"
    assert decode_uplink(3, bytes.fromhex("8BF3DC7B9438984278B85E"))["type"] != "position"
    assert decode_uplink(31, bytes.fromhex("8BF3DC7B94389842780843"))["type"] != "position"
