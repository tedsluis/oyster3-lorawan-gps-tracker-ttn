import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests

from oyster3 import ttn
from oyster3.ttn import (
    TTNConfig,
    TTNError,
    downlink_acks,
    fetch_uplinks,
    find_ack,
    parse_storage_response,
    push_downlink,
    wait_for_ack,
)
from tests.conftest import DUMMY_ENV, REPO

UTC = timezone.utc


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def record(received_at, f_port, payload_hex):
    payload = base64.b64encode(bytes.fromhex(payload_hex)).decode()
    return {
        "result": {
            "received_at": received_at,
            "uplink_message": {"f_port": f_port, "f_cnt": 1, "frm_payload": payload},
        }
    }


def body(*records, separator="\n\n", trailing=True):
    text = separator.join(json.dumps(r) for r in records)
    return text + (separator if trailing and records else "")


@pytest.fixture
def config():
    return TTNConfig.from_env(DUMMY_ENV)


@pytest.fixture
def http(monkeypatch):
    calls = {"get": [], "post": []}
    responses = {"get": [], "post": []}

    def fake(method):
        def call(url, **kwargs):
            calls[method].append({"url": url, **kwargs})
            response = responses[method].pop(0) if responses[method] else FakeResponse()
            if isinstance(response, Exception):
                raise response
            return response

        return call

    monkeypatch.setattr(ttn.requests, "get", fake("get"))
    monkeypatch.setattr(ttn.requests, "post", fake("post"))
    return calls, responses


# --- configuration (F11, F13, F17) ---------------------------------------------------------


def test_config_requires_all_variables():
    env = dict(DUMMY_ENV)
    del env["TTN_API_KEY"]
    with pytest.raises(TTNError, match="TTN_API_KEY"):
        TTNConfig.from_env(env)


def test_urls_are_built_from_console_and_region(config):
    # Audit F17: the downlink URL used a hardcoded tenant host
    prefix = "https://dummy-tenant.eu1.cloud.thethings.industries/api/v3/as/applications/dummy-app"
    assert config.storage_url == prefix + "/devices/dummy-device/packages/storage/uplink_message"
    assert config.downlink_url == prefix + "/devices/dummy-device/down/push"


def test_no_hardcoded_tenant_host_outside_the_client():
    for path in REPO.glob("*.py"):
        assert ".cloud.thethings.industries" not in path.read_text(), path.name


def test_downlink_key_falls_back_to_api_key(config):
    assert config.downlink_api_key == DUMMY_ENV["TTN_API_KEY"]
    separate = TTNConfig.from_env({**DUMMY_ENV, "TTN_DOWNLINK_API_KEY": "NNSXS.WRITE"})
    assert separate.downlink_api_key == "NNSXS.WRITE"
    assert separate.api_key == DUMMY_ENV["TTN_API_KEY"]


@pytest.mark.parametrize("value, expected", [("0", 0), ("", 0), ("50", 50), (" 7 ", 7)])
def test_number_of_records_is_an_integer(value, expected):
    assert TTNConfig.from_env({**DUMMY_ENV, "TTN_NUMBER_OF_RECORDS": value}).number_of_records == (
        expected
    )


def test_number_of_records_must_be_numeric():
    with pytest.raises(TTNError, match="TTN_NUMBER_OF_RECORDS"):
        TTNConfig.from_env({**DUMMY_ENV, "TTN_NUMBER_OF_RECORDS": "all"})


# --- response parsing (F21) ----------------------------------------------------------------

A = record("2025-01-05T13:56:56.256908367Z", 2, "D3010262010A")
B = record("2025-01-05T14:00:00.1Z", 1, "53AB783C0421F98E940AB3")


@pytest.mark.parametrize(
    "text, count",
    [
        ("", 0),
        ("\n\n", 0),
        (body(A), 1),
        (body(A, B, separator="\n"), 2),
        (body(A, B, separator="\n\n"), 2),
        (body(A, B, separator="\n", trailing=False), 2),
        (body(A, B, separator="\r\n\r\n"), 2),
    ],
)
def test_parse_storage_response(text, count):
    results = parse_storage_response(text)
    assert len(results) == count
    assert all("received_at" in r for r in results)


def test_parse_storage_response_reports_api_errors():
    with pytest.raises(TTNError, match="API error 16: unauthenticated"):
        parse_storage_response('{"code": 16, "message": "unauthenticated"}\n')


def test_parse_storage_response_reports_invalid_json():
    with pytest.raises(TTNError, match="invalid JSON on line 3"):
        parse_storage_response(body(A) + "{not json\n")


# --- HTTP (F13, F14, F22) ------------------------------------------------------------------


def test_fetch_uplinks_request(config, http):
    calls, responses = http
    responses["get"].append(FakeResponse(200, body(A, B)))
    after = datetime(2025, 1, 5, 12, 0, tzinfo=UTC)
    results = fetch_uplinks(config, after=after, limit=100)
    assert [r["uplink_message"]["f_port"] for r in results] == [2, 1]
    call = calls["get"][0]
    assert call["timeout"] == 30
    assert call["params"] == {
        "order": "received_at",
        "type": "uplink_message",
        "after": "2025-01-05T12:00:00.000000Z",
        "limit": "100",
    }
    assert call["headers"]["User-Agent"].startswith("oyster3-lorawan-gps-tracker-ttn/")
    assert call["headers"]["Accept"] == "text/event-stream"


def test_fetch_uplinks_without_limit_when_number_of_records_is_zero(config, http):
    # Audit F13: "0" used to be sent as limit=0
    calls, _ = http
    fetch_uplinks(config)
    assert "limit" not in calls["get"][0]["params"]
    assert "after" not in calls["get"][0]["params"]


def test_fetch_uplinks_uses_since_from_environment(http):
    calls, _ = http
    config = TTNConfig.from_env({**DUMMY_ENV, "TTN_SINCE_DATE_TIME": "2024-11-21T10:00:00Z"})
    fetch_uplinks(config)
    assert calls["get"][0]["params"]["after"] == "2024-11-21T10:00:00Z"


def test_http_error_is_reported_without_the_api_key(config, http):
    _, responses = http
    responses["get"].append(FakeResponse(401, '{"code":16,"message":"unauthenticated"}'))
    with pytest.raises(TTNError, match="HTTP 401") as error:
        fetch_uplinks(config)
    assert DUMMY_ENV["TTN_API_KEY"] not in str(error.value)


@pytest.mark.parametrize("exception", [requests.Timeout("slow"), requests.ConnectionError("down")])
def test_network_errors_become_ttn_errors(config, http, exception):
    _, responses = http
    responses["get"].append(exception)
    with pytest.raises(TTNError, match="request to TTN failed"):
        fetch_uplinks(config)


def test_empty_response_is_no_error(config, http):
    _, responses = http
    responses["get"].append(FakeResponse(200, ""))
    assert fetch_uplinks(config) == []


def test_push_downlink(config, http):
    calls, _ = http
    push_downlink(config, 9, bytes.fromhex("010711ff567f00"))
    call = calls["post"][0]
    assert call["url"] == config.downlink_url
    assert call["timeout"] == 30
    assert call["json"] == {
        "downlinks": [{"f_port": 9, "frm_payload": "AQcR/1Z/AA==", "confirmed": True}]
    }
    assert call["headers"]["Authorization"] == f"Bearer {config.downlink_api_key}"


def test_push_downlink_failure(config, http):
    _, responses = http
    responses["post"].append(FakeResponse(403, "forbidden"))
    with pytest.raises(TTNError, match="HTTP 403"):
        push_downlink(config, 9, b"\x01")


# --- acknowledgements (F12, F22) -----------------------------------------------------------


def ack_record(received_at, seq, port):
    return record(received_at, 2, f"{0x80 | seq:02x}01026201{port:02x}")


def test_downlink_acks_are_decoded_with_aware_times():
    acks = downlink_acks(parse_storage_response(body(A, B)))
    assert len(acks) == 1
    assert acks[0]["sequence"] == 83
    assert acks[0]["port"] == 10
    assert acks[0]["received_at"] == datetime(2025, 1, 5, 13, 56, 56, 256908, UTC)


def test_find_ack_matches_sequence_and_port():
    results = parse_storage_response(
        body(
            ack_record("2025-01-05T13:00:00Z", 1, 9),
            ack_record("2025-01-05T13:01:00Z", 2, 1),
            ack_record("2025-01-05T13:02:00Z", 2, 9),
        )
    )
    acks = downlink_acks(results)
    assert find_ack(acks, 2, 9)["received_at"].minute == 2
    assert find_ack(acks, 3, 9) is None


def test_wait_for_ack_stops_after_match_and_only_asks_for_new_uplinks(config, http):
    calls, responses = http
    since = datetime(2025, 1, 5, 13, 0, tzinfo=UTC)
    responses["get"].append(FakeResponse(200, body(ack_record("2025-01-05T12:00:00Z", 1, 9))))
    responses["get"].append(
        FakeResponse(200, body(ack_record("2025-01-05T13:30:00.123456789Z", 1, 9)))
    )
    sleeps, logs = [], []
    found = wait_for_ack(
        config, 1, 9, since, attempts=5, interval=7, sleep=sleeps.append, log=logs.append
    )
    assert found["sequence"] == 1 and found["port"] == 9
    assert len(calls["get"]) == 2  # stopped after the match
    assert sleeps == [7]
    assert calls["get"][0]["params"]["after"] == "2025-01-05T12:59:00.000000Z"
    assert calls["get"][0]["params"]["limit"] == "100"


def test_wait_for_ack_ignores_acks_from_before_the_send(config, http):
    # Audit F12: timestamps are compared in UTC, not against local naive time
    _, responses = http
    since = datetime(2025, 1, 5, 13, 0, tzinfo=UTC)
    old = FakeResponse(200, body(ack_record("2025-01-05T12:30:00Z", 1, 9)))
    responses["get"].extend([old, old])
    assert (
        wait_for_ack(
            config, 1, 9, since, attempts=2, interval=0, sleep=lambda s: None, log=lambda m: None
        )
        is None
    )


def test_wait_for_ack_survives_a_failing_poll(config, http):
    _, responses = http
    since = datetime(2025, 1, 5, 13, 0, tzinfo=UTC)
    responses["get"].append(requests.Timeout("slow"))
    responses["get"].append(FakeResponse(200, body(ack_record("2025-01-05T13:05:00Z", 4, 1))))
    logs = []
    found = wait_for_ack(
        config, 4, 1, since, attempts=3, interval=0, sleep=lambda s: None, log=logs.append
    )
    assert found is not None
    assert "request to TTN failed" in logs[0]


def test_ack_window_tolerates_small_clock_difference(config, http):
    _, responses = http
    since = datetime(2025, 1, 5, 13, 0, tzinfo=UTC)
    responses["get"].append(FakeResponse(200, body(ack_record("2025-01-05T12:59:30Z", 4, 1))))
    assert (
        wait_for_ack(config, 4, 1, since, attempts=1, sleep=lambda s: None, log=lambda m: None)
        is not None
    )
    assert since - timedelta(minutes=1) < datetime(2025, 1, 5, 12, 59, 30, tzinfo=UTC)


def test_reading_and_sending_use_separate_keys(http):
    calls, _ = http
    config = TTNConfig.from_env({**DUMMY_ENV, "TTN_DOWNLINK_API_KEY": "NNSXS.WRITE"})
    fetch_uplinks(config)
    push_downlink(config, 9, b"\x01")
    assert calls["get"][0]["headers"]["Authorization"] == f"Bearer {DUMMY_ENV['TTN_API_KEY']}"
    assert calls["post"][0]["headers"]["Authorization"] == "Bearer NNSXS.WRITE"


def test_example_environment_file_has_placeholders_only():
    text = (REPO / "export-env-vars.sh.example").read_text()
    for name in (
        "TTN_DEVICE",
        "TTN_APPLICATION",
        "TTN_REGION",
        "TTN_CONSOLE",
        "TTN_API_KEY",
        "TTN_DOWNLINK_API_KEY",
        "TTN_NUMBER_OF_RECORDS",
        "TTN_SINCE_DATE_TIME",
    ):
        assert name in text
    keys = [line for line in text.splitlines() if "NNSXS." in line]
    assert keys and all("REPLACE-WITH" in line for line in keys)
