from datetime import datetime, timezone

from tests.conftest import REPO, load_script


def fake_ack(config, sequence, port, since, attempts, interval):
    received = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {"sequence": sequence, "port": port, "accepted": True, "received_at": received}


def test_send_path_passes_f_port_as_integer(dummy_env, monkeypatch, capsys):
    # Audit A3: f_port was passed to the API as the string "9"
    module = load_script("configure-using-downlinks.py", "configure_send")
    sent = []
    monkeypatch.setattr(
        module, "push_downlink", lambda cfg, port, payload: sent.append((port, payload))
    )
    monkeypatch.setattr(module, "wait_for_ack", fake_ack)
    assert module.main(["--downlink", "9", "--send"]) == 0
    assert sent == [(9, bytes.fromhex("010711ff567f00"))]
    assert isinstance(sent[0][0], int)
    assert "MATCH: received_at" in capsys.readouterr().out


def test_send_never_happens_with_an_invalid_value(dummy_env, monkeypatch, tmp_path):
    module = load_script("configure-using-downlinks.py", "configure_send_invalid")
    sent = []
    monkeypatch.setattr(module, "push_downlink", lambda *a: sent.append(a))
    monkeypatch.setattr(module, "wait_for_ack", fake_ack)
    text = (REPO / "config.yaml").read_text().replace("      value: 7\n", "      value: 300\n", 1)
    path = tmp_path / "config.yaml"
    path.write_text(text)
    assert module.main(["--downlink", "9", "--send", "--config", str(path)]) == 2
    assert sent == []


def test_send_reports_missing_ack_without_failing_loudly(dummy_env, monkeypatch, capsys):
    module = load_script("configure-using-downlinks.py", "configure_send_noack")
    monkeypatch.setattr(module, "push_downlink", lambda *a: None)
    monkeypatch.setattr(module, "wait_for_ack", lambda *a, **kw: None)
    assert (
        module.main(["--downlink", "9", "--send", "--sequencenumber", "5", "--attempts", "2"]) == 1
    )
    out = capsys.readouterr().out
    assert "No acknowledgement after 2 attempts" in out
    assert "ack.py --downlink 9 --sequencenumber 5" in out


def test_send_failure_is_reported(dummy_env, monkeypatch, capsys):
    module = load_script("configure-using-downlinks.py", "configure_send_fail")

    def fail(*args):
        raise module.TTNError("HTTP 403: forbidden")

    monkeypatch.setattr(module, "push_downlink", fail)
    assert module.main(["--downlink", "9", "--send"]) == 1
    assert "Failed to send downlink: HTTP 403" in capsys.readouterr().err
