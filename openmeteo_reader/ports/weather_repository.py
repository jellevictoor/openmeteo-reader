"""
Port - Interface for persisting weather readings
"""
from abc import ABC, abstractmethod

from openmeteo_reader.domain.models import WeatherReading


class WeatherRepository(ABC):
    """Interface for persisting a batch of weather readings"""

    @abstractmethod
    def save(self, readings: list[WeatherReading]) -> None:
        """
        Persist a batch of readings. A reading at a timestamp/location that was
        already stored is overwritten - this is how corrections to recent hours
        are applied.
        """
