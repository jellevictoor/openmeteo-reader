"""
Adapter - Persists weather readings as points in InfluxDB
"""
from influxdb_client import Point

from openmeteo_reader.domain.models import WeatherReading
from openmeteo_reader.ports.weather_repository import WeatherRepository

MEASUREMENT = "openmeteo"


def reading_to_point(reading: WeatherReading) -> Point:
    """
    Translate a WeatherReading into an InfluxDB Point.

    Every field is coerced to float: Open-Meteo returns some variables (humidity,
    cloud cover, weather codes) as JSON integers, and an inconsistent int/float type
    for the same field name across points is a write-rejecting field-type conflict
    in InfluxDB.
    """
    point = Point(MEASUREMENT).tag("location", reading.location).time(reading.timestamp)
    for name, value in reading.values.items():
        point = point.field(name, float(value))
    return point


class InfluxWeatherRepository(WeatherRepository):
    """Writes weather readings to a fixed InfluxDB bucket/org via an injected write API"""

    def __init__(self, bucket: str, org: str, write_api):
        self.bucket = bucket
        self.org = org
        self.write_api = write_api

    def save(self, readings: list[WeatherReading]) -> None:
        if not readings:
            return
        points = [reading_to_point(reading) for reading in readings]
        self.write_api.write(bucket=self.bucket, org=self.org, record=points)
