import base64

import pytest


def test_webserver_port1_decoding_matches_spec(script):
    webserver = script("webserver.py")
    row = {
        "f_port": 1,
        "frm_payload": base64.b64encode(bytes.fromhex("53AB783C0421F98E940AB3")).decode(),
        "received_at": "2025-01-05T13:56:56.256908367Z",
        "f_cnt": 7,
        "consumed_airtime": "0.991232s",
    }
    (point,) = webserver.position_points([row])
    assert point["coords"] == pytest.approx((101.4541139, -189.6275708))
    assert point["heading_deg"] == pytest.approx(208.125)  # audit F05: was 112
    assert point["battery"] == pytest.approx(4.475)  # audit F31: volt
    assert (point["in_trip"], point["fix_failed"], point["speed"]) == (False, False, 10)
