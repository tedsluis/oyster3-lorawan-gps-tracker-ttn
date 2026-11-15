import base64

import pytest


def test_webserver_port1_decoding_matches_spec(script):
    webserver = script("webserver.py")
    payload = base64.b64encode(bytes.fromhex("53AB783C0421F98E940AB3")).decode()
    decoded = webserver.decode_oyster_payload(payload)
    lat, lon, battery, in_trip, fix_failed, heading, speed = decoded
    assert lat == pytest.approx(101.4541139)
    assert lon == pytest.approx(-189.6275708)
    assert heading == pytest.approx(208.125)  # audit F05: was 112
    assert battery == pytest.approx(4.475)  # audit F31: volt
    assert (in_trip, fix_failed, speed) == (False, False, 10)
