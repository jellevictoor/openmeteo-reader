from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from openmeteo_reader import api
from openmeteo_reader.domain.models import WeatherReading


class FakeQueryRepository:
    def __init__(self, latest_reading=None, series_points=None, series_by_variable=None):
        self._latest_reading = latest_reading
        self._series_points = series_points or []
        self._series_by_variable = series_by_variable or {}
        self.series_calls = []

    def latest(self):
        return self._latest_reading

    def series(self, variable, since, until=None):
        self.series_calls.append((variable, since, until))
        if variable in self._series_by_variable:
            return self._series_by_variable[variable]
        return self._series_points


def make_client(repository, forecast_repository=None):
    api.set_repository(repository)
    api.set_forecast_repository(forecast_repository)
    return TestClient(api.app)


def test_health_check_is_always_ok():
    client = make_client(FakeQueryRepository())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_current_returns_503_when_repository_is_not_wired_up():
    api.set_repository(None)
    client = TestClient(api.app)

    response = client.get("/api/current")

    assert response.status_code == 503


def test_current_returns_404_when_nothing_has_been_stored_yet():
    client = make_client(FakeQueryRepository(latest_reading=None))

    response = client.get("/api/current")

    assert response.status_code == 404


def test_current_returns_the_latest_reading():
    reading = WeatherReading(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        location="home",
        values={"temperature_2m": 5.2},
    )
    client = make_client(FakeQueryRepository(latest_reading=reading))

    response = client.get("/api/current")

    assert response.status_code == 200
    assert response.json() == {
        "timestamp": "2024-01-01T00:00:00+00:00",
        "values": {"temperature_2m": 5.2},
    }


def test_series_returns_the_requested_variables_points_since_the_given_number_of_hours():
    points = [
        (datetime(2024, 1, 1, 0, tzinfo=UTC), 5.2),
        (datetime(2024, 1, 1, 1, tzinfo=UTC), 4.8),
    ]
    repository = FakeQueryRepository(series_points=points)
    client = make_client(repository)

    response = client.get("/api/series", params={"variable": "temperature_2m", "hours": 24})

    assert response.status_code == 200
    assert response.json() == [
        {"time": "2024-01-01T00:00:00+00:00", "value": 5.2},
        {"time": "2024-01-01T01:00:00+00:00", "value": 4.8},
    ]

    called_variable, called_since, _called_until = repository.series_calls[0]
    assert called_variable == "temperature_2m"
    expected_since = datetime.now(tz=UTC) - timedelta(hours=24)
    assert abs((called_since - expected_since).total_seconds()) < 5


def test_index_page_renders():
    client = make_client(FakeQueryRepository())

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_history_page_renders():
    client = make_client(FakeQueryRepository())

    response = client.get("/history")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_forecast_series_returns_503_when_forecast_repository_is_not_wired_up():
    client = make_client(FakeQueryRepository(), forecast_repository=None)

    response = client.get("/api/forecast/series", params={"variable": "temperature_2m"})

    assert response.status_code == 503


def test_forecast_series_combines_min_median_max_by_time():
    t1 = datetime(2026, 8, 20, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 20, 1, tzinfo=UTC)
    forecast_repository = FakeQueryRepository(
        series_by_variable={
            "temperature_2m_min": [(t1, 10.0), (t2, 9.0)],
            "temperature_2m_median": [(t1, 12.0), (t2, 11.0)],
            "temperature_2m_max": [(t1, 14.0), (t2, 13.0)],
        }
    )
    client = make_client(FakeQueryRepository(), forecast_repository=forecast_repository)

    response = client.get("/api/forecast/series", params={"variable": "temperature_2m"})

    assert response.status_code == 200
    assert response.json() == [
        {"time": "2026-08-20T00:00:00+00:00", "min": 10.0, "median": 12.0, "max": 14.0},
        {"time": "2026-08-20T01:00:00+00:00", "min": 9.0, "median": 11.0, "max": 13.0},
    ]

    variables_queried = {call[0] for call in forecast_repository.series_calls}
    assert variables_queried == {
        "temperature_2m_min",
        "temperature_2m_median",
        "temperature_2m_max",
    }
