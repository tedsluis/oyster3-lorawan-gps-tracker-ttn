#!/usr/bin/env python3
"""Build (and optionally send) an Oyster 3 configuration downlink from config.yaml."""
import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime

import requests

from oyster3.downlinks import (
    VALID_PORTS,
    describe_fields,
    encode_downlink,
    load_config,
    non_default_fields,
    validate_config,
)

# Temporary safety lock: sending stays disabled until all golden encoder tests pass.
SEND_LOCKED = True

TABLE_HEADER = ["Downlink", "Byte", "Bit", "Length", "Type", "Value", "Field bits (MSB..LSB)",
                "Payload bytes", "Description"]
TABLE_NOTE = ("Bits are numbered from the least significant bit (bit 0) of each byte, as in the "
              "Digital Matter spec;\nmulti-byte fields are little-endian unless marked "
              "'endian: big'. 'Field bits' is the value the device reads.")

# Function to send a downlink to the Oyster3 device
def send_downlink(confirmed: bool, f_port: int, payload_hex: str):
    """
    Sends a downlink to the Oyster3 device.

    :param confirmed: Whether to confirm the downlink
    :param f_port: Port to send the downlink on
    :param payload_hex: The payload to send in hexadecimal
    """
    # Encode payload in base64
    payload_base64 = base64.b64encode(bytes.fromhex(payload_hex)).decode("utf-8")

    # Downlink URL
    url = f"https://bachstraat20-nl.eu2.cloud.thethings.industries/api/v3/as/applications/{ttnApplication}/devices/{ttnDevice}/down/push"

    # HTTP headers
    headers = {
        "Authorization": f"Bearer {ttnAPIKey}",
        "Content-Type": "application/json",
    }

    # Payload for the API
    downlink_payload = {
        "downlinks": [
            {
                "f_port": f_port,
                "frm_payload": payload_base64,
                "confirmed": confirmed,
            }
        ]
    }

    # Send the downlink request
    response = requests.post(url, json=downlink_payload, headers=headers)

    if response.status_code == 200:
        print(f"Downlink sent successfully. Status code: {response.status_code}, Response: {response.text}")
    else:
        print(f"Failed to send downlink. Status code: {response.status_code}, Response: {response.text}")

# Function to check if the configuration was applied successfully
def confirm_configuration():
    ttnStorageurl = f"https://{ttnConsole}.{ttnRegion}.cloud.thethings.industries/api/v3/as/applications/{ttnApplication}/devices/{ttnDevice}/packages/storage/uplink_message"
    headers = {
        "Authorization": f"Bearer {ttnAPIKey}"
    }

    for _ in range(60):  # Retry up to 10 times (adjust as needed)
        try:
            # Maak een GET-verzoek naar de TTN Storage Integration API
            response = requests.get(ttnStorageurl, headers=headers)
        except Exception as e:
            print(f"Onverwachte fout: {e}")

        # Check response
        print(f"Response Code: {response.status_code}")
        if response.status_code != 200:
            print("Fout bij ophalen van uplinkberichten.")
            response.raise_for_status()

        # Parseer de JSON-response
        ttnJSON = "{\"data\": [" + response.text.replace("\n", ",")[:-1] + "]}"
        someJSON = json.loads(ttnJSON)
        uplink_messages = someJSON["data"]

        # Controleer inkomende uplinks
        for message in uplink_messages:
            uplink = message["result"]
            uplink_message = uplink["uplink_message"]
            f_port = uplink_message["f_port"]
            received_at = uplink["received_at"]
            # Remove the 'Z' at the end of the string for compatibility
            date_string = received_at.rstrip('Z')
            # Parse the date string
            parsed_date = datetime.fromisoformat(date_string)
            # check if received_at > current date
            if f_port == 2 and parsed_date > current_date:
                frm_payload = uplink_message["frm_payload"]
                payload = base64.b64decode(frm_payload)
                ack_sequence_number=int(payload[0] & 0b01111111)   # 0.0 - 0.6 Sequence number (identifies downlink to server)
                accepted=bool(payload[0] & 0b10000000) # 0.7 0: Downlink rejected, 1: Downlink accepted
                # 1 Firmware major version
                # 2 Firmware minor version
                # 3 Product Id (98)
                # 4 Hardware revision
                downlink_port_number=payload[5] # 5 Downlink port number

                if ack_sequence_number == sequence_number and int(args.downlink) == downlink_port_number:
                    print(f"MATCH: received_at: {received_at}, sequence number: {ack_sequence_number}, accepted: {accepted}, downlink_port_number: {downlink_port_number}")
                    return True

        print("Missing Downlink Ack. Try again in 30 seconds...")
        time.sleep(30)

    print("Configuration confirmation timeout.")


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
            print(" | ".join(
                f"{(cell[line_number] if line_number < len(cell) else ''):<{widths[i]}}"
                for i, cell in enumerate(cells)
            ).rstrip())
        print("=" * len(separator) if index == 0 else separator)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downlink", type=int, choices=VALID_PORTS, required=True,
                        help="Downlink port: 1-12 or 30-35.")
    parser.add_argument("--sequencenumber", type=int, choices=range(0, 128), metavar="0-127",
                        help="Override the downlink sequence number from config.yaml.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    parser.add_argument("--send", action="store_true", help="Send the downlink now.")
    return parser.parse_args(argv)


def main(argv=None):
    global args, sequence_number, current_date
    global ttnDevice, ttnApplication, ttnRegion, ttnConsole, ttnAPIKey
    args = parse_args(argv)
    if args.send and SEND_LOCKED:
        sys.exit("Refusing to send: the downlink encoder is known to be wrong (see audit F01). "
                 "Sending is disabled until the encoder is fixed.")

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
    sequence_number = next(
        (args.sequencenumber if args.sequencenumber is not None else f["value"])
        for f in fields if f["name"].startswith("0.0 - 0.6 Downlink sequence number")
    )

    print(f"Send downlink: {args.send}")
    print(f"downlink{args.downlink} Byte Array: {payload.hex()}")
    print()
    print_table(describe_fields(args.downlink, fields, payload, args.sequencenumber))
    for field in non_default_fields(fields):
        print(f"WARNING: not the default value ({field['default']}): {field['name']}")

    if args.send:
        ttnDevice = os.environ["TTN_DEVICE"]
        ttnApplication = os.environ["TTN_APPLICATION"]
        ttnRegion = os.environ["TTN_REGION"]
        ttnConsole = os.environ["TTN_CONSOLE"]
        ttnAPIKey = os.environ["TTN_API_KEY"]
        current_date = datetime.now()
        send_downlink(confirmed=True, f_port=args.downlink, payload_hex=payload.hex())
        print("sequence_number:", sequence_number)
        confirm_configuration()
    return 0


if __name__ == "__main__":
    sys.exit(main())
