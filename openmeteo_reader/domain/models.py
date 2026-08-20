"""
Domain models - Core business entities
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WeatherReading:
    """A single hour of weather data for one location"""
    timestamp: datetime
    location: str
    values: dict[str, float]
