"""
Unit and scenario tests for the HeatGuard Occupational Heat Risk Engine.
Validates multi-factor deterministic scoring, factor extraction, explanations, and controls.
"""

import pytest

from heatguard.risk.engine import (
    assess_hourly_forecast_risk,
    calculate_occupational_risk,
    get_action_threshold_wbgt,
    get_clothing_adjustment_value,
)
from heatguard.risk.models import OccupationalRiskLevel, RiskAssessmentResult
from heatguard.thermal.validation import ThermalValidationError
from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    WorkforceProfile,
    WorkIntensity,
    WorkType,
)


# --- 1. Low Thermal Stress Scenario -----------------------------------------

def test_low_thermal_stress_scenario():
    """Cool, pleasant weather with light work should result in LOW risk."""
    res = calculate_occupational_risk(
        wbgt_c=21.0,
        temperature_c=23.0,
        humidity=60.0,
        wind_kmh=12.0,
        radiation=200.0,
        work_intensity=WorkIntensity.LIGHT,
        clothing_or_ppe=ClothingPPE.STANDARD_WORKWEAR.value,
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    assert res.risk_level == OccupationalRiskLevel.LOW
    assert res.risk_score < 30.0
    assert any("safe baselines" in f.factor.lower() or f.category == "Environmental" for f in res.primary_risk_factors)
    assert "low operational risk" in res.explanation.lower()


# --- 2. Elevated Thermal Stress Scenario ------------------------------------

def test_elevated_thermal_stress_scenario():
    """High WBGT (32°C) with strong sun should trigger HIGH or CRITICAL risk."""
    res = calculate_occupational_risk(
        wbgt_c=32.5,
        temperature_c=36.0,
        humidity=65.0,
        wind_kmh=6.0,
        radiation=850.0,
        work_intensity=WorkIntensity.MODERATE,
        clothing_or_ppe=ClothingPPE.STANDARD_WORKWEAR.value,
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    assert res.risk_level in (OccupationalRiskLevel.HIGH, OccupationalRiskLevel.CRITICAL)
    assert res.risk_score >= 60.0
    assert any(f.category == "Environmental" and "wbgt" in f.factor.lower() for f in res.primary_risk_factors)


# --- 3. Heavy Work Burden Impact --------------------------------------------

def test_heavy_work_increases_risk_score():
    """Holding all environmental parameters fixed, Heavy work must score higher than Light work."""
    env = dict(
        wbgt_c=27.5,
        temperature_c=30.0,
        humidity=60.0,
        wind_kmh=10.0,
        radiation=500.0,
        clothing_or_ppe=ClothingPPE.STANDARD_WORKWEAR.value,
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )

    light_res = calculate_occupational_risk(work_intensity=WorkIntensity.LIGHT, **env)
    heavy_res = calculate_occupational_risk(work_intensity=WorkIntensity.HEAVY, **env)

    assert heavy_res.risk_score > light_res.risk_score
    assert any("heavy physical exertion" in f.factor.lower() for f in heavy_res.primary_risk_factors)


# --- 4. Unacclimatized Workforce Impact -------------------------------------

def test_unacclimatized_cohort_increases_risk_score():
    """Unacclimatized cohorts have lower physiological heat tolerance, increasing risk score."""
    base_params = dict(
        wbgt_c=28.0,
        temperature_c=31.0,
        humidity=55.0,
        wind_kmh=8.0,
        radiation=450.0,
        work_intensity=WorkIntensity.MODERATE,
        clothing_or_ppe=ClothingPPE.STANDARD_WORKWEAR.value,
    )

    acclim_res = calculate_occupational_risk(
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
        **base_params,
    )
    unacclim_res = calculate_occupational_risk(
        acclimatization_status=AcclimatizationStatus.UNACCLIMATIZED,
        **base_params,
    )

    assert unacclim_res.risk_score > acclim_res.risk_score
    assert any("unacclimatized" in f.factor.lower() for f in unacclim_res.primary_risk_factors)
    # Action threshold for unacclimatized must be lower than acclimatized
    assert get_action_threshold_wbgt(WorkIntensity.MODERATE, AcclimatizationStatus.UNACCLIMATIZED) < \
           get_action_threshold_wbgt(WorkIntensity.MODERATE, AcclimatizationStatus.ACCLIMATIZED)


# --- 5. PPE & Impermeable Clothing Penalty ----------------------------------

def test_clothing_ppe_penalty():
    """Impermeable chemical gear traps body heat and elevates Effective WBGT."""
    env = dict(
        wbgt_c=26.0,
        temperature_c=29.0,
        humidity=50.0,
        wind_kmh=10.0,
        radiation=300.0,
        work_intensity=WorkIntensity.MODERATE,
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )

    standard_res = calculate_occupational_risk(clothing_or_ppe="Standard Workwear", **env)
    impermeable_res = calculate_occupational_risk(clothing_or_ppe="Impermeable / Chemical PPE", **env)

    assert impermeable_res.effective_wbgt_c > standard_res.effective_wbgt_c
    assert impermeable_res.risk_score > standard_res.risk_score
    assert any("impermeable" in f.factor.lower() for f in impermeable_res.primary_risk_factors)


# --- 6. Determinism ---------------------------------------------------------

def test_risk_calculation_is_deterministic():
    """Multiple evaluations of identical parameters must yield identical risk scores."""
    params = dict(
        wbgt_c=29.4,
        temperature_c=32.0,
        humidity=65.0,
        wind_kmh=7.5,
        radiation=620.0,
        work_intensity=WorkIntensity.HEAVY,
        clothing_or_ppe=ClothingPPE.HI_VIS_VEST_HELMET.value,
        acclimatization_status=AcclimatizationStatus.MIXED,
    )

    runs = [calculate_occupational_risk(**params) for _ in range(5)]
    assert all(r.risk_score == runs[0].risk_score for r in runs)
    assert all(r.risk_level == runs[0].risk_level for r in runs)
    assert all(r.explanation == runs[0].explanation for r in runs)


# --- 7. Invalid & Out-of-Bounds Input Handling ------------------------------

def test_invalid_environmental_inputs_raise_errors():
    valid_args = dict(
        wbgt_c=25.0,
        temperature_c=28.0,
        humidity=50.0,
        wind_kmh=10.0,
        radiation=400.0,
        work_intensity=WorkIntensity.MODERATE,
        clothing_or_ppe="Standard",
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )

    # Invalid relative humidity (< 0%)
    with pytest.raises(ThermalValidationError):
        calculate_occupational_risk(**{**valid_args, "humidity": -10.0})

    # Invalid temperature (> 60°C)
    with pytest.raises(ThermalValidationError):
        calculate_occupational_risk(**{**valid_args, "temperature_c": 75.0})

    # Negative wind speed
    with pytest.raises(ThermalValidationError):
        calculate_occupational_risk(**{**valid_args, "wind_kmh": -5.0})


# --- 8. Batch Evaluation & Shift Overlay ------------------------------------

def test_assess_hourly_forecast_risk_pipeline():
    forecast_items = [
        {"timestamp": "2026-06-15T09:00", "wbgt_c": 26.5, "temp_c": 28.0, "humidity": 60.0, "wind_kmh": 8.0, "radiation": 400.0},
        {"timestamp": "2026-06-15T13:00", "wbgt_c": 32.0, "temp_c": 35.0, "humidity": 55.0, "wind_kmh": 6.0, "radiation": 800.0},
        {"timestamp": "2026-06-15T21:00", "wbgt_c": 23.0, "temp_c": 25.0, "humidity": 75.0, "wind_kmh": 10.0, "radiation": 0.0},
    ]
    profile = WorkforceProfile(
        id="wf-test",
        site_id="s1",
        number_of_workers=20,
        work_type=WorkType.CONSTRUCTION,
        work_intensity=WorkIntensity.HEAVY,
        shift_start="08:00",
        shift_end="17:00",
        clothing_or_ppe=ClothingPPE.HI_VIS_VEST_HELMET.value,
        acclimatization_status=AcclimatizationStatus.MIXED,
    )

    results = assess_hourly_forecast_risk(forecast_items, profile)
    assert len(results) == 3
    assert all(isinstance(r, RiskAssessmentResult) for r in results)

    # 13:00 (midday, inside shift) should have much higher risk than 21:00 (night, off-shift)
    assert results[1].is_during_shift is True
    assert results[2].is_during_shift is False
    assert results[1].risk_score > results[0].risk_score > results[2].risk_score
