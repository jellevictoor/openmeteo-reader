"""
Translates raw Open-Meteo Ensemble API responses into WeatherReading domain objects.
"""
import statistics
from datetime import UTC, datetime, tzinfo

from openmeteo_reader.domain.models import WeatherReading

# A day's total precipitation can't be reconstructed by summing each hour's
# across-member median: it's common for over half the members to be dry in a
# given hour while a few show a real shower, so the hourly median sits at 0 even
# on a wet day, and summing 24 independently-taken medians is neither the mean
# nor the median of what actually falls. Tracking each member's own running
# total through the day and only then taking min/median/max preserves the
# correlation within one member's realization that a per-hour median discards.
CUMULATIVE_VARIABLES = {"precipitation"}

# A day with less than this much rain in total reads as dry, so the chance of a
# wet day is the share of members whose total reaches it.
WET_DAY_MM = 1.0


def member_columns(hourly: dict, variable: str) -> list[str]:
    """
    Every column holding one ensemble member of `variable`.

    Open-Meteo names a column "<variable>[_memberNN][_<model>]": a single model's
    control run is just "<variable>", and asking for several models suffixes every
    column with its model. Matching on the requested variable name pools the
    members of all models into one ensemble, whatever the suffix looks like.
    """
    return [c for c in hourly if c == variable or c.startswith(variable + "_")]


def parse_ensemble_readings(
    raw: dict, location: str, variables: list[str], day_zone: tzinfo
) -> list[WeatherReading]:
    """
    Parse a raw Open-Meteo Ensemble API response (timestamps in UTC) into one
    WeatherReading per hour, collapsing each requested variable's member columns,
    across every model in the response, into that hour's min/median/max.

    A member can be null for a given hour; such members are excluded from that
    hour's statistics. A variable with no non-null members for an hour is omitted
    entirely from that hour's reading, matching how parse_hourly_readings treats
    missing values.

    Variables in CUMULATIVE_VARIABLES additionally get a "{variable}_total_*"
    triple: each member's own running total for the calendar day in `day_zone`
    (a null hour counts as zero for that member), reset at local midnight, reduced
    to min/median/max across members - see CUMULATIVE_VARIABLES for why it isn't
    summed from the per-hour medians. "{variable}_total_probability" is the share
    of members, in percent, whose running total has reached WET_DAY_MM.
    """
    hourly = raw.get("hourly", {})
    timestamps = hourly.get("time", [])
    columns = {v: member_columns(hourly, v) for v in variables}
    columns = {v: cols for v, cols in columns.items() if cols}

    running_totals: dict[str, float] = {}
    current_day = None

    readings = []
    for index, timestamp in enumerate(timestamps):
        hour = datetime.fromisoformat(timestamp).replace(tzinfo=UTC)
        local_day = hour.astimezone(day_zone).date()
        if local_day != current_day:
            current_day = local_day
            running_totals = {}

        values = {}
        for variable, member_cols in columns.items():
            members = [hourly[c][index] for c in member_cols if hourly[c][index] is not None]
            if not members:
                continue
            values[f"{variable}_min"] = min(members)
            values[f"{variable}_median"] = statistics.median(members)
            values[f"{variable}_max"] = max(members)

            if variable in CUMULATIVE_VARIABLES:
                totals = []
                for column in member_cols:
                    value = hourly[column][index]
                    running_totals[column] = running_totals.get(column, 0.0) + (
                        value if value is not None else 0.0
                    )
                    totals.append(running_totals[column])
                values[f"{variable}_total_min"] = min(totals)
                values[f"{variable}_total_median"] = statistics.median(totals)
                values[f"{variable}_total_max"] = max(totals)
                wet = sum(1 for t in totals if t >= WET_DAY_MM)
                values[f"{variable}_total_probability"] = 100.0 * wet / len(totals)

        readings.append(WeatherReading(timestamp=hour, location=location, values=values))
    return readings
