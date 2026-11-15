import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DUMMY_ENV = {
    "TTN_DEVICE": "dummy-device",
    "TTN_APPLICATION": "dummy-app",
    "TTN_REGION": "eu1",
    "TTN_CONSOLE": "dummy-tenant",
    "TTN_API_KEY": "NNSXS.DUMMY",
    "TTN_NUMBER_OF_RECORDS": "0",
    "TTN_SINCE_DATE_TIME": "",
}


@pytest.fixture
def dummy_env(monkeypatch):
    for key, value in DUMMY_ENV.items():
        monkeypatch.setenv(key, value)
    for key in ("APP_HOST", "APP_PORT", "APP_DEBUG", "TTN_DOWNLINK_API_KEY", "APP_TIMEZONE"):
        monkeypatch.delenv(key, raising=False)
    return DUMMY_ENV


def load_script(filename, name=None):
    """Import a top-level script (which may contain hyphens) as a fresh module."""
    path = REPO / filename
    module_name = name or "script_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(dummy_env):
    return load_script
