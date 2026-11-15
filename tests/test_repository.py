import re

import yaml

from oyster3.downlinks import encode_downlink, load_config
from tests.conftest import REPO
from tests.test_downlink_encoder import with_values


def test_license_is_mit():
    # Audit F18
    text = (REPO / "LICENSE").read_text()
    assert text.startswith("MIT License") and "Ted Sluis" in text


def test_ci_runs_lint_and_tests_on_oldest_and_newest_python():
    workflow = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
    job = workflow["jobs"]["test"]
    assert job["strategy"]["matrix"]["python-version"] == ["3.10", "3.x"]
    commands = " ".join(step.get("run", "") for step in job["steps"])
    for command in ("ruff check", "ruff format --check", "pytest", "requirements-dev.txt"):
        assert command in commands
    assert "secrets." not in (REPO / ".github" / "workflows" / "ci.yml").read_text()


def test_recovery_runbook_payloads_match_the_encoder():
    # Audit F03: the runbook must show what the encoder really sends
    text = (REPO / "docs" / "DEVICE-RECOVERY.md").read_text()
    config = load_config(REPO / "config.yaml")
    assert f"downlink1 Byte Array: {encode_downlink(1, config[1]).hex()}" in text
    assert f"downlink9 Byte Array: {encode_downlink(9, config[9]).hex()}" in text
    poll = with_values(
        config[35],
        **{
            "0.7 Send Downlink Ack": True,
            "1.0 Send Device Statistics (Uplink 3)": True,
            "1.1 Send Device Statistics V3": True,
            "1.2 Apply Poll Position": False,
        },
    )
    assert f"payload is `{encode_downlink(35, poll).hex()}`" in text
    assert re.search(r"ack\.py --history", text)
    assert "downlink 7" in text and "8 (JoinEUI)" in text
