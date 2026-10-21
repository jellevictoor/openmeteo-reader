"""
Adapter - Fetches weather data from the Open-Meteo Forecast and Historical APIs
"""
import time
from datetime import UTC, date, datetime

import httpx

from openmeteo_reader.domain.ensemble_response import parse_ensemble_readings
from openmeteo_reader.domain.models import HOME_TIMEZONE, WeatherReading
from openmeteo_reader.domain.open_meteo_response import parse_hourly_readings
from openmeteo_reader.ports.forecast_source import ForecastSource
from openmeteo_reader.ports.weather_source import WeatherSource

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

# DWD's ICON (40 members, ~7.5 days) and ECMWF's IFS (51 members, 15 days), pooled
# into one 91-member ensemble. A single model family can be confidently wrong about
# when a front passes; two independent ones put the median where they agree.
ENSEMBLE_MODELS = ["icon_seamless", "ecmwf_ifs025"]
# The variables people actually act on day-to-day ("how warm", "will it rain", "how
# windy") - not the full curated actuals set, which would be far more members/writes
# for spread bands most people won't look at.
ENSEMBLE_VARIABLES = ["temperature_2m", "precipitation", "wind_speed_10m", "shortwave_radiation"]

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


# Open-Meteo's rate limit is occasionally hit even under normal, non-bulk use (seen
# in production on the very first backfill request) - retry a 429 with backoff
# rather than let one transient response kill an entire multi-year backfill.
RETRY_BACKOFF_SECONDS = [5, 15, 45]

# The home's actual PV array, from Home Assistant's forecast_solar integration
# (.storage/core.config_entries, subentry "39° / 154° / 5200W"). HA stores azimuth
# in compass convention (0=north, 90=east, 180=south); Open-Meteo's global_tilted_
# irradiance uses the solar-industry convention (0=south, -90=east, 90=west), so
# the stored 154 becomes 154-180=-26 here. Without this, global_tilted_irradiance
# is computed for Open-Meteo's default orientation, not this roof.
PANEL_TILT_DEGREES = 39
PANEL_AZIMUTH_DEGREES = -26


class OpenMeteoClient(WeatherSource, ForecastSource):
    """Fetches weather data for one fixed location from Open-Meteo"""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        location: str = "home",
        http_client: httpx.Client | None = None,
        sleep=time.sleep,
        now=lambda: datetime.now(UTC),
    ):
        self._latitude = latitude
        self._longitude = longitude
        self._location = location
        self._http = http_client or httpx.Client(timeout=30.0)
        self._sleep = sleep
        self._now = now

    def _get(self, url: str, params: dict) -> httpx.Response:
        response = self._http.get(url, params=params)
        for delay in RETRY_BACKOFF_SECONDS:
            if response.status_code != 429:
                break
            self._sleep(delay)
            response = self._http.get(url, params=params)
        response.raise_for_status()
        return response

    def fetch_recent(self, past_hours: int) -> list[WeatherReading]:
        response = self._get(
            FORECAST_URL,
            params={
                "latitude": self._latitude,
                "longitude": self._longitude,
                "hourly": ",".join(FORECAST_HOURLY_VARIABLES),
                "past_hours": past_hours,
                "forecast_hours": 0,
                "timezone": "UTC",
                "tilt": PANEL_TILT_DEGREES,
                "azimuth": PANEL_AZIMUTH_DEGREES,
            },
        )
        return parse_hourly_readings(response.json(), location=self._location)

    def fetch_forecast(self, days: int) -> list[WeatherReading]:
        # Timestamps stay UTC; days are cut at local midnight. Local midnight is
        # before UTC midnight, so yesterday is fetched too: today's running rain
        # total then starts at 00:00 local, and everything before it is dropped.
        response = self._get(
            ENSEMBLE_URL,
            params={
                "latitude": self._latitude,
                "longitude": self._longitude,
                "hourly": ",".join(ENSEMBLE_VARIABLES),
                "models": ",".join(ENSEMBLE_MODELS),
                "forecast_days": days,
                "past_days": 1,
                "timezone": "UTC",
            },
        )
        readings = parse_ensemble_readings(
            response.json(),
            location=self._location,
            variables=ENSEMBLE_VARIABLES,
            day_zone=HOME_TIMEZONE,
        )
        local_midnight = self._now().astimezone(HOME_TIMEZONE).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return [r for r in readings if r.timestamp >= local_midnight]

    def fetch_historical(self, start: date, end: date) -> list[WeatherReading]:
        response = self._get(
            HISTORICAL_URL,
            params={
                "latitude": self._latitude,
                "longitude": self._longitude,
                "hourly": ",".join(HISTORICAL_HOURLY_VARIABLES),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "timezone": "UTC",
                "tilt": PANEL_TILT_DEGREES,
                "azimuth": PANEL_AZIMUTH_DEGREES,
            },
        )
        return parse_hourly_readings(response.json(), location=self._location)
