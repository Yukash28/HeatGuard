"""
Open-Meteo Historical Archive API Provider (ECMWF ERA5 / ERA5-Land Reanalysis).
Pulls historical daily meteorological records across Indian coordinates.
"""

import logging
import time
from typing import Optional
import requests
import pandas as pd

from heatguard.api.base import BaseWeatherProvider, LocationTarget

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoHistoricalProvider(BaseWeatherProvider):
    """Fetches multi-year historical observations via Open-Meteo ERA5 Reanalysis Archive."""

    def __init__(self, timeout: float = 30.0, session: Optional[requests.Session] = None):
        self.timeout = timeout
        if session is not None:
            self.session = session
        else:
            self.session = requests.Session()
            from urllib3.util import Retry
            from requests.adapters import HTTPAdapter
            retries = Retry(total=5, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retries)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

    def fetch_historical_daily(
        self,
        target: LocationTarget,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Query Open-Meteo Archive API and return normalized DataFrame of daily observations.
        """
        params = {
            "latitude": round(target.latitude, 4),
            "longitude": round(target.longitude, 4),
            "start_date": start_date,
            "end_date": end_date,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "temperature_2m_mean",
                "relative_humidity_2m_mean",
                "dew_point_2m_mean",
                "precipitation_sum",
                "wind_speed_10m_max",
                "surface_pressure_mean",
                "shortwave_radiation_sum",
                "cloud_cover_mean",
                "soil_moisture_0_to_7cm_mean",
            ],
            "timezone": target.timezone,
        }

        logger.info(
            "Fetching historical data for %s (%s to %s) from Open-Meteo Archive...",
            target.name, start_date, end_date
        )

        resp = self.session.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        if "daily" not in data or "time" not in data["daily"]:
            raise ValueError(f"Open-Meteo Archive returned malformed payload for {target.name}: {data}")

        daily = data["daily"]
        df = pd.DataFrame({
            "date": pd.to_datetime(daily["time"]).strftime("%Y-%m-%d"),
            "location": target.name,
            "latitude": target.latitude,
            "longitude": target.longitude,
            "terrain_type": target.terrain_type,
            "tmax": daily.get("temperature_2m_max"),
            "tmin": daily.get("temperature_2m_min"),
            "tmean": daily.get("temperature_2m_mean"),
            "humidity": daily.get("relative_humidity_2m_mean"),
            "dew_point": daily.get("dew_point_2m_mean"),
            "rainfall": daily.get("precipitation_sum"),
            "wind_speed": daily.get("wind_speed_10m_max"),
            "pressure": daily.get("surface_pressure_mean"),
            "solar_radiation": daily.get("shortwave_radiation_sum"),
            "cloud_cover": daily.get("cloud_cover_mean"),
            "soil_moisture": daily.get("soil_moisture_0_to_7cm_mean"),
        })

        return df
