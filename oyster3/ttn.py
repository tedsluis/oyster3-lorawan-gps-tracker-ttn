"""The Things Stack client: the only module that talks HTTP.

Storage Integration: https://www.thethingsindustries.com/docs/integrations/storage/retrieve/
"""

import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from oyster3.timeutil import parse_ttn_timestamp, to_ttn_timestamp
from oyster3.uplinks import UplinkDecodeError, decode_uplink

USER_AGENT = "oyster3-lorawan-gps-tracker-ttn/0.2"
TIMEOUT = 30


class TTNError(Exception):
    pass


@dataclass(frozen=True)
class TTNConfig:
    device: str
    application: str
    region: str
    console: str
    api_key: str
    downlink_api_key: str
    number_of_records: int = 0
    since: str = ""

    @classmethod
    def from_env(cls, environ=os.environ):
        required = ("TTN_DEVICE", "TTN_APPLICATION", "TTN_REGION", "TTN_CONSOLE", "TTN_API_KEY")
        missing = [name for name in required if not environ.get(name)]
        if missing:
            raise TTNError(f"missing environment variables: {', '.join(missing)}")
        records = (environ.get("TTN_NUMBER_OF_RECORDS") or "0").strip()
        try:
            number_of_records = int(records)
        except ValueError:
            raise TTNError(f"TTN_NUMBER_OF_RECORDS must be a number, got {records!r}") from None
        return cls(
            device=environ["TTN_DEVICE"],
            application=environ["TTN_APPLICATION"],
            region=environ["TTN_REGION"],
            console=environ["TTN_CONSOLE"],
            api_key=environ["TTN_API_KEY"],
            downlink_api_key=environ.get("TTN_DOWNLINK_API_KEY") or environ["TTN_API_KEY"],
            number_of_records=max(number_of_records, 0),
            since=(environ.get("TTN_SINCE_DATE_TIME") or "").strip(),
        )

    @property
    def device_url(self):
        return (
            f"https://{self.console}.{self.region}.cloud.thethings.industries/api/v3/as/"
            f"applications/{self.application}/devices/{self.device}"
        )

    @property
    def storage_url(self):
        return f"{self.device_url}/packages/storage/uplink_message"

    @property
    def downlink_url(self):
        return f"{self.device_url}/down/push"


def parse_storage_response(text):
    """Parse a Storage Integration response: one JSON object per line, with or without
    blank lines in between (``Accept: text/event-stream`` or not)."""
    results = []
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as error:
            raise TTNError(f"invalid JSON on line {number}: {error}") from None
        if isinstance(obj, dict) and "result" in obj:
            results.append(obj["result"])
        elif isinstance(obj, dict) and ("code" in obj or "message" in obj or "error" in obj):
            message = obj.get("message") or obj.get("error")
            raise TTNError(f"API error {obj.get('code')}: {message}")
        else:
            raise TTNError(f"unexpected object on line {number}")
    return results


def _headers(api_key, **extra):
    return {"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT, **extra}


def _raise_for_status(response):
    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise TTNError(f"HTTP {response.status_code}: {response.text[:200].strip()}") from None


def fetch_uplinks(config, after=None, limit=None):
    """Stored uplinks, oldest first. ``after`` is an aware datetime or RFC 3339 string."""
    params = {"order": "received_at", "type": "uplink_message"}
    if after is None and config.since:
        after = config.since
    if after is not None:
        params["after"] = after if isinstance(after, str) else to_ttn_timestamp(after)
    limit = config.number_of_records if limit is None else limit
    if limit:
        params["limit"] = str(limit)
    try:
        response = requests.get(
            config.storage_url,
            params=params,
            headers=_headers(config.api_key, Accept="text/event-stream"),
            timeout=TIMEOUT,
        )
    except requests.RequestException as error:
        raise TTNError(f"request to TTN failed: {type(error).__name__}") from None
    _raise_for_status(response)
    return parse_storage_response(response.text)


def push_downlink(config, f_port, payload, confirmed=True):
    body = {
        "downlinks": [
            {
                "f_port": int(f_port),
                "frm_payload": base64.b64encode(bytes(payload)).decode("ascii"),
                "confirmed": bool(confirmed),
            }
        ]
    }
    try:
        response = requests.post(
            config.downlink_url,
            json=body,
            headers=_headers(config.downlink_api_key, **{"Content-Type": "application/json"}),
            timeout=TIMEOUT,
        )
    except requests.RequestException as error:
        raise TTNError(f"request to TTN failed: {type(error).__name__}") from None
    _raise_for_status(response)


def downlink_acks(results, since=None):
    """Decoded downlink acknowledgements (Uplink 2) with their reception time."""
    acks = []
    for result in results:
        message = result.get("uplink_message", {})
        if message.get("f_port") != 2 or "frm_payload" not in message:
            continue
        received_at = parse_ttn_timestamp(result["received_at"])
        if since is not None and received_at < since:
            continue
        try:
            ack = decode_uplink(2, base64.b64decode(message["frm_payload"]))
        except UplinkDecodeError:
            continue
        ack["received_at"] = received_at
        acks.append(ack)
    return acks


def find_ack(acks, sequence, port):
    for ack in acks:
        if ack["sequence"] == sequence and ack["port"] == port:
            return ack
    return None


def wait_for_ack(
    config, sequence, port, since: datetime, attempts=60, interval=30, sleep=time.sleep, log=print
):
    """Poll the Storage Integration for the acknowledgement of one downlink.

    The device sends the ack once, with its next uplink, and the Storage Integration writes
    in batches, so this can take a long time. Only uplinks after ``since`` are requested."""
    window_start = since - timedelta(minutes=1)  # tolerate a small clock difference
    for attempt in range(1, attempts + 1):
        try:
            results = fetch_uplinks(config, after=window_start, limit=100)
        except TTNError as error:
            log(f"Attempt {attempt}/{attempts}: {error}")
        else:
            ack = find_ack(downlink_acks(results, since=window_start), sequence, port)
            if ack is not None:
                return ack
            log(f"Attempt {attempt}/{attempts}: no acknowledgement yet.")
        if attempt < attempts:
            sleep(interval)
    return None


def format_ack(ack):
    return (
        f"received_at: {ack['received_at'].isoformat()}, sequence number: {ack['sequence']}, "
        f"accepted: {ack['accepted']}, downlink_port_number: {ack['port']}"
    )
