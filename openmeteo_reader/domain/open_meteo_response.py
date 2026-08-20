"""
Translates raw Open-Meteo "hourly" API responses into WeatherReading domain objects.
"""
from datetime import UTC, datetime

from openmeteo_reader.domain.models import WeatherReading


def parse_hourly_readings(raw: dict, location: str) -> list[WeatherReading]:
    """
    Parse a raw Open-Meteo API response's "hourly" block into WeatherReading objects.

    Open-Meteo returns one time series per variable, all indexed against a shared
    "time" array. A variable can be null for a given hour (e.g. not modelled at that
    depth/height); such values are omitted from that hour's reading rather than
    failing the whole parse, since the source variable set differs between the
    Forecast and Historical APIs and changes over time.

    Assumes the caller requested the response with timezone=UTC, so the naive
    timestamps Open-Meteo returns are interpreted as UTC.
    """
    hourly = raw.get("hourly", {})
    timestamps = hourly.get("time", [])
    variable_names = [name for name in hourly if name != "time"]

    readings = []
    for index, timestamp in enumerate(timestamps):
        values = {
            name: hourly[name][index]
            for name in variable_names
            if hourly[name][index] is not None
        }
        readings.append(
            WeatherReading(
                timestamp=datetime.fromisoformat(timestamp).replace(tzinfo=UTC),
                location=location,
                values=values,
            )
        )
    return readings
