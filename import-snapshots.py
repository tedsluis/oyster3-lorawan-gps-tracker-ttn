#!/usr/bin/env python3
"""One-off import of the old json/*.json snapshots into the local SQLite store.

The snapshot files are only read, never changed. Running the import twice is harmless."""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

from oyster3.store import DEFAULT_DATABASE, Store


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database",
        default=os.environ.get("APP_DATABASE") or DEFAULT_DATABASE,
        help=f"SQLite database (default {DEFAULT_DATABASE}).",
    )
    parser.add_argument("--directory", default="json", help="Snapshot directory (default json).")
    return parser.parse_args(argv)


def read_snapshot(path):
    with open(path) as handle:
        data = json.load(handle)
    return [
        item["result"]
        for item in data.get("data", [])
        if isinstance(item, dict) and isinstance(item.get("result"), dict)
    ]


def main(argv=None):
    args = parse_args(argv)
    files = sorted(glob.glob(str(Path(args.directory) / "*.json")))
    new = known = skipped = 0
    with Store(args.database) as store:
        for path in files:
            try:
                results = read_snapshot(path)
            except (OSError, ValueError) as error:
                skipped += 1
                print(f"Skipping {path}: {error}", file=sys.stderr)
                continue
            added, existing = store.upsert(results)
            new += added
            known += existing
        by_port = store.count_by_port()
    print(f"Read {len(files) - skipped} snapshot files ({skipped} skipped).")
    print(f"{new} new uplinks stored, {known} duplicates ignored.")
    total = sum(by_port.values())
    ports = ", ".join(f"port {port}: {count}" for port, count in by_port.items())
    print(f"Store now holds {total} unique uplinks ({ports}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
