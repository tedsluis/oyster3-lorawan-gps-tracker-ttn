from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from oyster3.timeutil import (
    format_local,
    local_input_to_utc,
    parse_ttn_timestamp,
    to_ttn_timestamp,
)

UTC = timezone.utc


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2025-01-05T13:56:56.256908367Z", datetime(2025, 1, 5, 13, 56, 56, 256908, UTC)),
        ("2025-01-05T13:56:56Z", datetime(2025, 1, 5, 13, 56, 56, tzinfo=UTC)),
        ("2025-01-05T13:56:56.2Z", datetime(2025, 1, 5, 13, 56, 56, 200000, UTC)),
        ("2025-01-05T14:56:56.000+01:00", datetime(2025, 1, 5, 13, 56, 56, tzinfo=UTC)),
        ("2025-01-05T13:56", datetime(2025, 1, 5, 13, 56, tzinfo=UTC)),
    ],
)
def test_parse_ttn_timestamp(text, expected):
    parsed = parse_ttn_timestamp(text)
    assert parsed == expected
    assert parsed.tzinfo is not None


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_ttn_timestamp("yesterday")


def test_to_ttn_timestamp_requires_aware_datetime():
    assert (
        to_ttn_timestamp(datetime(2025, 1, 5, 13, 0, tzinfo=UTC)) == "2025-01-05T13:00:00.000000Z"
    )
    with pytest.raises(ValueError):
        to_ttn_timestamp(datetime(2025, 1, 5, 13, 0))


def test_local_input_to_utc_handles_daylight_saving_time():
    amsterdam = ZoneInfo("Europe/Amsterdam")
    assert local_input_to_utc("2025-01-15T00:00", amsterdam) == datetime(
        2025, 1, 14, 23, 0, tzinfo=UTC
    )
    assert local_input_to_utc("2025-07-15T00:00", amsterdam) == datetime(
        2025, 7, 14, 22, 0, tzinfo=UTC
    )
    # 2025-03-30: clocks jump from 02:00 to 03:00 in Amsterdam
    assert local_input_to_utc("2025-03-30T03:30", amsterdam) == datetime(
        2025, 3, 30, 1, 30, tzinfo=UTC
    )
    assert (
        format_local(datetime(2025, 7, 14, 22, 0, tzinfo=UTC), amsterdam)
        == "2025-07-15 00:00:00 CEST"
    )
