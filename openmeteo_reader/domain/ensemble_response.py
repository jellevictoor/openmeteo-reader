"""
Translates raw Open-Meteo Ensemble API responses into WeatherReading domain objects.
"""
import re
import statistics
from datetime import UTC, datetime

from openmeteo_reader.domain.models import WeatherReading

MEMBER_SUFFIX = re.compile(r"_member\d+$")


def parse_ensemble_readings(raw: dict, location: str) -> list[WeatherReading]:
    """
    Parse a raw Open-Meteo Ensemble API response into one WeatherReading per hour,
    collapsing each variable's member columns (e.g. temperature_2m_member01..NN)
    into that hour's min/median/max across all members.

    A member can be null for a given hour; such members are excluded from that
    hour's statistics. A variable with no non-null members for an hour is omitted
    entirely from that hour's reading, matching how parse_hourly_readings treats
    missing values.
    """
    hourly = raw.get("hourly", {})
    timestamps = hourly.get("time", [])

    variables: dict[str, list[str]] = {}
    for column in hourly:
        if column == "time":
            continue
        variable = MEMBER_SUFFIX.sub("", column)
        variables.setdefault(variable, []).append(column)

    readings = []
    for index, timestamp in enumerate(timestamps):
        values = {}
        for variable, member_columns in variables.items():
            members = [
                hourly[column][index]
                for column in member_columns
                if hourly[column][index] is not None
            ]
            if not members:
                continue
            values[f"{variable}_min"] = min(members)
            values[f"{variable}_median"] = statistics.median(members)
            values[f"{variable}_max"] = max(members)

        readings.append(
            WeatherReading(
                timestamp=datetime.fromisoformat(timestamp).replace(tzinfo=UTC),
                location=location,
                values=values,
            )
        )
    return readings
