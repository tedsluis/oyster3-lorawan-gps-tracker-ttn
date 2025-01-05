import os
import requests
import base64
import time
import yaml
import json
from bitstring import BitArray
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description="Accept a parameter --downlink with an argument (0-36).")
parser.add_argument("--downlink", type=int, choices=range(0, 37), required=True, help="Specify --downlink [0-36].")
parser.add_argument("--send", action="store_true", help="Specify --send to send downlink now.")
args = parser.parse_args()

print(f"Send downlink: {args.send}")

# TTN configuration
ttnDevice = os.environ["TTN_DEVICE"]                     # TTN device id
ttnApplication=os.environ["TTN_APPLICATION"]             # TTN application id
ttnRegion = os.environ["TTN_REGION"]		             # TTN region
ttnConsole = os.environ["TTN_CONSOLE"]                   # TTN console name
ttnAPIKey = os.environ["TTN_API_KEY"]                    # TTN API KEY

configdata=[]
sequence_number=0
# Get the current date and time
current_date = datetime.now()

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

# load config.yaml
def load_yaml_config(file_path):
    """Load YAML configuration file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# parse values
def parse_value(value, value_type):
    """Parse the value based on its type."""
    if isinstance(value, str) and value.endswith('B'):
        return int(value[:-1], 2)  # Binary
    elif isinstance(value, str) and value.endswith('H'):
        return int(value[:-1], 16)  # Hexadecimal
    elif value_type == 'boolean':
        return 1 if value else 0
    else:
        return int(value)  # Decimal

# Add a value to the byte array at a specific position.
def add_to_bytearray(byte_array, value, byte_index, bit_index=None, length=8):
    if bit_index is not None:
        # Handle bit manipulation
        bit_array = BitArray(bytes=byte_array)
        bit_array.overwrite(BitArray(uint=value, length=length), byte_index * 8 + bit_index)
        byte_array[:] = bit_array.bytes
    else:
        # Handle byte-level insertion
        for i in range(length):
            byte_array[byte_index + i] = (value >> (8 * (length - 1 - i))) & 0xFF

# Normalize the hex string (remove spaces, ensure even length)
def get_bytes_from_hex(hex_string, start_byte, num_bytes):
    hex_string = hex_string.replace(" ", "").lower()
    if len(hex_string) % 2 != 0:
        raise ValueError("Hex string must have an even number of characters (valid bytes).")
    
    # Calculate the start and end indices in the hex string
    start_index = start_byte * 2  # Each byte is 2 hex characters
    end_index = start_index + num_bytes * 2
    
    # Extract and return the desired substring
    return hex_string[start_index:end_index]

# convert hexstring to bits
def convert_to_bits(hex_string):
    binary_representation = bin(int(hex_string, 16))[2:]  # Convert hex to binary and remove '0b'
    binary_representation = binary_representation.zfill(len(hex_string) * 4)  # Pad to full bit length
    return binary_representation

# high changed bits
def highlight_bits(bit_string, start_bit, num_bits):
    # Validate the input
    if start_bit < 0 or start_bit + num_bits > len(bit_string):
        raise ValueError("Invalid start bit or number of bits to highlight.")
    
    # Split the string into parts: before, highlighted, and after
    before = bit_string[:start_bit]
    highlight = bit_string[start_bit:start_bit + num_bits]
    after = bit_string[start_bit + num_bits:]
    
    # Use to highlight
    START = "["
    RESET = "]"
    
    # Combine the parts and print with color
    highlighted_string = f"{before}{START}{highlight}{RESET}{after}"
    return highlighted_string

# Generate a byte array for a specific downlink configuration.
def generate_byte_array(downlink_config,downlink):
    max_byte = 0
    for item in downlink_config:
        byte_start = item['byte']
        if 'bit' in item:
            max_byte = max(max_byte, byte_start + (item['bit'] + item['length'] - 1) // 8)
        else:
            max_byte = max(max_byte, byte_start + item['length'] - 1)

    byte_array = bytearray(max_byte + 1)

    for item in downlink_config:
        global sequence_number
        value = parse_value(item['value'], item['type'])
        byte_index = item['byte']
        bit_index = item.get('bit')
        length = item['length']

        if bit_index is not None:
            add_to_bytearray(byte_array, value, byte_index, bit_index, length)
        else:
            add_to_bytearray(byte_array, value, byte_index, length=length)

        arraybyte = ':'.join(byte_array.hex()[i:i+2] for i in range(0, len(byte_array.hex()), 2))
        arraybyte = ':' + arraybyte + ':'

        if 'Downlink sequence number' in item['name']:
            sequence_number=value

        # Debug info
        if bit_index is not None:
            # format bits to bitstring
            bytes=get_bytes_from_hex(byte_array.hex(), item['byte'], int( (item['length'] + item['bit'] -1)/8 )+1 )
            bits=convert_to_bits(bytes)
            bits=highlight_bits(bits, item['bit'], item['length'])
            modified_string = arraybyte[:(item['byte']*3)] + '[' + arraybyte[(item['byte']*3) + 1:]
            arraybyte = modified_string[:(item['byte']*3+(int( (item['length'] + item['bit'] -1)/8 )+1)*3)] + ']' + modified_string[(item['byte']*3+(int( (item['length'] + item['bit'] -1)/8 )+1)*3) + 1:]
            configdata.append([downlink,item['byte'],item['bit'],item['length'],item['type'],item['value'],bits,arraybyte,item['name']])
        else:
            # format bytesbitstring
            bytes=get_bytes_from_hex(byte_array.hex(), item['byte'], item['length'])
            bits=convert_to_bits(bytes)
            modified_string = arraybyte[:(item['byte']*3)] + '[' + arraybyte[(item['byte']*3) + 1:]
            arraybyte = modified_string[:(item['byte']*3+item['length']*3)] + ']' + modified_string[(item['byte']*3+item['length']*3) + 1:]
            configdata.append([downlink,item['byte'],'-',item['length'],item['type'],item['value'],'['+bits+']',arraybyte,item['name']])

    return byte_array

def print_table(data):
    """
    Prints a table based on an array of arrays with columns as narrow as possible, 
    but consistent across all rows. Columns are wrapped if content exceeds 40 characters.
    
    :param data: List of lists representing the table data
    """
    max_width = 70  # Maximum column width
    # Determine the minimum width for each column
    col_widths = [
        min(
            max(len(str(row[i])) for row in data if i < len(row)), 
            max_width
        ) for i in range(max(len(row) for row in data))
    ]

    def wrap_cell(content, width):
        """Wrap the content to fit within the specified width."""
        words = str(content).split()
        lines, current_line = [], []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + len(current_line) > width:
                lines.append(" ".join(current_line))
                current_line, current_length = [], 0
            current_line.append(word)
            current_length += len(word)
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines

    # Prepare the formatted rows
    formatted_rows = []
    for row in data:
        # Wrap each cell and align all rows for consistency
        wrapped_row = [wrap_cell(row[i] if i < len(row) else "", col_widths[i]) for i in range(len(col_widths))]
        max_lines = max(len(cell) for cell in wrapped_row)
        formatted_rows.append(
            [
                [wrapped_row[i][j] if j < len(wrapped_row[i]) else "" for i in range(len(wrapped_row))]
                for j in range(max_lines)
            ]
        )

    # Print the table
    header='x'
    for row in formatted_rows:
        for line in row:
            if line[0]!='' and header!=line[0]:
                header=line[0]
                print()
                print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(['D','B','B','L','Type','V','Bitstring','Bytearray','Description'])))
                print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(['o','y','i','e','    ','a','         ','         ','           '])))
                print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(['w','t','t','n','    ','l','[effected','[effected','           '])))
                print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(['n','e',' ','g','    ','u','bit(s)]  ','byte(s)] ','           '])))
                print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(['l',' ',' ','t','    ','e','         ','         ','           '])))
                print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(['k',' ',' ','h','    ',' ','         ','         ','           '])))
                print("=" * (sum(col_widths) + 3 * (len(col_widths) - 1)))  # Separator line
            print(" | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(line)))
        print("-" * (sum(col_widths) + 3 * (len(col_widths) - 1)))  # Separator line

def main(config_file):
    """Main function to process the YAML config and generate byte arrays."""
    config = load_yaml_config(config_file)
    for downlink_key, downlink_config in config.get('config', {}).items():
        downlink=downlink_key.replace('downlink', '')
        
        if int(args.downlink) == int(downlink):
            # construct byte array
            byte_array = generate_byte_array(downlink_config,downlink)
            print(f"{downlink_key} Byte Array: {byte_array.hex()}")

            if bool(args.send):
                # Send byte array to the downlink
                send_downlink(confirmed=True, f_port=downlink, payload_hex=byte_array.hex())

                # Confirm the configuration was applied
                print('sequence_number:', sequence_number)
                confirm_configuration()

    print_table(configdata)

if __name__ == "__main__":
    main("config.yaml")