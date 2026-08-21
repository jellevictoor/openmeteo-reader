"""
Translates raw Open-Meteo Ensemble API responses into WeatherReading domain objects.
"""
import re
import statistics
from datetime import UTC, datetime

from openmeteo_reader.domain.models import WeatherReading

MEMBER_SUFFIX = re.compile(r"_member\d+$")

# A day's total precipitation can't be reconstructed by summing each hour's
# across-member median: it's common for over half the members to be dry in a
# given hour while a few show a real shower, so the hourly median sits at 0 even
# on a wet day, and summing 24 independently-taken medians is neither the mean
# nor the median of what actually falls. Tracking each member's own running
# total through the day and only then taking min/median/max preserves the
# correlation within one member's realization that a per-hour median discards.
CUMULATIVE_VARIABLES = {"precipitation"}


def parse_ensemble_readings(raw: dict, location: str) -> list[WeatherReading]:
    """
    Parse a raw Open-Meteo Ensemble API response into one WeatherReading per hour,
    collapsing each variable's member columns (e.g. temperature_2m_member01..NN)
    into that hour's min/median/max across all members.

    A member can be null for a given hour; such members are excluded from that
    hour's statistics. A variable with no non-null members for an hour is omitted
    entirely from that hour's reading, matching how parse_hourly_readings treats
    missing values.

    Variables in CUMULATIVE_VARIABLES additionally get a "{variable}_total_*"
    triple: each member's own running total for the UTC calendar day (a null
    hour counts as zero for that member), reset at midnight, reduced to
    min/median/max across members. That's the day's expected total - see
    CUMULATIVE_VARIABLES for why it isn't just summed from the per-hour medians.
    """
    hourly = raw.get("hourly", {})
    timestamps = hourly.get("time", [])

    variables: dict[str, list[str]] = {}
    for column in hourly:
        if column == "time":
            continue
        variable = MEMBER_SUFFIX.sub("", column)
        variables.setdefault(variable, []).append(column)

    running_totals: dict[str, float] = {}
    current_day = None

    readings = []
    for index, timestamp in enumerate(timestamps):
        hour = datetime.fromisoformat(timestamp).replace(tzinfo=UTC)
        if hour.date() != current_day:
            current_day = hour.date()
            running_totals = {}

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

            if variable in CUMULATIVE_VARIABLES:
                totals = []
                for column in member_columns:
                    value = hourly[column][index]
                    running_totals[column] = running_totals.get(column, 0.0) + (
                        value if value is not None else 0.0
                    )
                    totals.append(running_totals[column])
                values[f"{variable}_total_min"] = min(totals)
                values[f"{variable}_total_median"] = statistics.median(totals)
                values[f"{variable}_total_max"] = max(totals)

        readings.append(WeatherReading(timestamp=hour, location=location, values=values))
    return readings
