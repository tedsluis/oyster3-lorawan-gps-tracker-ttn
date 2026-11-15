#!/usr/bin/env python3
"""Fetch new uplinks from the TTN Storage Integration into the local SQLite store.

TTN keeps stored uplinks for 30 days (The Things Stack Cloud; 24 hours on Sandbox), so run
this at least daily, for example from a systemd timer or cron (see README). It is safe to
run repeatedly: only uplinks after the newest stored one are requested, and duplicates are
ignored.
"""

import argparse
import base64
import csv
import os
import sys

from oyster3.store import DEFAULT_DATABASE, Store, fetch_new
from oyster3.ttn import TTNConfig, TTNError
from oyster3.uplinks import UplinkDecodeError, decode_uplink

TSV_HEADER = [
    "received_at", "f_port", "f_cnt", "frm_payload", "rssi", "snr", "consumed_airtime",
    "gps_lat", "gps_lon", "battery", "in_trip", "fix_failed", "heading_deg", "speed_kmph",
]  # fmt: skip


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database",
        default=os.environ.get("APP_DATABASE") or DEFAULT_DATABASE,
        help=f"SQLite database (default {DEFAULT_DATABASE}).",
    )
    parser.add_argument(
        "--export-tsv",
        metavar="PATH",
        help="Do not fetch; export all stored uplinks as tab-separated values.",
    )
    return parser.parse_args(argv)


def tsv_row(row):
    decoded = {}
    try:
        decoded = decode_uplink(row["f_port"], base64.b64decode(row["frm_payload"] or ""))
    except UplinkDecodeError:
        pass
    position = {}
    if decoded.get("type") == "position":
        position = decoded if not decoded["fix_failed"] else {**decoded, **decoded["cached"]}
    values = [
        row["received_at"], row["f_port"], row["f_cnt"], row["frm_payload"], row["rssi"],
        row["snr"], row["consumed_airtime"], position.get("latitude"), position.get("longitude"),
        position.get("battery_v"), position.get("in_trip"), position.get("fix_failed"),
        position.get("heading_deg"), position.get("speed_kmph"),
    ]  # fmt: skip
    return ["" if value is None else value for value in values]


def export_tsv(store, path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", newline="") as handle:
        writer = csv.writer(handle, dialect="excel-tab")
        writer.writerow(TSV_HEADER)
        rows = store.query()
        for row in rows:
            writer.writerow(tsv_row(row))
    return len(rows)


def main(argv=None):
    args = parse_args(argv)
    with Store(args.database) as store:
        if args.export_tsv:
            count = export_tsv(store, args.export_tsv)
            print(f"Exported {count} uplinks to {args.export_tsv}.")
            return 0
        try:
            new, known = fetch_new(store, TTNConfig.from_env())
        except TTNError as error:
            print(f"Error: {error}. Nothing was stored.", file=sys.stderr)
            return 1
    print(f"{new} new uplinks stored, {known} already known.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
