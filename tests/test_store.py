import json
import os
import stat
from datetime import datetime, timezone

import pytest

from oyster3.store import Store, fetch_new
from oyster3.ttn import TTNConfig, TTNError
from tests.conftest import DUMMY_ENV
from tests.test_ttn import FakeResponse, body, record

UTC = timezone.utc


def synthetic(minute, f_port=1, payload="53AB783C0421F98E940AB3"):
    result = record(f"2030-01-01T10:{minute:02d}:00.123456789Z", f_port, payload)["result"]
    result["uplink_message"]["rx_metadata"] = [{"rssi": -100, "snr": 7.5}]
    result["uplink_message"]["consumed_airtime"] = "0.991232s"
    return result


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "data" / "uplinks.sqlite3") as s:
        yield s


def test_store_files_are_private(tmp_path):
    path = tmp_path / "data" / "uplinks.sqlite3"
    Store(path).close()
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_upsert_is_idempotent(store):
    records = [synthetic(0), synthetic(1), synthetic(2, f_port=2, payload="D3010262010A")]
    assert store.upsert(records) == (3, 0)
    assert store.upsert(records) == (0, 3)
    assert store.count_by_port() == {1: 2, 2: 1}


def test_row_columns_and_raw_json(store):
    store.upsert([synthetic(5)])
    (row,) = store.query()
    assert row["f_port"] == 1 and row["f_cnt"] == 1
    assert (row["rssi"], row["snr"], row["consumed_airtime"]) == (-100, 7.5, "0.991232s")
    assert json.loads(row["raw_json"])["received_at"] == "2030-01-01T10:05:00.123456789Z"


def test_missing_rx_metadata_and_f_cnt_are_tolerated(store):
    result = synthetic(6)
    del result["uplink_message"]["rx_metadata"]
    del result["uplink_message"]["f_cnt"]
    store.upsert([result])
    (row,) = store.query()
    assert row["rssi"] is None and row["f_cnt"] is None


def test_query_is_inclusive_and_ordered(store):
    store.upsert([synthetic(3), synthetic(1), synthetic(2)])
    start = datetime(2030, 1, 1, 10, 1, 0, 123456, UTC)
    end = datetime(2030, 1, 1, 10, 2, 0, 123456, UTC)
    assert [r["received_at"][14:16] for r in store.query(start, end)] == ["01", "02"]
    assert store.latest_received_at().startswith("2030-01-01T10:03")


@pytest.fixture
def ttn_get(monkeypatch):
    from oyster3 import ttn

    calls, responses = [], []

    def get(url, **kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(ttn.requests, "get", get)
    return calls, responses


def test_fetch_new_is_incremental(store, ttn_get):
    calls, responses = ttn_get
    config = TTNConfig.from_env({**DUMMY_ENV, "TTN_SINCE_DATE_TIME": "2029-12-01T00:00:00Z"})
    responses.append(FakeResponse(200, body({"result": synthetic(0)}, {"result": synthetic(1)})))
    assert fetch_new(store, config) == (2, 0)
    assert calls[0]["params"]["after"] == "2029-12-01T00:00:00Z"
    responses.append(FakeResponse(200, body({"result": synthetic(1)}, {"result": synthetic(2)})))
    assert fetch_new(store, config) == (1, 1)
    assert calls[1]["params"]["after"] == "2030-01-01T10:01:00.123456789Z"


def test_fetch_with_zero_new_records_is_no_error(store, ttn_get):
    _, responses = ttn_get
    responses.append(FakeResponse(200, ""))
    assert fetch_new(store, TTNConfig.from_env(DUMMY_ENV)) == (0, 0)


def test_failed_fetch_writes_nothing(store, ttn_get):
    _, responses = ttn_get
    responses.append(FakeResponse(401, "unauthenticated"))
    with pytest.raises(TTNError):
        fetch_new(store, TTNConfig.from_env(DUMMY_ENV))
    assert store.query() == []


def test_existing_shared_directory_is_not_changed(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    os.chmod(shared, 0o755)
    Store(shared / "uplinks.sqlite3").close()
    assert stat.S_IMODE(os.stat(shared).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(shared / "uplinks.sqlite3").st_mode) == 0o600
