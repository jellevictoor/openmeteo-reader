"""
Application service - Orchestrates fetching weather data and storing it
"""
from datetime import date, timedelta

from openmeteo_reader.ports.weather_repository import WeatherRepository
from openmeteo_reader.ports.weather_source import WeatherSource

DEFAULT_CORRECTION_WINDOW_HOURS = 6
DEFAULT_BACKFILL_CHUNK_DAYS = 30


class WeatherImportService:
    """Fetches weather readings from a WeatherSource and persists them"""

    def __init__(
        self,
        weather_source: WeatherSource,
        repository: WeatherRepository,
        correction_window_hours: int = DEFAULT_CORRECTION_WINDOW_HOURS,
    ):
        self.weather_source = weather_source
        self.repository = repository
        self.correction_window_hours = correction_window_hours

    def import_recent(self) -> int:
        """
        Fetch and save the rolling recent window, re-writing the correction buffer
        so hours that Open-Meteo has since revised get overwritten.

        Returns:
            Number of readings written
        """
        readings = self.weather_source.fetch_recent(self.correction_window_hours)
        self.repository.save(readings)
        return len(readings)

    def backfill(
        self,
        start: date,
        end: date,
        chunk_days: int = DEFAULT_BACKFILL_CHUNK_DAYS,
    ) -> int:
        """
        Fetch and save historical data for [start, end], one chunk at a time to
        keep individual requests reasonably sized.

        Returns:
            Total number of readings written across all chunks
        """
        total = 0
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end)
            readings = self.weather_source.fetch_historical(chunk_start, chunk_end)
            self.repository.save(readings)
            total += len(readings)
            chunk_start = chunk_end + timedelta(days=1)
        return total
