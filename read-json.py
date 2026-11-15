import json
from datetime import datetime
import os
import glob
from pprint import pprint

def ExtractDateTime(json_file):
    # Extract the date portion of the filename
    filename = os.path.basename(json_file)
    date_str = filename.split('-')[-1].split('.')[0]  # Extract the YYYYmmddHHMMSS part
    return datetime.strptime(date_str, "%Y%m%d%H%M%S")

def SelectJsonData(startdate,enddate):
    # Initialize an empty dictionary to store filtered data
    jsondict = []
    records = {}
    counter=0
    oldest_date=datetime.strptime(enddate, "%Y-%m-%dT%H:%M:%SZ").timestamp()
    newest_date=datetime.strptime(startdate, "%Y-%m-%dT%H:%M:%SZ").timestamp()

    # Read json file >= startdate
    json_files = glob.glob("json/*.json")
    start_date = datetime.strptime(startdate, "%Y-%m-%dT%H:%M:%SZ")
    json_files = [f for f in json_files if datetime.strptime(f.split('-')[-1].split('.')[0], "%Y%m%d%H%M%S") >= start_date]

    # Sort the files by their modification time (oldest first)
    json_files.sort(key=lambda x: os.path.getmtime(x))

    # Group files by date and find the latest file of each day
    files_by_date = {}
    for json_file in json_files:
        file_datetime = ExtractDateTime(json_file) 
        # Extract the date without time (YYYY-mm-dd)
        date_only = file_datetime.strftime("%Y-%m-%d")
        # Track the latest file for each day
        if date_only not in files_by_date or file_datetime > ExtractDateTime(files_by_date[date_only]):
            files_by_date[date_only] = json_file

    # Loop through each JSON file
    for json_file in files_by_date.values():
        # Read the file and load the JSON data
        with open(json_file, 'r') as file:
            data = json.load(file)
            for item in data.get("data", []):
                # Extract the received_at date
                received_at = item.get("result", {}).get("received_at", "")
                
                if received_at:
                    # Check if the date is within the start and end dates
                    received_at=received_at[:26]+'Z'
                    dt=datetime.strptime(received_at, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
                    sdt=datetime.strptime(startdate, "%Y-%m-%dT%H:%M:%SZ").timestamp()
                    edt=datetime.strptime(enddate, "%Y-%m-%dT%H:%M:%SZ").timestamp()
                    if sdt <= dt and dt <= edt:
                        # Determine whether dt is the oldest or the newest date
                        if dt > newest_date:
                            newest_date=dt
                        if dt < oldest_date:
                            oldest_date=dt
                        # Check if item already in jsondict
                        if received_at not in records:
                            jsondict.append(item)
                            counter+=1
                            records[received_at]=counter
    return oldest_date,newest_date,jsondict

# Now, jsondict will contain the filtered results
# Define your start and end dates in the desired format
startdate = "2025-01-10T00:00:00Z"
enddate = "2025-01-12T23:59:59Z"

oldest_date,newest_date,jsondict=SelectJsonData(startdate,enddate)

pprint(jsondict)
print(oldest_date)
print(newest_date)
