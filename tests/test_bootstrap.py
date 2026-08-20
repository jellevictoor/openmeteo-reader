from openmeteo_reader.adapters.influx_weather_repository import InfluxWeatherRepository
from openmeteo_reader.adapters.open_meteo_client import OpenMeteoClient
from openmeteo_reader.application.weather_import_service import WeatherImportService
from openmeteo_reader.bootstrap import (
    ApplicationContainer,
    InfluxConfig,
    LocationConfig,
    bootstrap_application,
)

INFLUX_CONFIG = InfluxConfig(
    url="http://localhost:8086", token="test-token", org="klskmp", bucket="weather"
)
LOCATION_CONFIG = LocationConfig(latitude=50.995, longitude=3.213)


def test_bootstrap_returns_an_application_container():
    container = bootstrap_application(INFLUX_CONFIG, LOCATION_CONFIG)

    assert isinstance(container, ApplicationContainer)


def test_bootstrap_wires_an_import_service_with_the_configured_adapters():
    container = bootstrap_application(INFLUX_CONFIG, LOCATION_CONFIG)

    assert isinstance(container.import_service, WeatherImportService)
    assert isinstance(container.import_service.weather_source, OpenMeteoClient)
    assert isinstance(container.import_service.repository, InfluxWeatherRepository)


def test_bootstrap_repository_targets_the_configured_bucket_and_org():
    container = bootstrap_application(INFLUX_CONFIG, LOCATION_CONFIG)

    repository = container.import_service.repository
    assert repository.bucket == "weather"
    assert repository.org == "klskmp"


def test_close_closes_the_influx_client(mocker):
    container = bootstrap_application(INFLUX_CONFIG, LOCATION_CONFIG)
    close = mocker.patch.object(container.influx_client, "close")

    container.close()

    close.assert_called_once()
