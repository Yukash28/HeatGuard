"""
Abstract base class and provider interface for meteorological data ingestion.
Decouples data sources from downstream ML feature engineering.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd


@dataclass
class LocationTarget:
    """Geographic target for weather data collection."""
    name: str
    latitude: float
    longitude: float
    terrain_type: str = "plains"  # plains, coastal, hills
    timezone: str = "Asia/Kolkata"
    elevation_m: Optional[float] = None


class BaseWeatherProvider(ABC):
    """Abstract interface for weather data providers (Historical and Forecast)."""

    @abstractmethod
    def fetch_historical_daily(
        self,
        target: LocationTarget,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch daily meteorological variables for a location and date range.
        Must return DataFrame with normalized schema:
        ['date', 'location', 'latitude', 'longitude', 'tmax', 'tmin', 'tmean',
         'humidity', 'dew_point', 'rainfall', 'wind_speed', 'pressure',
         'solar_radiation', 'cloud_cover', 'soil_moisture']
        """
        pass
