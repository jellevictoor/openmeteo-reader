"""
Port - Interface for reading back stored weather data (for the website/API)
"""
from abc import ABC, abstractmethod
from datetime import datetime

from openmeteo_reader.domain.models import WeatherReading


class WeatherQueryRepository(ABC):
    """Interface for reading weather data back out of storage"""

    @abstractmethod
    def latest(self) -> WeatherReading | None:
        """The most recently stored reading, or None if nothing has been written yet"""

    @abstractmethod
    def series(self, variable: str, since: datetime) -> list[tuple[datetime, float]]:
        """
        A single variable's values from `since` up to now, oldest first.

        Args:
            variable: the field name to read (e.g. "temperature_2m")
            since: earliest timestamp to include
        """
