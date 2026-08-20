"""
CLI entrypoint - imports weather data from Open-Meteo into InfluxDB
"""
import logging
from datetime import UTC, date, datetime

import typer

from openmeteo_reader.bootstrap import (
    InfluxConfig,
    LocationConfig,
    bootstrap_application,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

app = typer.Typer()

# The single location this service ever imports for - see CONTEXT.md "Weather domain".
HOME_LATITUDE = 50.99528169318774
HOME_LONGITUDE = 3.2131169748116113


def _bootstrap(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    influx_bucket: str,
    latitude: float,
    longitude: float,
):
    influx_config = InfluxConfig(
        url=influx_url, token=influx_token, org=influx_org, bucket=influx_bucket
    )
    location_config = LocationConfig(latitude=latitude, longitude=longitude)
    return bootstrap_application(influx_config, location_config)


@app.command()
def main(
    influx_url: str = typer.Option(..., envvar="INFLUX_URL", help="InfluxDB URL"),
    influx_token: str = typer.Option(
        ..., envvar="INFLUX_TOKEN", help="InfluxDB authentication token"
    ),
    influx_org: str = typer.Option(..., envvar="INFLUX_ORG", help="InfluxDB organization"),
    influx_bucket: str = typer.Option(
        "weather", envvar="INFLUX_BUCKET", help="InfluxDB bucket name"
    ),
    latitude: float = typer.Option(HOME_LATITUDE, envvar="HOME_LATITUDE"),
    longitude: float = typer.Option(HOME_LONGITUDE, envvar="HOME_LONGITUDE"),
):
    """Fetch and store the rolling recent weather window. Run this hourly."""
    container = _bootstrap(
        influx_url, influx_token, influx_org, influx_bucket, latitude, longitude
    )
    try:
        count = container.import_service.import_recent()
        logger.info("Wrote %d readings", count)
    finally:
        container.close()


@app.command()
def backfill(
    start: str = typer.Option(..., help="First day to backfill, as YYYY-MM-DD"),
    end: str = typer.Option(
        None, help="Last day to backfill, as YYYY-MM-DD. Defaults to today."
    ),
    chunk_days: int = typer.Option(30, help="Days per Historical Weather API request"),
    influx_url: str = typer.Option(..., envvar="INFLUX_URL", help="InfluxDB URL"),
    influx_token: str = typer.Option(
        ..., envvar="INFLUX_TOKEN", help="InfluxDB authentication token"
    ),
    influx_org: str = typer.Option(..., envvar="INFLUX_ORG", help="InfluxDB organization"),
    influx_bucket: str = typer.Option(
        "weather", envvar="INFLUX_BUCKET", help="InfluxDB bucket name"
    ),
    latitude: float = typer.Option(HOME_LATITUDE, envvar="HOME_LATITUDE"),
    longitude: float = typer.Option(HOME_LONGITUDE, envvar="HOME_LONGITUDE"),
):
    """One-off historical backfill via the Historical Weather API."""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end) if end else datetime.now(tz=UTC).date()

    container = _bootstrap(
        influx_url, influx_token, influx_org, influx_bucket, latitude, longitude
    )
    try:
        logger.info("Backfilling %s to %s in %d-day chunks", start_date, end_date, chunk_days)
        total = container.import_service.backfill(start_date, end_date, chunk_days)
        logger.info("Wrote %d readings", total)
    finally:
        container.close()


@app.command()
def forecast(
    horizon_days: int = typer.Option(
        8, envvar="FORECAST_HORIZON_DAYS", help="Days ahead to fetch, including today"
    ),
    influx_url: str = typer.Option(..., envvar="INFLUX_URL", help="InfluxDB URL"),
    influx_token: str = typer.Option(
        ..., envvar="INFLUX_TOKEN", help="InfluxDB authentication token"
    ),
    influx_org: str = typer.Option(..., envvar="INFLUX_ORG", help="InfluxDB organization"),
    forecast_bucket: str = typer.Option(
        "forecast", envvar="INFLUX_FORECAST_BUCKET", help="InfluxDB bucket name"
    ),
    latitude: float = typer.Option(HOME_LATITUDE, envvar="HOME_LATITUDE"),
    longitude: float = typer.Option(HOME_LONGITUDE, envvar="HOME_LONGITUDE"),
):
    """Refresh the ensemble forecast (temperature + precipitation spread). Run hourly."""
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS

    from openmeteo_reader.adapters.influx_weather_repository import (
        InfluxWeatherRepository,
    )
    from openmeteo_reader.adapters.open_meteo_client import OpenMeteoClient
    from openmeteo_reader.application.forecast_import_service import (
        ForecastImportService,
    )

    influx_client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    try:
        forecast_source = OpenMeteoClient(latitude=latitude, longitude=longitude)
        repository = InfluxWeatherRepository(
            bucket=forecast_bucket,
            org=influx_org,
            write_api=influx_client.write_api(write_options=SYNCHRONOUS),
        )
        service = ForecastImportService(forecast_source, repository, horizon_days)
        count = service.refresh()
        logger.info("Wrote %d forecast readings", count)
    finally:
        influx_client.close()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", envvar="HOST"),
    port: int = typer.Option(8000, envvar="PORT"),
    influx_url: str = typer.Option(..., envvar="INFLUX_URL", help="InfluxDB URL"),
    influx_token: str = typer.Option(
        ..., envvar="INFLUX_TOKEN", help="InfluxDB authentication token"
    ),
    influx_org: str = typer.Option(..., envvar="INFLUX_ORG", help="InfluxDB organization"),
    influx_bucket: str = typer.Option(
        "weather", envvar="INFLUX_BUCKET", help="InfluxDB bucket name"
    ),
    forecast_bucket: str = typer.Option(
        "forecast", envvar="INFLUX_FORECAST_BUCKET", help="InfluxDB bucket name"
    ),
):
    """Serve the website and JSON API, reading whatever the importer has written."""
    import uvicorn
    from influxdb_client import InfluxDBClient

    from openmeteo_reader import api
    from openmeteo_reader.adapters.influx_weather_query_repository import (
        InfluxWeatherQueryRepository,
    )

    influx_client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    query_api = influx_client.query_api()
    repository = InfluxWeatherQueryRepository(
        bucket=influx_bucket, org=influx_org, location="home", query_api=query_api
    )
    forecast_repository = InfluxWeatherQueryRepository(
        bucket=forecast_bucket, org=influx_org, location="home", query_api=query_api
    )
    api.set_repository(repository)
    api.set_forecast_repository(forecast_repository)

    try:
        uvicorn.run(api.app, host=host, port=port)
    finally:
        influx_client.close()


if __name__ == "__main__":
    app()
