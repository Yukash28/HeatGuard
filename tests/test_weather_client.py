"""
Tests for Open-Meteo weather client and data models.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from heatguard.weather.client import (
    OpenMeteoClient,
    WeatherAPIError,
    WeatherFetchError,
)
from heatguard.weather.models import HourlyForecast, HourlyWeatherRecord


def _make_sample_api_response():
    """Create a realistic Open-Meteo response dict."""
    return {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "timezone": "Asia/Kolkata",
        "hourly": {
            "time": ["2026-06-15T12:00", "2026-06-15T13:00"],
            "temperature_2m": [32.5, 33.1],
            "relative_humidity_2m": [60.0, 58.0],
            "wind_speed_10m": [12.0, 14.5],
            "shortwave_radiation": [750.0, 800.0],
            "surface_pressure": [1005.0, 1004.5],
            "direct_normal_irradiance": [600.0, 650.0],
        },
    }


def test_hourly_weather_record_to_dict():
    record = HourlyWeatherRecord(
        timestamp="2026-06-15T12:00",
        temperature_c=30.0,
        relative_humidity=65.0,
        wind_speed_kmh=10.0,
        shortwave_radiation=500.0,
        surface_pressure_hpa=1008.0,
        direct_normal_irradiance=400.0,
    )
    d = record.to_dict()
    assert d["timestamp"] == "2026-06-15T12:00"
    assert d["temperature_c"] == 30.0
    assert d["relative_humidity"] == 65.0


def test_hourly_forecast_container():
    record = HourlyWeatherRecord(
        timestamp="2026-06-15T12:00",
        temperature_c=30.0,
        relative_humidity=65.0,
        wind_speed_kmh=10.0,
        shortwave_radiation=500.0,
        surface_pressure_hpa=1008.0,
        direct_normal_irradiance=400.0,
    )
    forecast = HourlyForecast(
        latitude=12.97,
        longitude=77.59,
        timezone="Asia/Kolkata",
        records=[record],
    )
    assert len(forecast) == 1
    assert forecast[0].temperature_c == 30.0
    df = forecast.to_dataframe()
    assert len(df) == 1
    assert "temperature_c" in df.columns


def test_client_parse_valid_response():
    client = OpenMeteoClient()
    raw = _make_sample_api_response()
    forecast = client.parse_raw_response(raw, latitude=12.9716, longitude=77.5946, timezone="Asia/Kolkata")
    assert len(forecast) == 2
    assert forecast[0].timestamp == "2026-06-15T12:00"
    assert forecast[0].temperature_c == 32.5
    assert forecast[1].shortwave_radiation == 800.0


def test_client_parse_skips_null_hours():
    """Hours with null values in any required field must be filtered out."""
    raw = _make_sample_api_response()
    # Nullify one field in the first hour
    raw["hourly"]["shortwave_radiation"][0] = None

    client = OpenMeteoClient()
    forecast = client.parse_raw_response(raw, latitude=12.9716, longitude=77.5946, timezone="Asia/Kolkata")
    assert len(forecast) == 1
    assert forecast[0].timestamp == "2026-06-15T13:00"


def test_client_missing_hourly_key_raises_error():
    client = OpenMeteoClient()
    with pytest.raises(WeatherFetchError, match="invalid structure"):
        client.parse_raw_response({"error": True, "reason": "Invalid coords"}, 12.0, 77.0, "UTC")


def test_client_missing_required_field_raises_error():
    client = OpenMeteoClient()
    raw = {
        "hourly": {
            "time": ["2026-06-15T12:00"],
            "temperature_2m": [30.0],
            # missing humidity, wind, etc.
        }
    }
    with pytest.raises(WeatherFetchError, match="Required field"):
        client.parse_raw_response(raw, 12.0, 77.0, "UTC")


def test_client_http_error_handling():
    client = OpenMeteoClient()
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
    mock_session.get.return_value = mock_response

    client.session = mock_session
    with pytest.raises(WeatherAPIError, match="HTTP 500"):
        client.fetch_hourly_forecast(12.97, 77.59)


def test_client_network_timeout_handling():
    client = OpenMeteoClient()
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.Timeout("Connection timed out")

    client.session = mock_session
    with pytest.raises(WeatherFetchError, match="Could not connect"):
        client.fetch_hourly_forecast(12.97, 77.59)
