"""
Bootstrap module - Initializes and wires up all dependencies
"""
from dataclasses import dataclass

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from openmeteo_reader.adapters.influx_weather_repository import InfluxWeatherRepository
from openmeteo_reader.adapters.open_meteo_client import OpenMeteoClient
from openmeteo_reader.application.weather_import_service import WeatherImportService


@dataclass
class InfluxConfig:
    """InfluxDB connection configuration"""
    url: str
    token: str
    org: str
    bucket: str


@dataclass
class LocationConfig:
    """The home location weather is fetched for"""
    latitude: float
    longitude: float
    name: str = "home"


@dataclass
class ApplicationContainer:
    """Container holding all initialized application dependencies"""
    influx_client: InfluxDBClient
    import_service: WeatherImportService

    def close(self) -> None:
        """Release the InfluxDB client's connection"""
        self.influx_client.close()


def bootstrap_application(
    influx_config: InfluxConfig, location_config: LocationConfig
) -> ApplicationContainer:
    """
    Bootstrap the application by initializing and wiring up all dependencies.

    This is the composition root where we create concrete implementations and wire
    them together following dependency injection principles.
    """
    influx_client = InfluxDBClient(
        url=influx_config.url, token=influx_config.token, org=influx_config.org
    )
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    weather_source = OpenMeteoClient(
        latitude=location_config.latitude,
        longitude=location_config.longitude,
        location=location_config.name,
    )
    repository = InfluxWeatherRepository(
        bucket=influx_config.bucket, org=influx_config.org, write_api=write_api
    )
    import_service = WeatherImportService(weather_source, repository)

    return ApplicationContainer(influx_client=influx_client, import_service=import_service)
