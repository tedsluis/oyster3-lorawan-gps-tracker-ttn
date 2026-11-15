import os
import subprocess
import sys

from tests.conftest import DUMMY_ENV, REPO


def run_configure(*args):
    env = {**os.environ, **DUMMY_ENV}
    return subprocess.run(
        [sys.executable, str(REPO / "configure-using-downlinks.py"), *args],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_send_is_refused_while_encoder_is_wrong():
    result = run_configure("--downlink", "9", "--send")
    assert result.returncode != 0
    assert "audit F01" in result.stderr
    assert "Byte Array" not in result.stdout
