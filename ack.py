import os
import requests
import time
import json
import base64
import argparse
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(description="Accept a parameter --downlink with an argument (0-36), --sequencenumber [0-127]")
parser.add_argument("--downlink", type=int, choices=range(0, 37), required=True, help="Specify --downlink [0-36].")
parser.add_argument("--sequencenumber", type=int, choices=range(0, 127), required=True, help="Specify --sequencenumber [0-127].")
args = parser.parse_args()

def check_downlink_ack(sequence_number,downlink):
    ttnDevice = os.environ["TTN_DEVICE"]
    ttnApplication = os.environ["TTN_APPLICATION"]
    ttnRegion = os.environ["TTN_REGION"]
    ttnConsole = os.environ["TTN_CONSOLE"]
    ttnAPIKey = os.environ["TTN_API_KEY"]
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
            # Get the current date and time
            current_date = datetime.now() - timedelta(hours=24)

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

                if ack_sequence_number == sequence_number and downlink == downlink_port_number:
                    print(f"MATCH:    acknowledged: received_at: {received_at}, sequence number: {ack_sequence_number}, accepted: {accepted}, downlink_port_number: {downlink_port_number}")
                else:
                    print(f"NO_MATCH: acknowledged: received_at: {received_at}, sequence number: {ack_sequence_number}, accepted: {accepted}, downlink_port_number: {downlink_port_number}")

        print(f"Try again in 30 seconds...")
        time.sleep(30)

check_downlink_ack(args.sequencenumber,args.downlink)