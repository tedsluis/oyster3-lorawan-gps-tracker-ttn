"""Local SQLite store for uplinks (one row per received_at, idempotent upserts)."""

import json
import os
import sqlite3
from pathlib import Path

from oyster3.timeutil import parse_ttn_timestamp
from oyster3.ttn import fetch_uplinks

DEFAULT_DATABASE = Path("data") / "uplinks.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS uplinks (
    received_at TEXT PRIMARY KEY,
    received_ts REAL NOT NULL,
    f_port INTEGER,
    f_cnt INTEGER,
    frm_payload TEXT,
    rssi REAL,
    snr REAL,
    consumed_airtime TEXT,
    raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS uplinks_received_ts ON uplinks (received_ts);
"""


def _private_file(path: Path) -> None:
    """Create the database directory (0700) and file (0600): uplinks contain locations.
    An existing directory is left alone; it may be shared (e.g. /tmp)."""
    if not path.parent.exists():
        path.parent.mkdir(parents=True, mode=0o700)
        os.chmod(path.parent, 0o700)
    if not path.exists():
        path.touch(mode=0o600)
    os.chmod(path, 0o600)


def _row(result):
    message = result.get("uplink_message") or {}
    rx_metadata = message.get("rx_metadata") or [{}]
    first = rx_metadata[0] if isinstance(rx_metadata[0], dict) else {}
    try:
        f_cnt = int(message["f_cnt"]) if "f_cnt" in message else None
    except (TypeError, ValueError):
        f_cnt = None
    received_at = result["received_at"]
    return (
        received_at,
        parse_ttn_timestamp(received_at).timestamp(),
        message.get("f_port"),
        f_cnt,
        message.get("frm_payload"),
        first.get("rssi"),
        first.get("snr"),
        message.get("consumed_airtime"),
        json.dumps(result, separators=(",", ":"), sort_keys=True),
    )


class Store:
    def __init__(self, path=DEFAULT_DATABASE):
        self.path = Path(path)
        _private_file(self.path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def upsert(self, results):
        """Insert results that are not stored yet. Returns (new, already_known)."""
        new = known = 0
        with self.db:
            for result in results:
                if not result.get("received_at"):
                    continue
                cursor = self.db.execute(
                    "INSERT OR IGNORE INTO uplinks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", _row(result)
                )
                if cursor.rowcount:
                    new += 1
                else:
                    known += 1
        return new, known

    def query(self, start=None, end=None):
        """Rows with start <= received_at <= end (aware datetimes), oldest first."""
        sql, params = "SELECT * FROM uplinks", []
        conditions = []
        if start is not None:
            conditions.append("received_ts >= ?")
            params.append(start.timestamp())
        if end is not None:
            conditions.append("received_ts <= ?")
            params.append(end.timestamp())
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY received_ts"
        return [dict(row) for row in self.db.execute(sql, params)]

    def latest_received_at(self):
        row = self.db.execute(
            "SELECT received_at FROM uplinks ORDER BY received_ts DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def count_by_port(self):
        rows = self.db.execute("SELECT f_port, COUNT(*) FROM uplinks GROUP BY f_port ORDER BY 1")
        return {port: count for port, count in rows}


def fetch_new(store, config):
    """Fetch uplinks after the newest stored one (or TTN_SINCE_DATE_TIME) and store them.
    Nothing is written when the request fails (TTNError propagates)."""
    after = store.latest_received_at() or config.since or None
    results = fetch_uplinks(config, after=after)
    return store.upsert(results)
