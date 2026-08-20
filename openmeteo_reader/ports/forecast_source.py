"""
Port - Interface for fetching an ensemble forecast (spread across model members)
"""
from abc import ABC, abstractmethod

from openmeteo_reader.domain.models import WeatherReading


class ForecastSource(ABC):
    """Interface for fetching a forward-looking forecast with uncertainty spread"""

    @abstractmethod
    def fetch_forecast(self, days: int) -> list[WeatherReading]:
        """
        Fetch an ensemble forecast for the next `days` days, starting today.

        Returns:
            One reading per hour, each holding <variable>_min/_median/_max fields
            summarizing the spread across ensemble members - not raw member values.
        """
