from datetime import UTC, datetime

from openmeteo_reader.domain.models import WeatherReading
from openmeteo_reader.domain.open_meteo_response import parse_hourly_readings


def test_parses_one_reading_per_timestamp():
    raw = {
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [5.2, 4.8],
            "relative_humidity_2m": [88, 90],
        }
    }

    readings = parse_hourly_readings(raw, location="home")

    assert readings == [
        WeatherReading(
            timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            location="home",
            values={"temperature_2m": 5.2, "relative_humidity_2m": 88},
        ),
        WeatherReading(
            timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
            location="home",
            values={"temperature_2m": 4.8, "relative_humidity_2m": 90},
        ),
    ]


def test_omits_null_values_from_a_reading_instead_of_failing():
    raw = {
        "hourly": {
            "time": ["2024-01-01T00:00"],
            "temperature_2m": [5.2],
            "soil_moisture_0_to_1cm": [None],
        }
    }

    readings = parse_hourly_readings(raw, location="home")

    assert readings == [
        WeatherReading(
            timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            location="home",
            values={"temperature_2m": 5.2},
        ),
    ]


def test_returns_no_readings_when_hourly_block_is_missing():
    assert parse_hourly_readings({}, location="home") == []


def test_returns_no_readings_when_time_series_is_empty():
    raw = {"hourly": {"time": []}}

    assert parse_hourly_readings(raw, location="home") == []
