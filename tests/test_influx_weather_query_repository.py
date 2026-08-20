from datetime import UTC, datetime

from openmeteo_reader.adapters.influx_weather_query_repository import (
    InfluxWeatherQueryRepository,
)


class FakeRecord:
    def __init__(self, field, value, time):
        self.field = field
        self.value = value
        self.time = time

    def get_field(self):
        return self.field

    def get_value(self):
        return self.value

    def get_time(self):
        return self.time


class FakeTable:
    def __init__(self, records):
        self.records = records


class FakeQueryApi:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def query(self, org, query):
        self.calls.append({"org": org, "query": query})
        return self.tables


def repository(query_api):
    return InfluxWeatherQueryRepository(
        bucket="weather", org="klskmp", location="home", query_api=query_api
    )


def test_latest_combines_the_last_record_of_every_field_into_one_reading():
    time = datetime(2024, 1, 1, tzinfo=UTC)
    tables = [
        FakeTable([FakeRecord("temperature_2m", 5.2, time)]),
        FakeTable([FakeRecord("relative_humidity_2m", 88.0, time)]),
    ]
    query_api = FakeQueryApi(tables)
    repo = repository(query_api)

    reading = repo.latest()

    assert reading.timestamp == time
    assert reading.location == "home"
    assert reading.values == {"temperature_2m": 5.2, "relative_humidity_2m": 88.0}
    assert query_api.calls[0]["org"] == "klskmp"
    assert "weather" in query_api.calls[0]["query"]
    assert "home" in query_api.calls[0]["query"]


def test_latest_returns_none_when_nothing_is_stored():
    repo = repository(FakeQueryApi([]))

    assert repo.latest() is None


def test_series_returns_time_value_pairs_for_the_requested_variable_sorted_by_time():
    t1 = datetime(2024, 1, 1, 0, tzinfo=UTC)
    t2 = datetime(2024, 1, 1, 1, tzinfo=UTC)
    tables = [
        FakeTable(
            [
                FakeRecord("temperature_2m", 5.2, t1),
                FakeRecord("temperature_2m", 4.8, t2),
            ]
        )
    ]
    query_api = FakeQueryApi(tables)
    repo = repository(query_api)

    series = repo.series("temperature_2m", since=t1)

    assert series == [(t1, 5.2), (t2, 4.8)]
    assert "temperature_2m" in query_api.calls[0]["query"]


def test_series_returns_empty_list_when_nothing_matches():
    repo = repository(FakeQueryApi([]))

    assert repo.series("temperature_2m", since=datetime(2024, 1, 1, tzinfo=UTC)) == []


def test_series_includes_an_explicit_stop_when_until_is_given():
    query_api = FakeQueryApi([])
    repo = repository(query_api)
    since = datetime(2026, 8, 20, tzinfo=UTC)
    until = datetime(2026, 8, 28, tzinfo=UTC)

    repo.series("temperature_2m", since=since, until=until)

    query = query_api.calls[0]["query"]
    assert since.isoformat() in query
    assert until.isoformat() in query


def test_series_has_no_explicit_stop_when_until_is_omitted():
    query_api = FakeQueryApi([])
    repo = repository(query_api)

    repo.series("temperature_2m", since=datetime(2024, 1, 1, tzinfo=UTC))

    assert "stop:" not in query_api.calls[0]["query"]
