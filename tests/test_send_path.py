from tests.conftest import REPO, load_script


def test_send_path_passes_f_port_as_integer(dummy_env, monkeypatch, capsys):
    # Audit A3: f_port was passed to the API as the string "9"
    module = load_script("configure-using-downlinks.py", "configure_send")
    sent = []
    monkeypatch.setattr(module, "send_downlink", lambda **kw: sent.append(kw))
    monkeypatch.setattr(module, "confirm_configuration", lambda *a, **kw: True)
    assert module.main(["--downlink", "9", "--send"]) == 0
    assert sent == [{"confirmed": True, "f_port": 9, "payload_hex": "010711ff567f00"}]
    assert isinstance(sent[0]["f_port"], int)


def test_send_never_happens_with_an_invalid_value(dummy_env, monkeypatch, tmp_path):
    module = load_script("configure-using-downlinks.py", "configure_send_invalid")
    sent = []
    monkeypatch.setattr(module, "send_downlink", lambda **kw: sent.append(kw))
    monkeypatch.setattr(module, "confirm_configuration", lambda *a, **kw: True)
    text = (REPO / "config.yaml").read_text().replace("      value: 7\n", "      value: 300\n", 1)
    path = tmp_path / "config.yaml"
    path.write_text(text)
    assert module.main(["--downlink", "9", "--send", "--config", str(path)]) == 2
    assert sent == []
