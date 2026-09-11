from datetime import datetime

import requests

from heat_index import calculate_heat_index
from risk import calculate_risk
from wbgt import calculate_wbgt

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "shortwave_radiation",
    "surface_pressure",
    "direct_normal_irradiance",
]


class WeatherFetchError(Exception):
    """Raised when the forecast API can't be reached or returns bad data."""


def fetch_hourly_forecast(latitude, longitude, timezone="Asia/Kolkata", forecast_days=5):
    """Fetch raw hourly forecast data from Open-Meteo."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": HOURLY_FIELDS,
        "forecast_days": forecast_days,
        "timezone": timezone,
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherFetchError(f"Could not fetch forecast: {exc}") from exc

    data = response.json()

    if "hourly" not in data:
        raise WeatherFetchError(f"Unexpected API response: {data}")

    return data["hourly"]


def _hour_has_complete_data(hourly, i):
    """Skip hours where any required field is missing/null."""
    return all(hourly[field][i] is not None for field in HOURLY_FIELDS)


def get_hourly_risk_forecast(
    latitude,
    longitude,
    timezone="Asia/Kolkata",
    hours_ahead=24,
    daylight_only=False,
):
    """
    Fetch the forecast and compute heat index, WBGT, and risk level for
    each hour in the requested window.

    Returns a list of dicts, one per hour, e.g.:
        {
            "timestamp": "2026-09-10T14:00",
            "temp_c": 33.2,
            "humidity": 58,
            "wind_kmh": 11.4,
            "heat_index_c": 41.7,
            "wbgt_c": 30.1,
            "heat_index_risk": RiskLevel.EXTREME_CAUTION,
            "wbgt_risk": RiskLevel.EXTREME_CAUTION,
            "risk_verdict": RiskLevel.EXTREME_CAUTION,
        }

    Hours with missing data from the API are skipped rather than crashing
    the whole run.
    """
    hourly = fetch_hourly_forecast(latitude, longitude, timezone=timezone)

    n_available = len(hourly["time"])
    n_hours = min(hours_ahead, n_available)

    results = []

    for i in range(n_hours):
        if not _hour_has_complete_data(hourly, i):
            continue

        timestamp = hourly["time"][i]

        if daylight_only:
            hour = datetime.fromisoformat(timestamp).hour
            if hour < 6 or hour > 18:
                continue

        temp = hourly["temperature_2m"][i]
        humidity = hourly["relative_humidity_2m"][i]
        wind = hourly["wind_speed_10m"][i]
        radiation = hourly["shortwave_radiation"][i]
        pressure = hourly["surface_pressure"][i]
        direct_radiation = hourly["direct_normal_irradiance"][i]

        heat_index = calculate_heat_index(temp, humidity)

        wbgt = calculate_wbgt(
            temperature_c=temp,
            humidity=humidity,
            wind_kmh=wind,
            radiation=radiation,
            pressure_hpa=pressure,
            direct_radiation=direct_radiation,
            timestamp=timestamp,
        )

        risk = calculate_risk(heat_index, wbgt)

        results.append({
            "timestamp": timestamp,
            "temp_c": temp,
            "humidity": humidity,
            "wind_kmh": wind,
            "heat_index_c": heat_index,
            "wbgt_c": wbgt,
            "heat_index_risk": risk["heat_index_level"],
            "wbgt_risk": risk["wbgt_level"],
            "risk_verdict": risk["verdict"],
        })

    return results


def _print_forecast(results):
    for r in results:
        print(
            r["timestamp"],
            "| Temp:", r["temp_c"],
            "| Humidity:", r["humidity"],
            "| Wind:", r["wind_kmh"],
            "| Heat Index:", r["heat_index_c"], f"({r['heat_index_risk']})",
            "| WBGT:", r["wbgt_c"], f"({r['wbgt_risk']})",
            "| Verdict:", r["risk_verdict"],
        )


if __name__ == "__main__":
    LATITUDE = 12.9716
    LONGITUDE = 77.5946

    try:
        forecast = get_hourly_risk_forecast(LATITUDE, LONGITUDE, hours_ahead=10)
    except WeatherFetchError as exc:
        print(f"Error: {exc}")
    else:
        _print_forecast(forecast)