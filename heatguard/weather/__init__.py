"""
Weather data fetching and modeling module for HeatGuard.
"""

from heatguard.weather.client import (
    OPEN_METEO_URL,
    REQUIRED_HOURLY_FIELDS,
    OpenMeteoClient,
    WeatherAPIError,
    WeatherFetchError,
    fetch_hourly_forecast,
)
from heatguard.weather.models import HourlyForecast, HourlyWeatherRecord

__all__ = [
    "OPEN_METEO_URL",
    "REQUIRED_HOURLY_FIELDS",
    "OpenMeteoClient",
    "WeatherAPIError",
    "WeatherFetchError",
    "fetch_hourly_forecast",
    "HourlyForecast",
    "HourlyWeatherRecord",
]
