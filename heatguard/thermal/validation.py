"""
Meteorological validation, unit conversions, and thermal result schemas.
"""

from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any, Dict

try:
    from heatguard.thermal.risk import RiskLevel
except ImportError:
    from risk import RiskLevel


class ThermalValidationError(ValueError):
    """Raised when meteorological inputs violate physical or mathematical limits."""


# --- Meteorological Input Validation ----------------------------------------

def validate_temperature(temp_c: float) -> float:
    """Validate air temperature in Celsius."""
    if not isinstance(temp_c, Real):
        raise TypeError(f"Temperature must be numeric, got {type(temp_c).__name__}")
    if not -50.0 <= temp_c <= 60.0:
        raise ThermalValidationError(f"Temperature must be between -50°C and 60°C, got {temp_c}")
    return float(temp_c)


def validate_humidity(humidity: float) -> float:
    """Validate relative humidity in %."""
    if not isinstance(humidity, Real):
        raise TypeError(f"Humidity must be numeric, got {type(humidity).__name__}")
    if not 0.0 <= humidity <= 100.0:
        raise ThermalValidationError(f"Relative humidity must be between 0% and 100%, got {humidity}")
    return float(humidity)


def validate_wind_speed(wind_kmh: float) -> float:
    """Validate wind speed in km/h."""
    if not isinstance(wind_kmh, Real):
        raise TypeError(f"Wind speed must be numeric, got {type(wind_kmh).__name__}")
    if wind_kmh < 0.0 or wind_kmh > 250.0:
        raise ThermalValidationError(f"Wind speed must be between 0 and 250 km/h, got {wind_kmh}")
    return float(wind_kmh)


def validate_radiation(radiation: float, param_name: str = "Radiation") -> float:
    """Validate shortwave/solar radiation in W/m²."""
    if not isinstance(radiation, Real):
        raise TypeError(f"{param_name} must be numeric, got {type(radiation).__name__}")
    if radiation < 0.0 or radiation > 2000.0:
        raise ThermalValidationError(f"{param_name} must be between 0 and 2000 W/m², got {radiation}")
    return float(radiation)


def validate_pressure(pressure_hpa: float) -> float:
    """Validate barometric surface pressure in hPa."""
    if not isinstance(pressure_hpa, Real):
        raise TypeError(f"Pressure must be numeric, got {type(pressure_hpa).__name__}")
    if not 500.0 <= pressure_hpa <= 1100.0:
        raise ThermalValidationError(f"Pressure must be between 500 and 1100 hPa, got {pressure_hpa}")
    return float(pressure_hpa)


# --- Unit Conversions --------------------------------------------------------

def celsius_to_kelvin(celsius: float) -> float:
    """Convert Celsius to Kelvin."""
    return celsius + 273.15


def kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to Celsius."""
    return kelvin - 273.15


def kmh_to_ms(kmh: float) -> float:
    """Convert km/h to m/s."""
    return kmh / 3.6


def ms_to_kmh(ms: float) -> float:
    """Convert m/s to km/h."""
    return ms * 3.6


# --- Output Data Schema -----------------------------------------------------

@dataclass(frozen=True)
class HourlyThermalResult:
    """
    Structured outcome of thermal-stress and risk calculations for a single hour.
    """
    timestamp: str
    temp_c: float
    humidity: float
    wind_kmh: float
    heat_index_c: float
    wbgt_c: float
    heat_index_risk: RiskLevel
    wbgt_risk: RiskLevel
    risk_verdict: RiskLevel
    data_source: str = "Open-Meteo Live API"
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert result into standard dictionary format."""
        return {
            "timestamp": self.timestamp,
            "temp_c": self.temp_c,
            "humidity": self.humidity,
            "wind_kmh": self.wind_kmh,
            "heat_index_c": self.heat_index_c,
            "wbgt_c": self.wbgt_c,
            "heat_index_risk": self.heat_index_risk,
            "wbgt_risk": self.wbgt_risk,
            "risk_verdict": self.risk_verdict,
            "data_source": self.data_source,
            "is_fallback": self.is_fallback,
        }
