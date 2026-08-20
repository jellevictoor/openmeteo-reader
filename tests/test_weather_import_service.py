from datetime import UTC, date, datetime

from openmeteo_reader.application.weather_import_service import WeatherImportService
from openmeteo_reader.domain.models import WeatherReading


class FakeWeatherSource:
    def __init__(self):
        self.fetch_recent_calls = []
        self.fetch_historical_calls = []
        self.readings = [
            WeatherReading(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                location="home",
                values={"temperature_2m": 5.0},
            )
        ]

    def fetch_recent(self, past_hours):
        self.fetch_recent_calls.append(past_hours)
        return self.readings

    def fetch_historical(self, start, end):
        self.fetch_historical_calls.append((start, end))
        return self.readings


class FakeWeatherRepository:
    def __init__(self):
        self.saved_batches = []

    def save(self, readings):
        self.saved_batches.append(readings)


def test_import_recent_fetches_the_correction_window_and_saves_it():
    source = FakeWeatherSource()
    repository = FakeWeatherRepository()
    service = WeatherImportService(source, repository, correction_window_hours=6)

    count = service.import_recent()

    assert source.fetch_recent_calls == [6]
    assert repository.saved_batches == [source.readings]
    assert count == 1


def test_backfill_splits_the_date_range_into_chunks():
    source = FakeWeatherSource()
    repository = FakeWeatherRepository()
    service = WeatherImportService(source, repository)

    total = service.backfill(date(2019, 1, 1), date(2019, 2, 15), chunk_days=30)

    assert source.fetch_historical_calls == [
        (date(2019, 1, 1), date(2019, 1, 30)),
        (date(2019, 1, 31), date(2019, 2, 15)),
    ]
    assert len(repository.saved_batches) == 2
    assert total == 2


def test_backfill_handles_a_range_smaller_than_one_chunk():
    source = FakeWeatherSource()
    repository = FakeWeatherRepository()
    service = WeatherImportService(source, repository)

    total = service.backfill(date(2019, 1, 1), date(2019, 1, 5), chunk_days=30)

    assert source.fetch_historical_calls == [(date(2019, 1, 1), date(2019, 1, 5))]
    assert total == 1
