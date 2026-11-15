#!/usr/bin/env python3
"""Local Flask webserver that shows the Oyster 3 GPS track on OpenStreetMap.

Data comes from the local SQLite store (see fetch.py). The page never contacts TTN unless
you press "fetch new data".
"""

import base64
import binascii
import os
from datetime import datetime, timedelta

import folium
from flask import Flask, render_template, request, url_for

from oyster3.store import DEFAULT_DATABASE, Store, fetch_new
from oyster3.timeutil import app_timezone, format_local, local_input_to_utc, parse_ttn_timestamp
from oyster3.ttn import TTNConfig, TTNError
from oyster3.uplinks import POSITION_PORTS, UplinkDecodeError, decode_uplink

INPUT_FORMAT = "%Y-%m-%dT%H:%M"
DEFAULT_CENTER = (52.0, 5.0)
FILTERS = ("in_trip", "stopped", "fix_successful", "fix_failed")
ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILTERS = {"in_trip": True, "stopped": True, "fix_successful": True, "fix_failed": False}


def run_settings(environ=os.environ):
    """Safe defaults: local only, debugger off. Override with APP_HOST, APP_PORT, APP_DEBUG."""
    host = environ.get("APP_HOST", "127.0.0.1")
    port = int(environ.get("APP_PORT", "5000"))
    debug = environ.get("APP_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    return host, port, debug


def position_points(rows):
    """Decoded positions from stored uplinks. Only GNSS uplinks (ports 1, 4, 33) are used;
    a failed fix carries the device's cached (previous) position."""
    points = []
    for row in rows:
        if row["f_port"] not in POSITION_PORTS:
            continue
        try:
            payload = base64.b64decode(row["frm_payload"] or "", validate=True)
            decoded = decode_uplink(row["f_port"], payload)
        except (UplinkDecodeError, binascii.Error):
            continue
        location = decoded["cached"] if decoded["fix_failed"] else decoded
        points.append(
            {
                "coords": (location["latitude"], location["longitude"]),
                "received_at": parse_ttn_timestamp(row["received_at"]),
                "f_cnt": row["f_cnt"],
                "consumed_airtime": row["consumed_airtime"],
                "battery": decoded["battery_v"],
                "in_trip": decoded["in_trip"],
                "fix_failed": decoded["fix_failed"],
                "heading_deg": location["heading_deg"],
                "speed": location["speed_kmph"],
            }
        )
    return points


def select_points(points, filters):
    selected = []
    for point in points:
        movement = filters["in_trip"] if point["in_trip"] else filters["stopped"]
        fix = filters["fix_failed"] if point["fix_failed"] else filters["fix_successful"]
        if movement and fix:
            selected.append(point)
    return selected


def marker_kind(point):
    """Failed fixes first (cached position), then stationary, then without movement."""
    if point["fix_failed"]:
        return "cached", "red"
    if not point["in_trip"]:
        return "stopped", "green"
    if point["speed"] == 0:
        return "no-direction", "blue"
    return "arrow", None


def popup_html(point, zone):
    airtime = point["consumed_airtime"] or ""
    lines = [
        f"Index: {point['f_cnt'] if point['f_cnt'] is not None else '-'}",
        f"Consumed airtime: {airtime.rstrip('s')[:5]} seconds" if airtime else None,
        f"Battery: {point['battery']} volt",
        f"In trip: {point['in_trip']}",
        "Fix failed: cached position" if point["fix_failed"] else "Fix failed: False",
        f"Direction: {point['heading_deg']} degrees",
        f"Speed: {point['speed']} km/h",
        f"Time: {format_local(point['received_at'], zone)}",
    ]
    return "<br>".join(line for line in lines if line)


def build_map(points, zone, arrow_url):
    if not points:
        return folium.Map(location=DEFAULT_CENTER, zoom_start=12).get_root().render()
    map_object = folium.Map(location=points[0]["coords"], zoom_start=12)
    route = [point["coords"] for point in points if not point["fix_failed"]]
    if len(route) >= 2:
        folium.PolyLine(route, color="blue", weight=2.5, opacity=1).add_to(map_object)
    for point in points:
        kind, color = marker_kind(point)
        if kind == "arrow":
            icon = folium.DivIcon(
                html=(
                    f'<div style="transform: translate(-50%, -50%) rotate({point["heading_deg"]}'
                    f'deg); width: 32px; height: 32px;"><img src="{arrow_url}" '
                    'style="width: 100%; height: 100%; background: transparent;"/></div>'
                )
            )
        else:
            icon = folium.Icon(color=color)
        folium.Marker(
            location=point["coords"],
            popup=folium.Popup(popup_html(point, zone), max_width=300),
            tooltip="cached position" if kind == "cached" else None,
            icon=icon,
        ).add_to(map_object)
    map_object.fit_bounds([point["coords"] for point in points])
    return map_object.get_root().render()


def read_form(form, method, zone, messages):
    today = datetime.now(zone).date().isoformat()
    defaults = (f"{today}T00:00", f"{today}T23:59")
    values = []
    for key, default in zip(("start_datetime", "end_datetime"), defaults, strict=True):
        text = (form.get(key) or "").strip()
        try:
            datetime.strptime(text, INPUT_FORMAT)
        except ValueError:
            if method == "POST":
                messages.append(f"Invalid or missing {key.replace('_', ' ')}; using {default}.")
            text = default
        values.append(text)
    start, end = values
    if start > end:
        messages.append("The start must be before the end; showing today instead.")
        start, end = defaults
    if method == "POST":
        filters = {name: f"{name}_checked" in form for name in FILTERS}
    else:
        filters = dict(DEFAULT_FILTERS)
    return start, end, filters


def create_app(database=None, template_folder="templates", environ=os.environ):
    app = Flask(__name__, root_path=ROOT, template_folder=template_folder)
    app.config["DATABASE"] = database or environ.get("APP_DATABASE") or DEFAULT_DATABASE

    @app.route("/", methods=["GET", "POST"])
    def index():
        zone = app_timezone(environ)
        messages = []
        start, end, filters = read_form(request.form, request.method, zone, messages)
        with Store(app.config["DATABASE"]) as store:
            if request.method == "POST" and "refresh" in request.form:
                try:
                    new, known = fetch_new(store, TTNConfig.from_env(environ))
                    messages.append(f"Fetched {new} new uplinks from TTN ({known} known).")
                except TTNError as error:
                    messages.append(f"Could not fetch from TTN, showing local data: {error}")
            start_utc = local_input_to_utc(start, zone)
            end_utc = local_input_to_utc(end, zone) + timedelta(seconds=59, microseconds=999999)
            rows = store.query(start_utc, end_utc)
        points = select_points(position_points(rows), filters)
        map_html = build_map(points, zone, url_for("static", filename="images/arrow.png"))
        return render_template(
            "map.html",
            map_html=map_html,
            messages=messages,
            timezone=zone.key,
            start_datetime=start,
            end_datetime=end,
            show_in_trip=filters["in_trip"],
            show_stopped=filters["stopped"],
            show_fix_successful=filters["fix_successful"],
            show_fix_failed=filters["fix_failed"],
        )

    return app


app = create_app()

if __name__ == "__main__":
    host, port, debug = run_settings()
    app.run(host=host, port=port, debug=debug)
