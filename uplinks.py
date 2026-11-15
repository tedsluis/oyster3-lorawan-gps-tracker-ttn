#!/usr/bin/env python3
"""List recent Oyster 3 uplinks from the TTN Storage Integration, decoded per port."""

import argparse
import base64
import sys
from datetime import timedelta

from oyster3.timeutil import utc_now
from oyster3.ttn import TTNConfig, TTNError, fetch_uplinks
from oyster3.uplinks import UplinkDecodeError, decode_uplink


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours", type=float, default=200, help="Look back this many hours (default 200)."
    )
    parser.add_argument(
        "--port",
        type=int,
        action="append",
        help="Only show this uplink port (repeatable), e.g. --port 3 --port 31.",
    )
    return parser.parse_args(argv)


def describe(result):
    message = result.get("uplink_message", {})
    f_port = message.get("f_port")
    try:
        decoded = decode_uplink(f_port, base64.b64decode(message.get("frm_payload", "")))
    except UplinkDecodeError as error:
        decoded = {"type": "invalid", "error": str(error)}
    fields = ", ".join(f"{k}: {v}" for k, v in decoded.items() if k not in ("type", "f_port"))
    return f"{result['received_at']} port {f_port} {decoded['type']}: {fields}"


def main(argv=None):
    args = parse_args(argv)
    try:
        config = TTNConfig.from_env()
        results = fetch_uplinks(config, after=utc_now() - timedelta(hours=args.hours))
    except TTNError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    for result in results:
        if args.port and result.get("uplink_message", {}).get("f_port") not in args.port:
            continue
        print(describe(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
