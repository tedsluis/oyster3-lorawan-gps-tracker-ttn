#!/usr/bin/env python3
"""Check Oyster 3 downlink acknowledgements (Uplink 2) in the TTN Storage Integration."""

import argparse
import sys
from datetime import timedelta

from oyster3.downlinks import VALID_PORTS
from oyster3.timeutil import utc_now
from oyster3.ttn import (
    TTNConfig,
    TTNError,
    downlink_acks,
    fetch_uplinks,
    format_ack,
    wait_for_ack,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--downlink", type=int, choices=VALID_PORTS, help="Downlink port: 1-12 or 30-35."
    )
    parser.add_argument(
        "--sequencenumber",
        type=int,
        choices=range(0, 128),
        metavar="0-127",
        help="Downlink sequence number 0-127.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="List all acknowledgements in the period once, without polling.",
    )
    parser.add_argument(
        "--hours", type=float, default=24, help="Look back this many hours (default 24)."
    )
    parser.add_argument("--attempts", type=int, default=60, help="Polling attempts (default 60).")
    parser.add_argument(
        "--interval", type=int, default=30, help="Seconds between attempts (default 30)."
    )
    args = parser.parse_args(argv)
    if not args.history and (args.downlink is None or args.sequencenumber is None):
        parser.error("--downlink and --sequencenumber are required unless --history is given")
    return args


def main(argv=None):
    args = parse_args(argv)
    since = utc_now() - timedelta(hours=args.hours)
    try:
        config = TTNConfig.from_env()
        if args.history:
            acks = downlink_acks(fetch_uplinks(config, after=since), since=since)
            if not acks:
                print(f"No acknowledgements in the last {args.hours:g} hours.")
            for ack in acks:
                print(format_ack(ack))
            return 0
    except TTNError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    ack = wait_for_ack(
        config,
        args.sequencenumber,
        args.downlink,
        since,
        attempts=args.attempts,
        interval=args.interval,
    )
    if ack is None:
        print(
            f"NO_MATCH: no acknowledgement of downlink {args.downlink} with sequence number "
            f"{args.sequencenumber} after {args.attempts} attempts."
        )
        return 1
    print(f"MATCH: {format_ack(ack)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
