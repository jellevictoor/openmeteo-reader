from datetime import UTC, datetime

from openmeteo_reader.adapters.influx_weather_repository import (
    InfluxWeatherRepository,
    reading_to_point,
)
from openmeteo_reader.domain.models import WeatherReading


class FakeWriteApi:
    def __init__(self):
        self.calls = []

    def write(self, bucket, org, record):
        self.calls.append({"bucket": bucket, "org": org, "record": record})


def test_reading_to_point_has_measurement_tag_time_and_float_fields():
    reading = WeatherReading(
        timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        location="home",
        # relative_humidity_2m arrives from Open-Meteo as a JSON int - it must not
        # end up as an integer-typed Influx field, or a later float value for the
        # same field name would be rejected as a field-type conflict.
        values={"temperature_2m": 5.2, "relative_humidity_2m": 88},
    )

    line = reading_to_point(reading).to_line_protocol()

    assert line == (
        "openmeteo,location=home relative_humidity_2m=88,temperature_2m=5.2 "
        "1704067200000000000"
    )


def test_save_writes_one_point_per_reading_to_the_configured_bucket_and_org():
    write_api = FakeWriteApi()
    repo = InfluxWeatherRepository(bucket="weather", org="klskmp", write_api=write_api)
    readings = [
        WeatherReading(
            timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            location="home",
            values={"temperature_2m": 5.2},
        ),
        WeatherReading(
            timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
            location="home",
            values={"temperature_2m": 4.8},
        ),
    ]

    repo.save(readings)

    assert len(write_api.calls) == 1
    call = write_api.calls[0]
    assert call["bucket"] == "weather"
    assert call["org"] == "klskmp"
    assert len(call["record"]) == 2


def test_save_does_nothing_for_an_empty_batch():
    write_api = FakeWriteApi()
    repo = InfluxWeatherRepository(bucket="weather", org="klskmp", write_api=write_api)

    repo.save([])

    assert write_api.calls == []
