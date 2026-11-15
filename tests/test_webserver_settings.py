from tests.conftest import REPO


def test_webserver_defaults_are_local_and_without_debugger(script):
    webserver = script("webserver.py")
    assert webserver.run_settings({}) == ("127.0.0.1", 5000, False)


def test_webserver_settings_can_be_overridden(script):
    webserver = script("webserver.py")
    env = {"APP_HOST": "0.0.0.0", "APP_PORT": "8080", "APP_DEBUG": "true"}
    assert webserver.run_settings(env) == ("0.0.0.0", 8080, True)


def test_webserver_main_block_has_no_hardcoded_debug():
    source = (REPO / "webserver.py").read_text()
    assert "debug=True" not in source
    assert "host='0.0.0.0'" not in source
