"""
Data models for weather forecasts and atmospheric observations.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, List


@dataclass(frozen=True)
class HourlyWeatherRecord:
    """
    Strongly-typed record of hourly atmospheric observations/forecasts
    required by thermal stress models (WBGT, Heat Index).
    """
    timestamp: str
    temperature_c: float
    relative_humidity: float
    wind_speed_kmh: float
    shortwave_radiation: float
    surface_pressure_hpa: float
    direct_normal_irradiance: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to standard dictionary."""
        return asdict(self)


@dataclass
class HourlyForecast:
    """
    Container for a sequence of hourly weather records at a specific location.
    """
    latitude: float
    longitude: float
    timezone: str
    records: List[HourlyWeatherRecord]
    is_fallback: bool = False
    data_source: str = "Open-Meteo Live API"

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[HourlyWeatherRecord]:
        return iter(self.records)

    def __getitem__(self, index: int) -> HourlyWeatherRecord:
        return self.records[index]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Return all records as a list of dictionaries."""
        return [record.to_dict() for record in self.records]

    def to_dataframe(self):
        """Convert hourly records to a pandas DataFrame if pandas is installed."""
        try:
            import pandas as pd
            return pd.DataFrame(self.to_dict_list())
        except ImportError:
            raise RuntimeError("pandas is required for to_dataframe()")
