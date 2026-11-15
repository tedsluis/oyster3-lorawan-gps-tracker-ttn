"""Uplink decoders for the Oyster 3, field by field after spec §3.2-3.3 and the
reference decoder in §3.3.4.

``decode_uplink`` returns a dict. For position uplinks (ports 1, 4 and 33) the location
fields (``latitude``, ``longitude``, ``heading_deg``, ``speed_kmph``) are top-level when the
fix succeeded. When ``fix_failed`` is true they are placed under ``cached`` instead,
because the device then repeats its last known position.
"""

from datetime import datetime, timezone

from oyster3.bits import BitReader

POSITION_PORTS = frozenset({1, 4, 33})

_MIN_LENGTH = {1: 11, 2: 3, 3: 11, 4: 9, 30: 8, 31: 11, 33: 11}


class UplinkDecodeError(ValueError):
    pass


def _position(result, location):
    if result["fix_failed"]:
        result["cached"] = location
    else:
        result.update(location)
    return result


def _port1(b):
    location = {}
    location["latitude"] = round(b.s(32) / 1e7, 7)
    location["longitude"] = round(b.s(32) / 1e7, 7)
    result = {"type": "position", "in_trip": bool(b.u(1)), "fix_failed": bool(b.u(1))}
    location["heading_deg"] = b.u(6) * 5.625
    location["speed_kmph"] = b.u(8)
    result["battery_v"] = round(b.u(8) * 0.025, 3)
    result["inactivity_alarm"] = None
    result["battery_critical"] = None
    return _position(result, location)


def _port2(b, length):
    result = {"type": "downlink_ack", "sequence": b.u(7), "accepted": bool(b.u(1))}
    result["fw_major"] = b.u(8)
    result["fw_minor"] = b.u(8)
    if length < 6:
        result.update(product_id=None, hw_revision=None, port=None)
    else:
        result.update(product_id=b.u(8), hw_revision=b.u(8), port=b.u(8))
    return result


def _port3(b):
    return {
        "type": "stats",
        "initial_battery_v": round(4.0 + 0.1 * b.u(4), 2),
        "tx_count": 32 * b.u(11),
        "trip_count": 32 * b.u(13),
        "gnss_successes": 32 * b.u(10),
        "gnss_failures": 32 * b.u(8),
        "avg_gnss_fix_s": b.u(9),
        "avg_gnss_fail_s": b.u(9),
        "avg_gnss_freshen_s": b.u(8),
        "wakeups_per_trip": b.u(7),
        "uptime_weeks": b.u(9),
    }


def _port4(b):
    location = {}
    location["latitude"] = round(256 * b.s(24) / 1e7, 7)
    location["longitude"] = round(256 * b.s(24) / 1e7, 7)
    location["heading_deg"] = 45 * b.u(3)
    location["speed_kmph"] = 5 * b.u(5)
    raw_battery = b.u(8)
    result = {"type": "position", "in_trip": bool(b.u(1)), "fix_failed": bool(b.u(1))}
    result["inactivity_alarm"] = bool(b.u(1))
    if b.u(1) == 0:
        result["battery_v"] = round(0.025 * raw_battery, 3)
    else:
        result["battery_v"] = round(3.5 + 0.032 * raw_battery, 3)
    critical = b.u(2)
    result["battery_critical"] = None if critical == 0 else critical >= 2
    return _position(result, location)


def _port30(b):
    result = {"type": "hello", "fw_major": b.u(8), "fw_minor": b.u(8)}
    result["product_id"] = b.u(8)
    result["hw_revision"] = b.u(8)
    result["reset_power_on"] = bool(b.u(1))
    result["reset_watchdog"] = bool(b.u(1))
    result["reset_external"] = bool(b.u(1))
    result["reset_software"] = bool(b.u(1))
    b.skip(4)
    result["watchdog_reason"] = b.u(16)
    result["battery_v"] = round(3.5 + 0.032 * b.u(8), 3)
    return result


def _port31(b):
    result = {"type": "stats_v3", "ttff_s": b.u(8), "wakeups_per_trip": b.u(8)}
    result["initial_battery_v"] = round(3.5 + 0.032 * b.u(8), 3)
    result["current_battery_v"] = round(3.5 + 0.032 * b.u(8), 3)
    result["battery_critical"] = bool(b.u(1))
    result["battery_low"] = bool(b.u(1))
    result["trip_count"] = 32 * b.u(14)
    result["uptime_weeks"] = b.u(10)
    result["energy_used_mwh"] = 10 * b.u(10)
    shares = ("lorawan", "gnss_success", "gnss_fail", "sleep_discharge")
    for key in shares:
        result[f"percent_{key}"] = 100 / 32 * b.u(5)
    result["percent_other"] = 100 - sum(result[f"percent_{key}"] for key in shares)
    return result


def _port33(b):
    result = {"type": "position", "fix_failed": bool(b.u(1))}
    location = {}
    location["latitude"] = round(180 * b.s(23) / (1 << 23), 7)
    location["longitude"] = round(360 * b.s(24) / (1 << 24), 7)
    result["in_trip"] = bool(b.u(1))
    timestamp = b.u(7)
    result["timestamp15"] = None if timestamp == 127 else timestamp
    result["battery_critical"] = bool(b.u(1))
    result["inactivity_alarm"] = bool(b.u(1))
    result["inactivity_minutes"] = 2 * b.u(14)
    result["battery_v"] = round(3.5 + 0.032 * b.u(8), 3)
    location["heading_deg"] = 45 * b.u(3)
    location["speed_kmph"] = 5 * b.u(5)
    return _position(result, location)


def decode_uplink(f_port: int, payload: bytes) -> dict:
    payload = bytes(payload)
    if f_port not in _MIN_LENGTH:
        return {"type": "unknown", "f_port": f_port, "warnings": [f"unknown f_port {f_port}"]}
    if len(payload) < _MIN_LENGTH[f_port]:
        raise UplinkDecodeError(
            f"f_port {f_port} payload has {len(payload)} bytes, "
            f"expected at least {_MIN_LENGTH[f_port]}"
        )
    b = BitReader(payload)
    if f_port == 1:
        result = _port1(b)
    elif f_port == 2:
        result = _port2(b, len(payload))
    elif f_port == 3:
        result = _port3(b)
    elif f_port == 4:
        result = _port4(b)
    elif f_port == 30:
        result = _port30(b)
    elif f_port == 31:
        result = _port31(b)
    else:
        result = _port33(b)
    result["f_port"] = f_port
    return result


def resolve_timestamp15(timestamp15, approx_reception: datetime):
    """Resolve the Uplink 33 timestamp (round(unix/15) mod 127) near the reception time,
    following ResolveTime() from the reference decoder."""
    if timestamp15 is None or timestamp15 == 127:
        return None
    ref_time = round(approx_reception.timestamp()) + 600
    timestamp = timestamp15 * 15
    period = 127 * 15
    multiple, modulo = divmod(ref_time, period)
    if modulo > timestamp:
        unix_time = multiple * period + timestamp
    else:
        unix_time = (multiple - 1) * period + timestamp
    return datetime.fromtimestamp(unix_time, tz=timezone.utc)
