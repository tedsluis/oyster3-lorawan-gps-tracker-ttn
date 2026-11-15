import pytest

from tests.conftest import load_script
from tests.test_ttn import FakeResponse, ack_record, body, record


@pytest.fixture
def ttn_get(monkeypatch):
    from oyster3 import ttn

    calls, responses = [], []

    def get(url, **kwargs):
        calls.append(kwargs)
        return responses.pop(0) if responses else FakeResponse(200, "")

    monkeypatch.setattr(ttn.requests, "get", get)
    monkeypatch.setattr(ttn.time, "sleep", lambda seconds: None)
    return calls, responses


def test_history_lists_acks_once(dummy_env, ttn_get, capsys):
    calls, responses = ttn_get
    now = "2999-01-01T00:00:00Z"  # inside any look-back window
    responses.append(FakeResponse(200, body(ack_record(now, 2, 9), ack_record(now, 3, 1))))
    module = load_script("ack.py", "ack_history")
    assert module.main(["--history", "--hours", "48"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(calls) == 1
    assert "sequence number: 2" in out[0] and "downlink_port_number: 9" in out[0]
    assert "sequence number: 3" in out[1]


def test_poll_stops_after_match(dummy_env, ttn_get, capsys):
    calls, responses = ttn_get
    responses.append(FakeResponse(200, body(ack_record("2999-01-01T00:00:00Z", 2, 1))))
    responses.append(FakeResponse(200, body(ack_record("2999-01-01T00:00:00Z", 2, 9))))
    module = load_script("ack.py", "ack_poll")
    code = module.main(
        ["--downlink", "9", "--sequencenumber", "2", "--attempts", "5", "--interval", "0"]
    )
    assert code == 0
    assert len(calls) == 2
    assert "MATCH: received_at" in capsys.readouterr().out


def test_poll_without_match_reports_no_match(dummy_env, ttn_get, capsys):
    module = load_script("ack.py", "ack_nomatch")
    code = module.main(
        ["--downlink", "9", "--sequencenumber", "2", "--attempts", "2", "--interval", "0"]
    )
    assert code == 1
    assert "NO_MATCH" in capsys.readouterr().out


def test_ack_requires_downlink_and_sequence_without_history(dummy_env):
    module = load_script("ack.py", "ack_args")
    with pytest.raises(SystemExit):
        module.parse_args(["--downlink", "9"])


def test_api_error_gives_clean_exit(dummy_env, ttn_get, capsys):
    _, responses = ttn_get
    responses.append(FakeResponse(401, "unauthenticated"))
    module = load_script("ack.py", "ack_error")
    assert module.main(["--history"]) == 1
    assert "HTTP 401" in capsys.readouterr().err


def test_uplinks_lists_every_port_decoded(dummy_env, ttn_get, capsys):
    _, responses = ttn_get
    responses.append(
        FakeResponse(
            200,
            body(
                record("2999-01-01T00:00:00Z", 3, "8BF3DC7B9438984278B85E"),
                record("2999-01-01T00:01:00Z", 31, "8BF3DC7B94389842780843"),
                record("2999-01-01T00:02:00Z", 2, "D30102"),
            ),
        )
    )
    module = load_script("uplinks.py", "uplinks_cli")
    assert module.main(["--port", "3", "--port", "31"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2
    assert "port 3 stats" in out[0] and "tx_count: 59136" in out[0]
    assert "port 31 stats_v3" in out[1] and "energy_used_mwh: 5280" in out[1]
