"""
Domain models - Core business entities
"""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# Home's local time. A "day" - for a day's rain total or a day card - runs from
# local midnight to local midnight, not UTC midnight.
HOME_TIMEZONE = ZoneInfo("Europe/Brussels")


@dataclass
class WeatherReading:
    """A single hour of weather data for one location"""
    timestamp: datetime
    location: str
    values: dict[str, float]
