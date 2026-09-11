"""
Physical scenario validation and determinism tests for the WBGT engine.
Validates physical laws and consistency without inventing synthetic benchmark data.
"""

import pytest

from heatguard.thermal.validation import HourlyThermalResult, ThermalValidationError
from heatguard.thermal.wbgt import calculate_wbgt
from heatguard.thermal.weather import compute_hourly_thermal_stress
from heatguard.weather.models import HourlyForecast, HourlyWeatherRecord


# --- Determinism ------------------------------------------------------------

def test_wbgt_is_strictly_deterministic():
    """Calling calculate_wbgt multiple times with identical inputs must return identical results."""
    params = dict(
        temperature_c=34.0,
        humidity=65.0,
        wind_kmh=12.0,
        radiation=750.0,
        pressure_hpa=1005.0,
        direct_radiation=550.0,
        timestamp="2026-06-15T13:00",
    )
    results = [calculate_wbgt(**params) for _ in range(5)]
    assert all(r == results[0] for r in results)


# --- Physical Sensitivity Checks -------------------------------------------

def test_wbgt_increases_monotonically_with_temperature():
    """Holding all other factors constant, higher air temperature must yield higher WBGT."""
    cool = calculate_wbgt(
        temperature_c=28.0, humidity=60.0, wind_kmh=10.0,
        radiation=500.0, pressure_hpa=1005.0, direct_radiation=350.0,
        timestamp="2026-06-15T12:00",
    )
    hot = calculate_wbgt(
        temperature_c=38.0, humidity=60.0, wind_kmh=10.0,
        radiation=500.0, pressure_hpa=1005.0, direct_radiation=350.0,
        timestamp="2026-06-15T12:00",
    )
    assert hot > cool


def test_wbgt_increases_with_higher_humidity():
    """Holding all other factors constant, higher humidity must yield higher WBGT."""
    dry = calculate_wbgt(
        temperature_c=32.0, humidity=30.0, wind_kmh=10.0,
        radiation=500.0, pressure_hpa=1005.0, direct_radiation=350.0,
        timestamp="2026-06-15T12:00",
    )
    humid = calculate_wbgt(
        temperature_c=32.0, humidity=85.0, wind_kmh=10.0,
        radiation=500.0, pressure_hpa=1005.0, direct_radiation=350.0,
        timestamp="2026-06-15T12:00",
    )
    assert humid > dry


def test_wbgt_decreases_with_higher_wind_speed():
    """Holding all other factors constant, higher convective cooling from wind reduces WBGT."""
    still_air = calculate_wbgt(
        temperature_c=35.0, humidity=60.0, wind_kmh=2.0,
        radiation=600.0, pressure_hpa=1005.0, direct_radiation=400.0,
        timestamp="2026-06-15T12:00",
    )
    breeze = calculate_wbgt(
        temperature_c=35.0, humidity=60.0, wind_kmh=25.0,
        radiation=600.0, pressure_hpa=1005.0, direct_radiation=400.0,
        timestamp="2026-06-15T12:00",
    )
    assert breeze < still_air


def test_wbgt_increases_with_solar_radiation():
    """Sunny conditions add black globe radiant heat load compared to zero radiation."""
    no_sun = calculate_wbgt(
        temperature_c=30.0, humidity=60.0, wind_kmh=10.0,
        radiation=0.0, pressure_hpa=1005.0, direct_radiation=0.0,
        timestamp="2026-06-15T12:00",
    )
    full_sun = calculate_wbgt(
        temperature_c=30.0, humidity=60.0, wind_kmh=10.0,
        radiation=800.0, pressure_hpa=1005.0, direct_radiation=600.0,
        timestamp="2026-06-15T12:00",
    )
    assert full_sun > no_sun


# --- Boundary & Edge Cases -------------------------------------------------

def test_wbgt_zero_wind_does_not_crash():
    """Zero wind speed should be handled safely without division-by-zero errors."""
    result = calculate_wbgt(
        temperature_c=30.0, humidity=70.0, wind_kmh=0.0,
        radiation=300.0, pressure_hpa=1005.0, direct_radiation=150.0,
        timestamp="2026-06-15T11:00",
    )
    assert isinstance(result, float)
    assert 20.0 < result < 45.0


def test_wbgt_invalid_temperature_raises_error():
    with pytest.raises(ThermalValidationError):
        calculate_wbgt(
            temperature_c=70.0, humidity=50.0, wind_kmh=10.0,  # 70°C exceeds bounds
            radiation=500.0, pressure_hpa=1005.0, direct_radiation=300.0,
            timestamp="2026-06-15T12:00",
        )


def test_wbgt_invalid_humidity_raises_error():
    with pytest.raises(ThermalValidationError):
        calculate_wbgt(
            temperature_c=30.0, humidity=-5.0, wind_kmh=10.0,  # negative humidity
            radiation=500.0, pressure_hpa=1005.0, direct_radiation=300.0,
            timestamp="2026-06-15T12:00",
        )


# --- Pipeline Integration Tests --------------------------------------------

def test_compute_hourly_thermal_stress_pipeline():
    record1 = HourlyWeatherRecord(
        timestamp="2026-06-15T12:00",
        temperature_c=32.0,
        relative_humidity=60.0,
        wind_speed_kmh=10.0,
        shortwave_radiation=700.0,
        surface_pressure_hpa=1005.0,
        direct_normal_irradiance=500.0,
    )
    record2 = HourlyWeatherRecord(
        timestamp="2026-06-15T22:00",
        temperature_c=24.0,
        relative_humidity=85.0,
        wind_speed_kmh=8.0,
        shortwave_radiation=0.0,
        surface_pressure_hpa=1008.0,
        direct_normal_irradiance=0.0,
    )
    forecast = HourlyForecast(
        latitude=12.9716,
        longitude=77.5946,
        timezone="Asia/Kolkata",
        records=[record1, record2],
    )

    results = compute_hourly_thermal_stress(forecast)
    assert len(results) == 2
    assert all(isinstance(r, HourlyThermalResult) for r in results)
    assert results[0].wbgt_c > results[1].wbgt_c

    # Test daylight filtering
    daylight_results = compute_hourly_thermal_stress(forecast, daylight_only=True)
    assert len(daylight_results) == 1
    assert daylight_results[0].timestamp == "2026-06-15T12:00"
