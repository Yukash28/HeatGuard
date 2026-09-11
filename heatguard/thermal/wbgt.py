"""
Wet Bulb Globe Temperature (WBGT) calculation engine.
Implements the Liljegren et al. (2008) outdoor physical model via thermofeel.
"""

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

# Ensure project root is importable when executed directly
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
import thermofeel
from earthkit.meteo import solar

try:
    from heatguard.thermal.validation import (
        celsius_to_kelvin,
        kelvin_to_celsius,
        kmh_to_ms,
        validate_humidity,
        validate_pressure,
        validate_radiation,
        validate_temperature,
        validate_wind_speed,
    )
except ImportError:
    from validation import (
        celsius_to_kelvin,
        kelvin_to_celsius,
        kmh_to_ms,
        validate_humidity,
        validate_pressure,
        validate_radiation,
        validate_temperature,
        validate_wind_speed,
    )

DEFAULT_LATITUDE = 12.9716
DEFAULT_LONGITUDE = 77.5946
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Retain module constants for backward compatibility
LATITUDE = DEFAULT_LATITUDE
LONGITUDE = DEFAULT_LONGITUDE
TIMEZONE = DEFAULT_TIMEZONE


def calculate_wbgt(
    temperature_c: float,
    humidity: float,
    wind_kmh: float,
    radiation: float,
    pressure_hpa: float,
    direct_radiation: float,
    timestamp: str,
    latitude: float = DEFAULT_LATITUDE,
    longitude: float = DEFAULT_LONGITUDE,
    timezone: str = DEFAULT_TIMEZONE,
) -> float:
    """
    Calculate outdoor WBGT using the Liljegren et al. (2008) model.

    Inputs:
        temperature_c    : air temperature in °C
        humidity         : relative humidity in % (0-100)
        wind_kmh         : wind speed at 10 m in km/h
        radiation        : total downward shortwave radiation in W/m²
        pressure_hpa     : surface pressure in hPa
        direct_radiation : direct normal irradiance (DNI) in W/m²
        timestamp        : local ISO timestamp (e.g. '2026-06-15T13:00')
        latitude         : site latitude in decimal degrees
        longitude        : site longitude in decimal degrees
        timezone         : local timezone name (default 'Asia/Kolkata')

    Returns:
        WBGT in °C (rounded to 2 decimal places)
    """
    # Validate input boundaries
    temp_c = validate_temperature(temperature_c)
    rh = validate_humidity(humidity)
    wind = validate_wind_speed(wind_kmh)
    rad = validate_radiation(radiation, "Total solar radiation")
    p_hpa = validate_pressure(pressure_hpa)
    dni = validate_radiation(direct_radiation, "Direct radiation")

    # Unit conversions
    temperature_k = celsius_to_kelvin(temp_c)
    wind_ms = kmh_to_ms(wind)

    # Convert timestamp to timezone-aware datetime
    date_time = datetime.fromisoformat(timestamp)
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=ZoneInfo(timezone))

    # Calculate cosine of solar zenith angle
    cossza = solar.cos_solar_zenith_angle(
        date_time,
        np.array([latitude]),
        np.array([longitude]),
    )
    cossza = float(np.asarray(cossza).reshape(-1)[0])

    # Calculate direct horizontal fraction
    if rad <= 0 or dni <= 0 or cossza <= 0:
        fdir = 0.0
    else:
        direct_horizontal = dni * cossza
        fdir = direct_horizontal / rad
        # Operational guard: clamp fdir to [0.0, 0.9] as expected by Liljegren model
        fdir = max(0.0, min(0.9, fdir))

    # Calculate WBGT using the Liljegren energy balance formulation
    wbgt_k = thermofeel.calculate_wbgt_liljegren(
        t2_k=temperature_k,
        rh=rh,
        pressure=p_hpa,
        va=wind_ms,
        ssrd=rad,
        fdir=fdir,
        cossza=cossza,
    )

    if np.isnan(wbgt_k):
        raise ValueError(
            f"Liljegren solver did not converge for inputs: temp={temp_c}, rh={rh}, "
            f"wind={wind}, rad={rad}, pressure={p_hpa}"
        )

    wbgt_c = kelvin_to_celsius(float(wbgt_k))
    return round(wbgt_c, 2)