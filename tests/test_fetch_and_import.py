import csv
import json
import os
import stat

import pytest

from oyster3.store import Store
from tests.conftest import load_script
from tests.test_store import synthetic
from tests.test_ttn import FakeResponse, body


@pytest.fixture
def ttn_get(monkeypatch):
    from oyster3 import ttn

    calls, responses = [], []

    def get(url, **kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(ttn.requests, "get", get)
    return calls, responses


def test_fetch_stores_new_uplinks(dummy_env, ttn_get, tmp_path, capsys):
    _, responses = ttn_get
    responses.append(FakeResponse(200, body({"result": synthetic(0)}, {"result": synthetic(1)})))
    database = tmp_path / "db.sqlite3"
    assert load_script("fetch.py").main(["--database", str(database)]) == 0
    assert "2 new uplinks stored, 0 already known." in capsys.readouterr().out
    with Store(database) as store:
        assert len(store.query()) == 2


def test_fetch_with_api_error_stores_nothing(dummy_env, ttn_get, tmp_path, capsys):
    _, responses = ttn_get
    responses.append(FakeResponse(401, "unauthenticated"))
    database = tmp_path / "db.sqlite3"
    assert load_script("fetch.py").main(["--database", str(database)]) == 1
    assert "Nothing was stored" in capsys.readouterr().err
    with Store(database) as store:
        assert store.query() == []


def test_export_tsv_uses_the_spec_decoder(tmp_path):
    database = tmp_path / "db.sqlite3"
    with Store(database) as store:
        store.upsert([synthetic(0), synthetic(1, f_port=3, payload="8BF3DC7B9438984278B85E")])
    out = tmp_path / "export.tsv"
    assert (
        load_script("fetch.py").main(["--database", str(database), "--export-tsv", str(out)]) == 0
    )
    rows = list(csv.DictReader(out.open(), dialect="excel-tab"))
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o600
    assert rows[0]["heading_deg"] == "208.125"
    assert rows[0]["battery"] == "4.475"
    assert rows[1]["f_port"] == "3" and rows[1]["gps_lat"] == ""


def write_snapshot(directory, name, results):
    (directory / name).write_text(json.dumps({"data": [{"result": r} for r in results]}))


def test_import_snapshots_counts_unique_records_per_port(tmp_path, capsys):
    snapshots = tmp_path / "json"
    snapshots.mkdir()
    write_snapshot(snapshots, "a.json", [synthetic(0), synthetic(1)])
    write_snapshot(snapshots, "b.json", [synthetic(1), synthetic(2, 2, "D3010262010A")])
    (snapshots / "broken.json").write_text("{not json")
    before = {p.name: p.read_bytes() for p in snapshots.iterdir()}
    database = tmp_path / "db.sqlite3"
    module = load_script("import-snapshots.py")
    args = ["--database", str(database), "--directory", str(snapshots)]
    assert module.main(args) == 0
    out = capsys.readouterr().out
    assert "3 new uplinks stored, 1 duplicates ignored." in out
    assert "3 unique uplinks (port 1: 2, port 2: 1)" in out
    assert module.main(args) == 0
    assert "0 new uplinks stored, 4 duplicates ignored." in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in snapshots.iterdir()} == before
