from datetime import date

import httpx
import pytest
import respx

from openmeteo_reader.adapters.open_meteo_client import (
    FORECAST_URL,
    HISTORICAL_URL,
    OpenMeteoClient,
)


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(sleeps):
    return OpenMeteoClient(
        latitude=50.995, longitude=3.213, location="home", sleep=sleeps.append
    )


@respx.mock
def test_fetch_recent_requests_the_forecast_api_with_no_future_hours(client):
    route = respx.get(FORECAST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2024-01-01T00:00"],
                    "temperature_2m": [5.2],
                }
            },
        )
    )

    readings = client.fetch_recent(past_hours=6)

    request = route.calls.last.request
    params = httpx.QueryParams(request.url.query)
    assert params["latitude"] == "50.995"
    assert params["longitude"] == "3.213"
    assert params["past_hours"] == "6"
    assert params["forecast_hours"] == "0"
    assert params["timezone"] == "UTC"
    assert params["tilt"] == "39"
    assert params["azimuth"] == "-26"
    assert "temperature_2m" in params["hourly"]

    assert [r.values for r in readings] == [{"temperature_2m": 5.2}]
    assert readings[0].location == "home"


@respx.mock
def test_fetch_historical_requests_the_archive_api_for_the_given_date_range(client):
    route = respx.get(HISTORICAL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2019-01-01T00:00"],
                    "temperature_2m": [3.1],
                }
            },
        )
    )

    readings = client.fetch_historical(start=date(2019, 1, 1), end=date(2019, 1, 31))

    request = route.calls.last.request
    params = httpx.QueryParams(request.url.query)
    assert params["start_date"] == "2019-01-01"
    assert params["end_date"] == "2019-01-31"
    assert params["timezone"] == "UTC"
    assert params["tilt"] == "39"
    assert params["azimuth"] == "-26"
    assert "temperature_2m" in params["hourly"]

    assert [r.values for r in readings] == [{"temperature_2m": 3.1}]


@respx.mock
def test_fetch_recent_raises_on_http_error(client):
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_recent(past_hours=6)


@respx.mock
def test_fetch_recent_retries_after_a_transient_429_then_succeeds(client, sleeps):
    route = respx.get(FORECAST_URL)
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(
            200,
            json={"hourly": {"time": ["2024-01-01T00:00"], "temperature_2m": [5.2]}},
        ),
    ]

    readings = client.fetch_recent(past_hours=6)

    assert [r.values for r in readings] == [{"temperature_2m": 5.2}]
    assert route.call_count == 2
    assert sleeps == [5]


@respx.mock
def test_fetch_recent_raises_after_exhausting_retries_on_429(client, sleeps):
    route = respx.get(FORECAST_URL)
    route.side_effect = [httpx.Response(429)] * 4

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_recent(past_hours=6)

    assert route.call_count == 4
    assert sleeps == [5, 15, 45]


@respx.mock
def test_fetch_recent_does_not_retry_on_a_non_429_error(client, sleeps):
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_recent(past_hours=6)

    assert route.call_count == 1
    assert sleeps == []
