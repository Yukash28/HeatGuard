"""
Thermal stress pipeline integrating weather retrieval, WBGT, and heat risk models.
"""

from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure project root is importable when executed directly
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from heatguard.thermal.heat_index import calculate_heat_index
    from heatguard.thermal.risk import calculate_risk
    from heatguard.thermal.validation import HourlyThermalResult
    from heatguard.thermal.wbgt import calculate_wbgt
    from heatguard.weather.client import (
        OPEN_METEO_URL,
        REQUIRED_HOURLY_FIELDS as HOURLY_FIELDS,
        OpenMeteoClient,
        WeatherFetchError,
        fetch_hourly_forecast as fetch_weather_forecast,
    )
    from heatguard.weather.models import HourlyForecast, HourlyWeatherRecord
except ImportError:
    from heat_index import calculate_heat_index
    from risk import calculate_risk
    from validation import HourlyThermalResult
    from wbgt import calculate_wbgt
    from heatguard.weather.client import (
        OPEN_METEO_URL,
        REQUIRED_HOURLY_FIELDS as HOURLY_FIELDS,
        OpenMeteoClient,
        WeatherFetchError,
        fetch_hourly_forecast as fetch_weather_forecast,
    )
    from heatguard.weather.models import HourlyForecast, HourlyWeatherRecord


def compute_hourly_thermal_stress(
    forecast: HourlyForecast,
    hours_ahead: int = 24,
    daylight_only: bool = False,
) -> List[HourlyThermalResult]:
    """
    Compute WBGT, Heat Index, and risk classifications for each record in a forecast.

    Parameters:
        forecast: HourlyForecast containing validated HourlyWeatherRecord entries
        hours_ahead: maximum number of hours to process
        daylight_only: whether to restrict calculation to daytime hours (06:00 to 18:00)

    Returns:
        List of structured HourlyThermalResult dataclasses.
    """
    records_to_process = forecast.records[:hours_ahead]
    results: List[HourlyThermalResult] = []

    for rec in records_to_process:
        if daylight_only:
            try:
                hour = datetime.fromisoformat(rec.timestamp).hour
                if hour < 6 or hour > 18:
                    continue
            except (ValueError, TypeError):
                pass

        heat_index = calculate_heat_index(rec.temperature_c, rec.relative_humidity)

        wbgt = calculate_wbgt(
            temperature_c=rec.temperature_c,
            humidity=rec.relative_humidity,
            wind_kmh=rec.wind_speed_kmh,
            radiation=rec.shortwave_radiation,
            pressure_hpa=rec.surface_pressure_hpa,
            direct_radiation=rec.direct_normal_irradiance,
            timestamp=rec.timestamp,
            latitude=forecast.latitude,
            longitude=forecast.longitude,
            timezone=forecast.timezone,
        )

        risk = calculate_risk(heat_index, wbgt)

        results.append(
            HourlyThermalResult(
                timestamp=rec.timestamp,
                temp_c=rec.temperature_c,
                humidity=rec.relative_humidity,
                wind_kmh=rec.wind_speed_kmh,
                heat_index_c=heat_index,
                wbgt_c=wbgt,
                heat_index_risk=risk["heat_index_level"],
                wbgt_risk=risk["wbgt_level"],
                risk_verdict=risk["verdict"],
                data_source=forecast.data_source,
                is_fallback=forecast.is_fallback,
            )
        )

    return results


def get_hourly_risk_forecast(
    latitude: float,
    longitude: float,
    timezone: str = "Asia/Kolkata",
    hours_ahead: int = 24,
    daylight_only: bool = False,
    forecast_days: int = 5,
) -> List[Dict[str, Any]]:
    """
    Fetch forecast and compute thermal stress & risk for each hour.
    Returns standard list of dictionaries for complete backward compatibility.
    """
    client = OpenMeteoClient()
    forecast = client.fetch_hourly_forecast(
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        forecast_days=forecast_days,
    )

    thermal_results = compute_hourly_thermal_stress(
        forecast=forecast,
        hours_ahead=hours_ahead,
        daylight_only=daylight_only,
    )

    return [res.to_dict() for res in thermal_results]


# Retain legacy functional alias for backward compatibility
fetch_hourly_forecast = fetch_weather_forecast


def _print_forecast(results: List[Dict[str, Any]]) -> None:
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
        forecast_output = get_hourly_risk_forecast(LATITUDE, LONGITUDE, hours_ahead=10)
    except WeatherFetchError as exc:
        print(f"Error: {exc}")
    else:
        _print_forecast(forecast_output)