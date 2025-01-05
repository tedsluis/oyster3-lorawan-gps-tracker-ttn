#!/usr/bin/python3
import os, sys, logging, time
import requests
import json
import csv
from datetime import datetime
import struct
import base64
from flask import Flask, render_template, request, url_for
import folium

ttnDevice = os.environ["TTN_DEVICE"]                     # TTN device id
ttnApplication=os.environ["TTN_APPLICATION"]             # TTN application name
ttnRegion = os.environ["TTN_REGION"]		             # TTN region
ttnConsole = os.environ["TTN_CONSOLE"]                   # TTN console name
ttnAPIKey = os.environ["TTN_API_KEY"]                    # TTN API KEY
ttnNumberOfRecords = os.environ["TTN_NUMBER_OF_RECORDS"] # How many records you want, set to 0 if you want everything available
ttnSinceDateTime = os.environ["TTN_SINCE_DATE_TIME"]     # Format is 2020-10-01T12:13:14Z From which date you want the records returned. Note, DS only holds 7 days of data
ttnStorageURL = f"https://{ttnConsole}.{ttnRegion}.cloud.thethings.industries/api/v3/as/applications/{ttnApplication}/devices/{ttnDevice}/packages/storage/uplink_message?order=received_at&type=uplink_message"

def decode_oyster_payload(payload_base64):
	"""
	Decode the Oyster3 payload and extract GPS, battery, and additional telemetry.

	Payload Structure (Example - modify based on actual Oyster3 format):
	[Bytes 0-3] Latitude (int32, 1e7 scaling)
	[Bytes 4-7] Longitude (int32, 1e7 scaling)
	[Byte  8] Movement Status (uint8)
	- Bit 0: inTrip
	- Bit 1: fixFailed
	- Bit 2-7: Heading degrees (1 = 5.625 degree)
	[Byte  9] Speed (uint16, km/h)
	[Byte  10] Battery Level (uint8, 1 = 25mVolt)
	"""
	payload = base64.b64decode(payload_base64)
	try:
		gps_lat = struct.unpack(">i", payload[3:4]+payload[2:3]+payload[1:2]+payload[0:1])[0] / 1e7
	except:
		fix_failed = True
		gps_lat = 0
	try:
		gps_lon = struct.unpack(">i", payload[7:8]+payload[6:7]+payload[5:6]+payload[4:5])[0] / 1e7
	except:
		fix_failed = True
		gps_lon = 0 
	try:
		movement_status = payload[8]
		in_trip = bool(movement_status & 0b00000001)               # Bit 0    1=Moving, 0=Stationary
		fix_failed = bool(movement_status & 0b00000010)            # Bit 1    1=failed, 0=success
		heading_deg = int((movement_status & 0b01111100) * 5.625)  # bit 2-7 degrees
	except:
		in_trip = False
		fix_failed = True
		heading_deg = 0
	try:
		speed_kmph = payload[9]                                    # Decode speed (km/h)
	except:
		speed_kmph = 0
	try:
		battery = int(payload[10] * 25) / 1000                     # Convert battery to mVolt
	except:
		battery = 0
	return (gps_lat,gps_lon,battery,in_trip,fix_failed,heading_deg,speed_kmph)

def fetchGPSdata():

	ttnURL =  ttnStorageURL

	if ttnNumberOfRecords:
		ttnURL += "&limit=" + str(ttnNumberOfRecords)

	if ttnSinceDateTime:
		ttnURL += "&after=" + ttnSinceDateTime

	# These are the headers required in the documentation.
	ttnHeaders = { 'Accept': 'text/event-stream', 'Authorization': 'Bearer ' + ttnAPIKey }

	print("\n\nFetching from data storage  ...\n")

	r = requests.get(ttnURL, headers=ttnHeaders)

	print("URL: " + r.url)
	print("Status: " + str(r.status_code))
	print()

	# The text returned is one block of JSON per uplink with a blank line between.
	# Event Stream (see headers above) is a connection type that sends a message when it 
	# becomes available. This script is about downloading a bunch of records in one go
	# So we have to turn the response in to an array and remove the blank lines.

	ttnJSON = "{\"data\": [" + r.text.replace("\n\n", ",")[:-1] + "]}";

	someJSON = json.loads(ttnJSON)
	# print(json.dumps(someJSON, indent=4))
	someUplinks = someJSON["data"]

	# Output to timestamped file
	now = datetime.now()

	# Write JSON data to a file
	pathNFile = "json/" + ttnDevice + "-" + now.strftime("%Y%m%d%H%M%S") + ".json"
	with open(pathNFile, "w") as file:
		json.dump(someJSON, file, indent=4)

	pathNFile = "file/" + ttnDevice + "-" + now.strftime("%Y%m%d%H%M%S") + ".txt"
	print(pathNFile)
	if (not os.path.isfile(pathNFile)):
		with open(pathNFile, 'a', newline='') as tabFile:
			fw = csv.writer(tabFile, dialect='excel-tab')
			fw.writerow(["received_at", "f_port", "f_cnt", "frm_payload", "rssi", "snr", "consumed_airtime", "gps_lat","gps_lon","battery", "in_trip","fix_failed","heading_deg","speed_kmph"])

	gps_data = []

	for anUplink in someUplinks:
		uplink = anUplink["result"]

		received_at = uplink["received_at"]

		uplink_message = uplink["uplink_message"];
		f_port = uplink_message["f_port"];
		f_cnt = uplink_message.get("f_cnt", "");	# first uplink is zero which is missing
		frm_payload = uplink_message["frm_payload"];
		rssi = uplink_message["rx_metadata"][0]["rssi"];
		try:
			snr = uplink_message["rx_metadata"][0]["snr"];
		except:
			snr="unknown"

		# Simulated uplinks don't include these, hence the 'gets'
		consumed_airtime = uplink_message.get("consumed_airtime", "");	

		gps_lat,gps_lon,battery,in_trip,fix_failed,heading_deg,speed_kmph = decode_oyster_payload(frm_payload)
		if fix_failed == False:
			gps_data.append({"coords": (gps_lat,gps_lon), "f_cnt": f_cnt, "consumed_airtime": consumed_airtime, "battery": battery, "in_trip": in_trip, "fix_failed": fix_failed, "heading_deg": heading_deg, "speed": speed_kmph, "time": received_at} )

		with open(pathNFile, 'a', newline='') as tabFile:
			fw = csv.writer(tabFile, dialect='excel-tab')
			fw.writerow([received_at, f_port, f_cnt, frm_payload, rssi, snr, consumed_airtime, gps_lat, gps_lon, battery, in_trip,fix_failed,heading_deg,speed_kmph])
	return gps_data

# Initialize Flask app
app = Flask(__name__)

@app.route('/',methods=['GET', 'POST'])
def index():
	gps_data=fetchGPSdata()
	
	# select gps data for a specific date
	selected_date = request.form.get('date', None)
	print('selected_date: ',selected_date)
	selected_gps_data=[]
	if selected_date:
		for data in gps_data:
			date,time=data['time'].split('T')
			if selected_date == date:
				selected_gps_data.append(data)
	else:
		selected_gps_data=gps_data
	gps_data=selected_gps_data
	
	# Create a map centered at the first GPS location
	if gps_data:
		start_coords = gps_data[0]["coords"]
		map_object = folium.Map(location=start_coords, zoom_start=12)

		# Add route to the map
		route_coords = [data["coords"] for data in gps_data]
		folium.PolyLine(route_coords, color="blue", weight=2.5, opacity=1).add_to(map_object)

		bounds = []

		# Add markers for each point with speed and time in popup
		for data in gps_data:

			if data['f_cnt'] > 0:

				bounds.append(data["coords"])

				date,time=data['time'].split('T')

				image_url = url_for('static', filename='images/arrow.png')

				if data["in_trip"] == False:
					marker_color = "green"
					icon=folium.Icon(color=marker_color)
				elif data["speed"] == 0:
					marker_color = "blue"
					icon=folium.Icon(color=marker_color)
				elif data["heading_deg"] == 0:
					marker_color = "orange"
					icon=folium.Icon(color=marker_color)
				elif data["fix_failed"] == 1:
					marker_color = "red"
					icon=folium.Icon(color=marker_color)
				else:
					compass_icon_html = f"""
					<div style="transform: translate(-50%, -50%) rotate({data['heading_deg']}deg); 
					width: 32px; 
					height: 32px; ">
					<img src="{image_url}" 
					style="width: 100%; 
					height: 100%;
					background: transparent; "/>
					</div>
					"""
					icon = folium.DivIcon(html=compass_icon_html)

				popup_text = f"Index: {data['f_cnt']}<br>Consumed airtime: {data['consumed_airtime'][:4]} seconds<br>Battery: {data['battery']} volt<br>In trip: {data['in_trip']}<br>Fix failed: {data['fix_failed']}<br>Direction {data['heading_deg']} degrees<br>Speed: {data['speed']} km/h<br>Date: {date}<br>Time: {time[:8]}"
				folium.Marker(
					location=data["coords"],
					popup=folium.Popup(popup_text, max_width=300),
					icon=icon
				).add_to(map_object)

		# set map bounds
		if bounds:
			map_object.fit_bounds(bounds)

	else:
		# create map without markers
		start_coords = (52,5)
		map_object = folium.Map(location=start_coords, zoom_start=12)

	# Save map to an HTML file
	map_object.save('templates/map_content.html')

	# Render the map HTML file in Flask
	return render_template('map.html',selected_date=selected_date)

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)

