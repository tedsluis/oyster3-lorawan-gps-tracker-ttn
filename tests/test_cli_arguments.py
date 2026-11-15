import os
import re
import subprocess
import sys

import pytest

from tests.conftest import DUMMY_ENV, REPO, load_script


@pytest.fixture
def configure(dummy_env):
    return load_script("configure-using-downlinks.py", "configure_args")


@pytest.mark.parametrize("port", [0, 13, 29, 36, 224])
def test_configure_rejects_invalid_downlink_ports(configure, port):
    with pytest.raises(SystemExit):
        configure.parse_args(["--downlink", str(port)])


@pytest.mark.parametrize("port", [1, 12, 30, 35])
def test_configure_accepts_valid_downlink_ports(configure, port):
    assert configure.parse_args(["--downlink", str(port)]).downlink == port


def test_configure_sequence_number_range_is_inclusive(configure):
    args = configure.parse_args(["--downlink", "9", "--sequencenumber", "127"])
    assert args.sequencenumber == 127
    with pytest.raises(SystemExit):
        configure.parse_args(["--downlink", "9", "--sequencenumber", "128"])


def test_configure_sequence_override_is_used_in_payload(capsys):
    # Audit A6: distinguish successive attempts without editing config.yaml
    module = load_script("configure-using-downlinks.py", "configure_seq")
    assert module.main(["--downlink", "9", "--sequencenumber", "42"]) == 0
    assert "downlink9 Byte Array: 2a0711ff567f00" in capsys.readouterr().out


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, str(REPO / name), *args],
        cwd=REPO, env={**os.environ, **DUMMY_ENV}, capture_output=True, text=True, timeout=60,
    )


@pytest.mark.parametrize("name", ["ack.py", "uplinks.py"])
def test_ack_scripts_validate_arguments_before_any_network_call(name):
    result = run_script(name, "--downlink", "0", "--sequencenumber", "127")
    assert result.returncode == 2
    assert re.search(r"--downlink: invalid choice: '?0'?", result.stderr)
    result = run_script(name, "--downlink", "9", "--sequencenumber", "128")
    assert result.returncode == 2
    assert re.search(r"--sequencenumber: invalid choice: '?128'?", result.stderr)
