"""
Application service - Refreshes the ensemble forecast and stores it
"""
from openmeteo_reader.ports.forecast_source import ForecastSource
from openmeteo_reader.ports.weather_repository import WeatherRepository

DEFAULT_HORIZON_DAYS = 8


class ForecastImportService:
    """Fetches the ensemble forecast from a ForecastSource and persists it"""

    def __init__(
        self,
        forecast_source: ForecastSource,
        repository: WeatherRepository,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
    ):
        self.forecast_source = forecast_source
        self.repository = repository
        self.horizon_days = horizon_days

    def refresh(self) -> int:
        """
        Fetch and save the full forecast horizon, overwriting whatever was stored
        for those hours by the previous run.

        Returns:
            Number of readings written
        """
        readings = self.forecast_source.fetch_forecast(self.horizon_days)
        self.repository.save(readings)
        return len(readings)
