from datetime import UTC, datetime

from openmeteo_reader.application.forecast_import_service import ForecastImportService
from openmeteo_reader.domain.models import WeatherReading


class FakeForecastSource:
    def __init__(self):
        self.fetch_forecast_calls = []
        self.readings = [
            WeatherReading(
                timestamp=datetime(2026, 8, 20, tzinfo=UTC),
                location="home",
                values={"temperature_2m_median": 18.0},
            )
        ]

    def fetch_forecast(self, days):
        self.fetch_forecast_calls.append(days)
        return self.readings


class FakeWeatherRepository:
    def __init__(self):
        self.saved_batches = []

    def save(self, readings):
        self.saved_batches.append(readings)


def test_refresh_fetches_the_configured_horizon_and_saves_it():
    source = FakeForecastSource()
    repository = FakeWeatherRepository()
    service = ForecastImportService(source, repository, horizon_days=8)

    count = service.refresh()

    assert source.fetch_forecast_calls == [8]
    assert repository.saved_batches == [source.readings]
    assert count == 1
