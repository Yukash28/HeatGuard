from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import thermofeel
from earthkit.meteo import solar


LATITUDE = 12.9716
LONGITUDE = 77.5946
TIMEZONE = "Asia/Kolkata"


def calculate_wbgt(
    temperature_c,
    humidity,
    wind_kmh,
    radiation,
    pressure_hpa,
    direct_radiation,
    timestamp
):
    """
    Calculate outdoor WBGT using the Liljegren et al. (2008) model.

    Inputs:
        temperature_c    : air temperature in °C
        humidity         : relative humidity in %
        wind_kmh         : wind speed at 10 m in km/h
        radiation        : total shortwave radiation in W/m²
        pressure_hpa     : surface pressure in hPa
        direct_radiation : direct normal irradiance in W/m²
        timestamp        : local ISO timestamp

    Returns:
        WBGT in °C
    """

    # Convert temperature from Celsius to Kelvin
    temperature_k = temperature_c + 273.15

    # Convert wind from km/h to m/s
    wind_ms = wind_kmh / 3.6

    # Convert timestamp to timezone-aware datetime
    date_time = datetime.fromisoformat(timestamp)

    if date_time.tzinfo is None:
        date_time = date_time.replace(
            tzinfo=ZoneInfo(TIMEZONE)
        )

    # Calculate cosine of solar zenith angle
    cossza = solar.cos_solar_zenith_angle(
        date_time,
        np.array([LATITUDE]),
        np.array([LONGITUDE])
    )

    cossza = float(np.asarray(cossza).reshape(-1)[0])

    # Calculate direct horizontal radiation
    if radiation <= 0 or direct_radiation <= 0 or cossza <= 0:
        fdir = 0.0
    else:
        direct_horizontal = direct_radiation * cossza

        fdir = direct_horizontal / radiation

        # Keep fdir within the range expected by the model
        fdir = max(0.0, min(0.9, fdir))

    # Calculate WBGT using the Liljegren model
    wbgt_k = thermofeel.calculate_wbgt_liljegren(
        t2_k=temperature_k,
        rh=humidity,
        pressure=pressure_hpa,
        va=wind_ms,
        ssrd=radiation,
        fdir=fdir,
        cossza=cossza
    )

    # Convert Kelvin back to Celsius
    wbgt_c = float(wbgt_k - 273.15)

    return round(wbgt_c, 2)