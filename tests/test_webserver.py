import html
import os
import re
import shutil
import stat
import struct
from concurrent.futures import ThreadPoolExecutor

import pytest

from oyster3.store import Store
from tests.conftest import REPO, load_script
from tests.test_store import synthetic
from tests.test_ttn import FakeResponse


def port1(lat, lon, in_trip=True, fix_failed=False, heading_raw=0, speed=0, battery_raw=160):
    status = int(in_trip) | int(fix_failed) << 1 | heading_raw << 2
    raw = struct.pack("<ii", round(lat * 1e7), round(lon * 1e7))
    return (raw + bytes([status, speed, battery_raw])).hex()


def uplink(received_at, payload_hex, f_port=1):
    result = synthetic(0, f_port=f_port, payload=payload_hex)
    result["received_at"] = received_at
    return result


@pytest.fixture
def webserver(dummy_env, monkeypatch):
    monkeypatch.setenv("APP_TIMEZONE", "Europe/Amsterdam")
    module = load_script("webserver.py", "webserver_app")
    return module


@pytest.fixture
def http_calls(monkeypatch):
    from oyster3 import ttn

    calls, responses = [], []

    def get(url, **kwargs):
        calls.append(url)
        if responses:
            return responses.pop(0)
        raise AssertionError("unexpected HTTP call")

    monkeypatch.setattr(ttn.requests, "get", get)
    return calls, responses


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "data" / "uplinks.sqlite3"
    with Store(path) as store:
        store.upsert(
            [
                # 2030-07-01 22:30 UTC is 2030-07-02 00:30 in Amsterdam (CEST)
                uplink("2030-07-01T22:30:00Z", port1(10.1, 20.1, heading_raw=63, speed=40)),
                uplink("2030-07-02T08:00:00Z", port1(10.2, 20.2, speed=30, heading_raw=16)),
                uplink("2030-07-02T09:00:00Z", port1(10.3, 20.3, in_trip=False)),
                uplink("2030-07-02T10:00:00Z", port1(11.5, 21.5, fix_failed=True, speed=5)),
                uplink("2030-07-02T11:00:00Z", "8BF3DC7B9438984278B85E", f_port=3),
                uplink("2030-07-02T11:30:00Z", "D3010262010A", f_port=2),
                uplink("2030-07-02T12:00:00Z", "8BF3DC7B94389842780843", f_port=31),
                uplink("2030-07-03T08:00:00Z", port1(12.0, 22.0, speed=10, heading_raw=8)),
            ]
        )
    return path


def page(client, **form):
    response = client.post("/", data=form) if form else client.get("/")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    srcdoc = re.search(r'srcdoc="([^"]*)"', text).group(1)
    return text, html.unescape(srcdoc)


def day(date, **extra):
    form = {
        "start_datetime": f"{date}T00:00",
        "end_datetime": f"{date}T23:59",
        "in_trip_checked": "on",
        "stopped_checked": "on",
        "fix_successful_checked": "on",
        "fix_failed_checked": "on",
    }
    form.update(extra)
    return form


def markers(map_html):
    return len(re.findall(r"L\.marker\(", map_html))


def polyline(map_html):
    match = re.search(r"L\.polyline\(\s*(\[\[.*?\]\])", map_html, re.S)
    return match.group(1) if match else ""


def test_get_makes_no_http_calls_and_writes_no_files(
    webserver, http_calls, database, tmp_path, monkeypatch
):
    calls, _ = http_calls
    monkeypatch.chdir(tmp_path)
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    client = webserver.create_app(database=database).test_client()
    page(client)
    assert calls == []
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before


def test_map_is_not_written_to_templates():
    source = (REPO / "webserver.py").read_text()
    assert "map_content" not in source and ".save(" not in source
    assert "map_content" not in (REPO / "templates" / "map.html").read_text()


def test_only_position_uplinks_are_plotted(webserver, database):
    # Audit F08: ports 2, 3 and 31 used to be plotted at bogus coordinates
    client = webserver.create_app(database=database).test_client()
    _, map_html = page(client, **day("2030-07-02"))
    assert markers(map_html) == 4  # 4 GNSS uplinks on 2030-07-02 local time


def test_failed_fix_is_a_cached_marker_outside_the_route(webserver, database):
    client = webserver.create_app(database=database).test_client()
    _, map_html = page(client, **day("2030-07-02"))
    assert "11.5" not in polyline(map_html)
    assert "10.2" in polyline(map_html)
    assert "Fix failed: cached position" in map_html
    assert '"red"' in map_html


def test_local_day_selection_uses_the_app_timezone(webserver, database):
    # Audit F19: 22:30 UTC on July 1st is 00:30 on July 2nd in Amsterdam
    client = webserver.create_app(database=database).test_client()
    _, july1 = page(client, **day("2030-07-01"))
    _, july2 = page(client, **day("2030-07-02"))
    assert markers(july1) == 0
    assert "Time: 2030-07-02 00:30:00 CEST" in july2


def test_heading_in_popup_is_below_360(webserver, database):
    client = webserver.create_app(database=database).test_client()
    _, map_html = page(client, **day("2030-07-02"))
    headings = [float(h) for h in re.findall(r"Direction: ([0-9.]+) degrees", map_html)]
    assert headings and max(headings) < 360
    assert 354.375 in headings
    assert "rotate(354.375deg)" in map_html


def test_filters_select_points(webserver, database):
    client = webserver.create_app(database=database).test_client()
    form = day("2030-07-02")
    del form["fix_failed_checked"], form["stopped_checked"]
    _, map_html = page(client, **form)
    assert markers(map_html) == 2


@pytest.mark.parametrize(
    "form, message",
    [
        ({}, "Invalid or missing start datetime"),
        ({"start_datetime": "yesterday", "end_datetime": "2030-07-02T23:59"}, "Invalid or missing"),
        (
            {"start_datetime": "2030-07-03T00:00", "end_datetime": "2030-07-02T00:00"},
            "The start must be before the end",
        ),
    ],
)
def test_bad_form_input_falls_back_with_a_message(webserver, database, form, message):
    # Audit F24: missing fields used to give HTTP 500
    client = webserver.create_app(database=database).test_client()
    response = client.post("/", data=form)
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)


def test_template_uses_required_attribute():
    template = (REPO / "templates" / "map.html").read_text()
    assert "requiered" not in template
    assert template.count(" required ") == 2


def test_refresh_failure_shows_local_data(webserver, http_calls, database):
    _, responses = http_calls
    responses.append(FakeResponse(401, "unauthenticated"))
    client = webserver.create_app(database=database).test_client()
    text, map_html = page(client, **day("2030-07-02", refresh="1"))
    assert "Could not fetch from TTN, showing local data: HTTP 401" in html.unescape(text)
    assert markers(map_html) == 4


def test_refresh_stores_new_uplinks(webserver, http_calls, database):
    _, responses = http_calls
    new = uplink("2030-07-02T13:00:00Z", port1(10.9, 20.9, speed=12, heading_raw=4))
    responses.append(FakeResponse(200, '{"result": ' + __import__("json").dumps(new) + "}\n"))
    client = webserver.create_app(database=database).test_client()
    text, map_html = page(client, **day("2030-07-02", refresh="1"))
    assert "Fetched 1 new uplinks" in text
    assert markers(map_html) == 5


def test_concurrent_requests_get_their_own_map(webserver, database):
    app = webserver.create_app(database=database)

    def fetch(date):
        return page(app.test_client(), **day(date))[1]

    with ThreadPoolExecutor(max_workers=2) as pool:
        july2, july3 = pool.map(fetch, ["2030-07-02", "2030-07-03"] * 1)
    assert "12.0" not in polyline(july2) and markers(july2) == 4
    assert markers(july3) == 1 and "[12.0, 22.0]" in july3


def test_app_runs_without_write_access_to_templates(webserver, database, tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    shutil.copy(REPO / "templates" / "map.html", templates / "map.html")
    os.chmod(templates, stat.S_IRUSR | stat.S_IXUSR)
    try:
        client = webserver.create_app(database=database, template_folder=str(templates))
        page(client.test_client(), **day("2030-07-02"))
    finally:
        os.chmod(templates, stat.S_IRWXU)
