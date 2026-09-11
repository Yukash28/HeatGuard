"""
Tests for meteorological validation rules and unit conversions.
"""

import pytest

from heatguard.thermal.risk import RiskLevel
from heatguard.thermal.validation import (
    HourlyThermalResult,
    ThermalValidationError,
    celsius_to_kelvin,
    kelvin_to_celsius,
    kmh_to_ms,
    ms_to_kmh,
    validate_humidity,
    validate_pressure,
    validate_radiation,
    validate_temperature,
    validate_wind_speed,
)


# --- Temperature Validation Tests -------------------------------------------

def test_validate_temperature_valid():
    assert validate_temperature(25.0) == 25.0
    assert validate_temperature(0) == 0.0
    assert validate_temperature(-40.0) == -40.0
    assert validate_temperature(55.0) == 55.0


def test_validate_temperature_out_of_bounds():
    with pytest.raises(ThermalValidationError, match="between -50°C and 60°C"):
        validate_temperature(-55.0)

    with pytest.raises(ThermalValidationError, match="between -50°C and 60°C"):
        validate_temperature(65.0)


def test_validate_temperature_non_numeric():
    with pytest.raises(TypeError, match="numeric"):
        validate_temperature("25.0")  # type: ignore


# --- Humidity Validation Tests ----------------------------------------------

def test_validate_humidity_valid():
    assert validate_humidity(0.0) == 0.0
    assert validate_humidity(50.5) == 50.5
    assert validate_humidity(100.0) == 100.0


def test_validate_humidity_out_of_bounds():
    with pytest.raises(ThermalValidationError, match="between 0% and 100%"):
        validate_humidity(-1.0)

    with pytest.raises(ThermalValidationError, match="between 0% and 100%"):
        validate_humidity(105.0)


# --- Wind Speed Validation Tests --------------------------------------------

def test_validate_wind_speed_valid():
    assert validate_wind_speed(0.0) == 0.0
    assert validate_wind_speed(15.2) == 15.2
    assert validate_wind_speed(120.0) == 120.0


def test_validate_wind_speed_negative():
    with pytest.raises(ThermalValidationError, match="between 0 and 250"):
        validate_wind_speed(-5.0)


# --- Radiation Validation Tests ---------------------------------------------

def test_validate_radiation_valid():
    assert validate_radiation(0.0) == 0.0
    assert validate_radiation(850.0) == 850.0


def test_validate_radiation_negative():
    with pytest.raises(ThermalValidationError, match="between 0 and 2000"):
        validate_radiation(-10.0)


# --- Pressure Validation Tests ----------------------------------------------

def test_validate_pressure_valid():
    assert validate_pressure(1013.25) == 1013.25
    assert validate_pressure(910.0) == 910.0  # Bengaluru elevation


def test_validate_pressure_out_of_bounds():
    with pytest.raises(ThermalValidationError, match="between 500 and 1100"):
        validate_pressure(400.0)

    with pytest.raises(ThermalValidationError, match="between 500 and 1100"):
        validate_pressure(1200.0)


# --- Unit Conversion Tests --------------------------------------------------

def test_celsius_kelvin_roundtrip():
    temp_c = 25.0
    k = celsius_to_kelvin(temp_c)
    assert k == pytest.approx(298.15)
    assert kelvin_to_celsius(k) == pytest.approx(temp_c)


def test_kmh_ms_roundtrip():
    speed_kmh = 36.0
    ms = kmh_to_ms(speed_kmh)
    assert ms == pytest.approx(10.0)
    assert ms_to_kmh(ms) == pytest.approx(speed_kmh)


# --- HourlyThermalResult Schema Tests ---------------------------------------

def test_hourly_thermal_result_to_dict():
    result = HourlyThermalResult(
        timestamp="2026-06-15T14:00",
        temp_c=34.0,
        humidity=60.0,
        wind_kmh=12.0,
        heat_index_c=42.5,
        wbgt_c=31.2,
        heat_index_risk=RiskLevel.DANGER,
        wbgt_risk=RiskLevel.DANGER,
        risk_verdict=RiskLevel.DANGER,
    )
    d = result.to_dict()
    assert d["timestamp"] == "2026-06-15T14:00"
    assert d["wbgt_c"] == 31.2
    assert d["risk_verdict"] == RiskLevel.DANGER
