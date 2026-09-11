"""
Unit tests for heat_index.py and risk.py.

wbgt.py is not covered here since it depends on thermofeel/earthkit which
aren't installed in every environment — test it separately once those are
available, using reference values from a WBGT calculator/table as ground
truth (e.g. NOAA's HeatRisk or a published Liljegren-model comparison).
"""

import pytest

from heat_index import calculate_heat_index
from risk import RiskLevel, calculate_risk, classify_heat_index, classify_wbgt


# --- heat_index.py -----------------------------------------------------

def test_heat_index_below_80f_returns_raw_temp():
    # 25°C ≈ 77°F, below the 80°F threshold
    assert calculate_heat_index(25, 50) == 25


def test_heat_index_known_value():
    # 32.2°C (90°F), 70% humidity -> NWS table value is ~105.8°F ≈ 41.0°C
    result = calculate_heat_index(32.2, 70)
    assert result == pytest.approx(41.0, abs=0.5)


def test_heat_index_high_extreme():
    # 40°C (104°F), 60% humidity -> should land in "extreme danger" territory
    result = calculate_heat_index(40, 60)
    assert result > 51


# --- risk.py -------------------------------------------------------------

def test_classify_heat_index_low():
    assert classify_heat_index(20) == RiskLevel.LOW


def test_classify_heat_index_boundary():
    assert classify_heat_index(26.9) == RiskLevel.LOW
    assert classify_heat_index(27.0) == RiskLevel.CAUTION


def test_classify_heat_index_extreme_danger():
    assert classify_heat_index(55) == RiskLevel.EXTREME_DANGER


def test_classify_wbgt_flags():
    assert classify_wbgt(25) == RiskLevel.LOW           # green
    assert classify_wbgt(28) == RiskLevel.CAUTION        # yellow
    assert classify_wbgt(30) == RiskLevel.EXTREME_CAUTION  # orange
    assert classify_wbgt(31.5) == RiskLevel.DANGER       # red
    assert classify_wbgt(33) == RiskLevel.EXTREME_DANGER  # black


def test_calculate_risk_verdict_is_more_severe():
    # heat index says CAUTION, wbgt says EXTREME_DANGER -> verdict should be EXTREME_DANGER
    result = calculate_risk(heat_index_c=28, wbgt_c=33)
    assert result["heat_index_level"] == RiskLevel.CAUTION
    assert result["wbgt_level"] == RiskLevel.EXTREME_DANGER
    assert result["verdict"] == RiskLevel.EXTREME_DANGER


def test_calculate_risk_both_low():
    result = calculate_risk(heat_index_c=20, wbgt_c=22)
    assert result["verdict"] == RiskLevel.LOW


def test_risk_level_string_formatting():
    assert str(RiskLevel.EXTREME_CAUTION) == "Extreme Caution"

from wbgt import calculate_wbgt


def test_wbgt_night():
    result = calculate_wbgt(
        temperature_c=25.0,
        humidity=80.0,
        wind_kmh=10.0,
        radiation=0.0,
        pressure_hpa=912.0,
        direct_radiation=0.0,
        timestamp="2026-09-10T02:00"
    )

    assert 20.0 < result < 25.0