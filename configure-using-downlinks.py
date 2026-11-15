#!/usr/bin/env python3
"""Build (and optionally send) an Oyster 3 configuration downlink from config.yaml."""

import argparse
import sys

from oyster3.downlinks import (
    VALID_PORTS,
    describe_fields,
    encode_downlink,
    load_config,
    non_default_fields,
    validate_config,
)
from oyster3.timeutil import utc_now
from oyster3.ttn import TTNConfig, TTNError, format_ack, push_downlink, wait_for_ack

TABLE_HEADER = [
    "Downlink",
    "Byte",
    "Bit",
    "Length",
    "Type",
    "Value",
    "Field bits (MSB..LSB)",
    "Payload bytes",
    "Description",
]
TABLE_NOTE = (
    "Bits are numbered from the least significant bit (bit 0) of each byte, as in the "
    "Digital Matter spec;\nmulti-byte fields are little-endian unless marked "
    "'endian: big'. 'Field bits' is the value the device reads."
)


def print_table(rows, max_width=70):
    data = [TABLE_HEADER, *rows]
    widths = [max(len(row[i]) for row in data) for i in range(len(TABLE_HEADER))]
    widths[-1] = min(widths[-1], max_width)

    def wrap(text, width):
        lines, line = [], ""
        for word in text.split():
            if line and len(line) + 1 + len(word) > width:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}" if line else word
        return lines + [line] if line else lines or [""]

    separator = "-" * (sum(widths) + 3 * (len(widths) - 1))
    print(TABLE_NOTE)
    print()
    for index, row in enumerate(data):
        cells = [wrap(cell, widths[i]) for i, cell in enumerate(row)]
        for line_number in range(max(len(cell) for cell in cells)):
            print(
                " | ".join(
                    f"{(cell[line_number] if line_number < len(cell) else ''):<{widths[i]}}"
                    for i, cell in enumerate(cells)
                ).rstrip()
            )
        print("=" * len(separator) if index == 0 else separator)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--downlink",
        type=int,
        choices=VALID_PORTS,
        required=True,
        help="Downlink port: 1-12 or 30-35.",
    )
    parser.add_argument(
        "--sequencenumber",
        type=int,
        choices=range(0, 128),
        metavar="0-127",
        help="Override the downlink sequence number from config.yaml.",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    parser.add_argument("--send", action="store_true", help="Send the downlink now.")
    parser.add_argument(
        "--attempts",
        type=int,
        default=60,
        help="How often to look for the acknowledgement after sending (default 60).",
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Seconds between attempts (default 30)."
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)
    problems = validate_config(config)
    if problems:
        print("config.yaml does not match the Oyster 3 spec:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    fields = config[args.downlink]
    try:
        payload = encode_downlink(args.downlink, fields, sequence=args.sequencenumber)
    except ValueError as error:
        print(f"downlink{args.downlink}: {error}", file=sys.stderr)
        return 2
    sequence = payload[0] & 0x7F

    print(f"Send downlink: {args.send}")
    print(f"downlink{args.downlink} Byte Array: {payload.hex()}")
    print()
    print_table(describe_fields(args.downlink, fields, payload, args.sequencenumber))
    for field in non_default_fields(fields):
        print(f"WARNING: not the default value ({field['default']}): {field['name']}")
    if not args.send:
        return 0
    return send_and_confirm(args, payload, sequence)


def send_and_confirm(args, payload, sequence):
    try:
        ttn_config = TTNConfig.from_env()
        sent_at = utc_now()
        push_downlink(ttn_config, args.downlink, payload)
    except TTNError as error:
        print(f"Failed to send downlink: {error}", file=sys.stderr)
        return 1
    print(f"Downlink queued on port {args.downlink} with sequence number {sequence}.")
    print(
        "Waiting for the acknowledgement (Uplink 2). The device sends it once, with its next "
        "uplink, and the Storage Integration is not real-time, so this can take a while."
    )
    ack = wait_for_ack(
        ttn_config, sequence, args.downlink, sent_at, attempts=args.attempts, interval=args.interval
    )
    if ack is None:
        print(
            f"No acknowledgement after {args.attempts} attempts. This does not mean the "
            f"configuration failed; check later with: python ack.py --downlink "
            f"{args.downlink} --sequencenumber {sequence}"
        )
        return 1
    print(f"MATCH: {format_ack(ack)}")
    if not ack["accepted"]:
        print("The device REJECTED this downlink.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
