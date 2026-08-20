"""
Adapter - Fetches weather data from the Open-Meteo Forecast and Historical APIs
"""
from datetime import date

import httpx

from openmeteo_reader.domain.models import WeatherReading
from openmeteo_reader.domain.open_meteo_response import parse_hourly_readings
from openmeteo_reader.ports.weather_source import WeatherSource

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

# The Forecast API's rolling window: this is what revises for up to ~3h after the
# fact as observations land, so it's what feeds the hourly correction job.
FORECAST_HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "wind_speed_10m",
    "wind_speed_80m",
    "wind_speed_120m",
    "wind_speed_180m",
    "wind_direction_10m",
    "wind_direction_80m",
    "wind_direction_120m",
    "wind_direction_180m",
    "wind_gusts_10m",
    "shortwave_radiation",
    "direct_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "global_tilted_irradiance",
    "precipitation",
    "precipitation_probability",
    "rain",
    "showers",
    "snowfall",
    "snow_depth",
    "weather_code",
    "visibility",
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
    "soil_moisture_3_to_9cm",
    "soil_moisture_9_to_27cm",
    "soil_moisture_27_to_81cm",
    "vapour_pressure_deficit",
    "cape",
    "evapotranspiration",
    "et0_fao_evapotranspiration",
    "freezing_level_height",
    "is_day",
]

# The Historical Weather API's (ERA5 reanalysis) variable set: overlapping but not
# identical to the Forecast API's - different soil depth bands, no forecast-only
# fields like precipitation_probability or cape. Used only for the one-off backfill.
HISTORICAL_HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "pressure_msl",
    "surface_pressure",
    "precipitation",
    "rain",
    "snowfall",
    "snow_depth",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "shortwave_radiation",
    "direct_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "global_tilted_irradiance",
    "sunshine_duration",
    "wind_speed_10m",
    "wind_speed_100m",
    "wind_direction_10m",
    "wind_direction_100m",
    "wind_gusts_10m",
    "et0_fao_evapotranspiration",
    "soil_temperature_0_to_7cm",
    "soil_temperature_7_to_28cm",
    "soil_temperature_28_to_100cm",
    "soil_temperature_100_to_255cm",
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
    "soil_moisture_100_to_255cm",
    "weather_code",
    "vapour_pressure_deficit",
]


class OpenMeteoClient(WeatherSource):
    """Fetches weather data for one fixed location from Open-Meteo"""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        location: str = "home",
        http_client: httpx.Client | None = None,
    ):
        self._latitude = latitude
        self._longitude = longitude
        self._location = location
        self._http = http_client or httpx.Client(timeout=30.0)

    def fetch_recent(self, past_hours: int) -> list[WeatherReading]:
        response = self._http.get(
            FORECAST_URL,
            params={
                "latitude": self._latitude,
                "longitude": self._longitude,
                "hourly": ",".join(FORECAST_HOURLY_VARIABLES),
                "past_hours": past_hours,
                "forecast_hours": 0,
                "timezone": "UTC",
            },
        )
        response.raise_for_status()
        return parse_hourly_readings(response.json(), location=self._location)

    def fetch_historical(self, start: date, end: date) -> list[WeatherReading]:
        response = self._http.get(
            HISTORICAL_URL,
            params={
                "latitude": self._latitude,
                "longitude": self._longitude,
                "hourly": ",".join(HISTORICAL_HOURLY_VARIABLES),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "timezone": "UTC",
            },
        )
        response.raise_for_status()
        return parse_hourly_readings(response.json(), location=self._location)
