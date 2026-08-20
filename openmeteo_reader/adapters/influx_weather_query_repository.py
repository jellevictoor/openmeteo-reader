"""
Adapter - Reads weather data back out of InfluxDB for the website/API
"""
from datetime import datetime

from openmeteo_reader.domain.models import WeatherReading
from openmeteo_reader.ports.weather_query_repository import WeatherQueryRepository

MEASUREMENT = "openmeteo"


class InfluxWeatherQueryRepository(WeatherQueryRepository):
    """Reads weather data for one location back out of InfluxDB via Flux"""

    def __init__(self, bucket: str, org: str, location: str, query_api):
        self.bucket = bucket
        self.org = org
        self.location = location
        self.query_api = query_api

    def latest(self) -> WeatherReading | None:
        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -6h)
          |> filter(fn: (r) => r._measurement == "{MEASUREMENT}" and r.location == "{self.location}")
          |> last()
        '''
        tables = self.query_api.query(org=self.org, query=flux)

        values = {}
        timestamp = None
        for table in tables:
            for record in table.records:
                values[record.get_field()] = record.get_value()
                timestamp = record.get_time()

        if timestamp is None:
            return None
        return WeatherReading(timestamp=timestamp, location=self.location, values=values)

    def series(self, variable: str, since: datetime) -> list[tuple[datetime, float]]:
        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {since.isoformat()})
          |> filter(fn: (r) => r._measurement == "{MEASUREMENT}" and r.location == "{self.location}" and r._field == "{variable}")
          |> sort(columns: ["_time"])
        '''
        tables = self.query_api.query(org=self.org, query=flux)

        return [
            (record.get_time(), record.get_value())
            for table in tables
            for record in table.records
        ]
