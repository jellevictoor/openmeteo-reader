"""
Port - Interface for fetching weather readings from an external provider
"""
from abc import ABC, abstractmethod
from datetime import date

from openmeteo_reader.domain.models import WeatherReading


class WeatherSource(ABC):
    """Interface for fetching weather readings for the configured home location"""

    @abstractmethod
    def fetch_recent(self, past_hours: int) -> list[WeatherReading]:
        """
        Fetch the rolling recent window, including hours whose values may still be
        revised as observations land.

        Args:
            past_hours: how many hours of history to include, counting back from now

        Returns:
            One reading per hour, oldest first
        """

    @abstractmethod
    def fetch_historical(self, start: date, end: date) -> list[WeatherReading]:
        """
        Fetch a historical date range for one-off backfill.

        Args:
            start: first day to fetch (inclusive)
            end: last day to fetch (inclusive)

        Returns:
            One reading per hour, oldest first
        """
