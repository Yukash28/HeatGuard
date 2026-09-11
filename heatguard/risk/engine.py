"""
HeatGuard Occupational Heat Risk Engine.
Translates environmental thermal metrics and workforce parameters into deterministic,
explainable operational risk assessments based on ISO 7243 and ACGIH principles.
"""

from typing import Any, Dict, List, Optional

from heatguard.risk.controls import get_recommended_controls
from heatguard.risk.models import (
    OccupationalRiskLevel,
    RecommendedControl,
    RiskAssessmentResult,
    RiskFactor,
)
from heatguard.thermal.validation import (
    validate_humidity,
    validate_pressure,
    validate_radiation,
    validate_temperature,
    validate_wind_speed,
)
from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    WorkforceProfile,
    WorkIntensity,
)


def get_clothing_adjustment_value(clothing_or_ppe: str) -> float:
    """
    Determine Clothing Adjustment Value (CAV in °C) per ISO 7243 and ACGIH guidelines.
    Added to WBGT to compute Effective WBGT.
    """
    c_lower = str(clothing_or_ppe).lower()
    if "impermeable" in c_lower or "chemical" in c_lower:
        return 3.5
    elif "coverall" in c_lower or "double" in c_lower:
        return 1.5
    elif "hi-vis" in c_lower or "helmet" in c_lower or "vest" in c_lower:
        return 0.5
    else:
        # Standard workwear baseline
        return 0.0


def get_action_threshold_wbgt(
    work_intensity: WorkIntensity,
    acclimatization_status: AcclimatizationStatus,
) -> float:
    """
    Derive reference occupational action threshold (in °C WBGT)
    derived from ISO 7243 / ACGIH TLV baseline values and NIOSH action limits.
    """
    # Baseline threshold by metabolic workload
    baseline_thresholds = {
        WorkIntensity.LIGHT: 30.0,      # ~200 W (e.g. driving, inspection)
        WorkIntensity.MODERATE: 28.0,   # ~300 W (e.g. walking, warehouse, handling)
        WorkIntensity.HEAVY: 26.0,      # ~400 W (e.g. digging, concrete, asphalt)
    }
    t_base = baseline_thresholds.get(work_intensity, 28.0)

    # Acclimatization threshold adjustment (unacclimatized cohorts need earlier action)
    acclimatization_offsets = {
        AcclimatizationStatus.ACCLIMATIZED: 0.0,
        AcclimatizationStatus.MIXED: -1.5,
        AcclimatizationStatus.UNACCLIMATIZED: -2.5,
    }
    offset = acclimatization_offsets.get(acclimatization_status, 0.0)

    return t_base + offset


def calculate_occupational_risk(
    wbgt_c: float,
    temperature_c: float,
    humidity: float,
    wind_kmh: float,
    radiation: float,
    work_intensity: WorkIntensity,
    clothing_or_ppe: str,
    acclimatization_status: AcclimatizationStatus,
    timestamp: str = "2026-01-01T12:00",
    is_during_shift: bool = True,
) -> RiskAssessmentResult:
    """
    Calculate deterministic occupational heat risk assessment.

    Parameters:
        wbgt_c: Outdoor Wet Bulb Globe Temperature in °C
        temperature_c: Air dry-bulb temperature in °C
        humidity: Relative humidity in %
        wind_kmh: Wind speed in km/h
        radiation: Downward solar radiation in W/m²
        work_intensity: WorkIntensity (LIGHT, MODERATE, HEAVY)
        clothing_or_ppe: Description of protective equipment / workwear
        acclimatization_status: AcclimatizationStatus (ACCLIMATIZED, UNACCLIMATIZED, MIXED)
        timestamp: ISO timestamp for the assessment hour
        is_during_shift: Whether this hour overlaps with active work shift

    Returns:
        RiskAssessmentResult with score, level, factors, explanation, and controls.
    """
    # 1. Input Validation
    t_c = validate_temperature(temperature_c)
    rh = validate_humidity(humidity)
    wind = validate_wind_speed(wind_kmh)
    rad = validate_radiation(radiation)

    if not isinstance(work_intensity, WorkIntensity):
        work_intensity = WorkIntensity.from_str(str(work_intensity))
    if not isinstance(acclimatization_status, AcclimatizationStatus):
        acclimatization_status = AcclimatizationStatus.from_str(str(acclimatization_status))

    # 2. Clothing Adjustment Value (CAV) & Effective WBGT
    cav = get_clothing_adjustment_value(clothing_or_ppe)
    effective_wbgt = float(wbgt_c + cav)

    # 3. Reference Action Threshold
    t_action = get_action_threshold_wbgt(work_intensity, acclimatization_status)

    # 4. Continuous Deterministic Scoring (0.0 to 100.0)
    # Action threshold maps to 40.0; each 1.0°C deviation alters score by 10 points
    strain_delta = effective_wbgt - t_action
    base_score = 40.0 + (strain_delta * 10.0)

    # Environmental co-factors
    solar_penalty = 4.0 if rad >= 700 else (2.0 if rad >= 350 else 0.0)
    humidity_penalty = 3.0 if rh >= 75.0 else 0.0
    wind_penalty = 3.0 if wind < 5.0 else 0.0

    raw_score = base_score + solar_penalty + humidity_penalty + wind_penalty
    risk_score = round(max(0.0, min(100.0, raw_score)), 1)

    # 5. Risk Level Classification
    if risk_score < 30.0:
        risk_level = OccupationalRiskLevel.LOW
    elif risk_score < 60.0:
        risk_level = OccupationalRiskLevel.MODERATE
    elif risk_score < 85.0:
        risk_level = OccupationalRiskLevel.HIGH
    else:
        risk_level = OccupationalRiskLevel.CRITICAL

    # 6. Extract Primary Risk Factors
    factors: List[RiskFactor] = []

    # Environmental Factors
    if wbgt_c >= 32.0:
        factors.append(RiskFactor("Environmental", f"Extreme outdoor WBGT ({wbgt_c:.1f}°C)", "critical"))
    elif wbgt_c >= 28.0:
        factors.append(RiskFactor("Environmental", f"Elevated outdoor WBGT ({wbgt_c:.1f}°C)", "high"))
    elif wbgt_c >= 25.0:
        factors.append(RiskFactor("Environmental", f"Moderate ambient thermal stress ({wbgt_c:.1f}°C WBGT)", "moderate"))

    if rad >= 700:
        factors.append(RiskFactor("Environmental", f"Intense direct solar radiation ({rad:.0f} W/m²)", "high"))
    if rh >= 75.0:
        factors.append(RiskFactor("Environmental", f"High humidity ({rh:.0f}%) suppresses evaporative cooling", "moderate"))
    if wind < 5.0:
        factors.append(RiskFactor("Environmental", f"Stagnant air ({wind:.1f} km/h) minimizes convective dissipation", "moderate"))

    # Workforce Factors
    if work_intensity == WorkIntensity.HEAVY:
        factors.append(RiskFactor("Metabolic", "Heavy physical exertion generates rapid internal core body heat", "high"))
    elif work_intensity == WorkIntensity.MODERATE:
        factors.append(RiskFactor("Metabolic", "Moderate physical activity adds sustained metabolic heat load", "moderate"))

    if acclimatization_status == AcclimatizationStatus.UNACCLIMATIZED:
        severity = "critical" if risk_score >= 60.0 else "high"
        factors.append(RiskFactor("Physiological", "Unacclimatized cohort lacks cardiovascular and sweat-rate adaptation", severity))
    elif acclimatization_status == AcclimatizationStatus.MIXED:
        factors.append(RiskFactor("Physiological", "Mixed acclimatization: unadapted workers require conservative oversight", "moderate"))

    if cav >= 3.0:
        factors.append(RiskFactor("PPE/Gear", f"Impermeable protective equipment severely traps heat (CAV +{cav:.1f}°C)", "critical"))
    elif cav >= 1.0:
        factors.append(RiskFactor("PPE/Gear", f"Coveralls/layered clothing creates insulative thermal barrier (CAV +{cav:.1f}°C)", "moderate"))

    if not is_during_shift:
        factors.append(RiskFactor("Duration", "Hour falls outside scheduled active shift window", "low"))

    if not factors:
        factors.append(RiskFactor("Environmental", "Atmospheric and metabolic conditions within safe baselines", "low"))

    # 7. Generate Plain-English Transparent Explanation
    explanation_parts = [
        f"{risk_level.value} operational risk (Score: {risk_score:.1f}/100) at {timestamp}."
    ]

    key_drivers = []
    if wbgt_c >= 28.0:
        key_drivers.append(f"elevated WBGT of {wbgt_c:.1f}°C")
    if work_intensity == WorkIntensity.HEAVY:
        key_drivers.append("heavy physical labor")
    elif work_intensity == WorkIntensity.MODERATE:
        key_drivers.append("moderate metabolic exertion")

    if acclimatization_status == AcclimatizationStatus.UNACCLIMATIZED:
        key_drivers.append("an unacclimatized workforce cohort")
    if cav >= 1.0:
        key_drivers.append(f"insulative PPE (effective WBGT: {effective_wbgt:.1f}°C)")

    if key_drivers:
        explanation_parts.append("Risk is primarily driven by " + ", ".join(key_drivers) + ".")
    else:
        explanation_parts.append("Environmental thermal stress and metabolic heat production remain within normal safe thresholds.")

    if risk_level in (OccupationalRiskLevel.HIGH, OccupationalRiskLevel.CRITICAL):
        explanation_parts.append("Immediate administrative controls and structured work-rest schedules are required to protect workers.")
    elif risk_level == OccupationalRiskLevel.MODERATE:
        explanation_parts.append("Enhanced hydration access and regular shaded breaks are recommended.")
    else:
        explanation_parts.append("Standard workplace hydration and routine supervisory oversight are adequate.")

    explanation = " ".join(explanation_parts)

    # 8. Generate Recommended Controls
    recommended_controls = get_recommended_controls(
        risk_level=risk_level,
        work_intensity=work_intensity,
        acclimatization_status=acclimatization_status,
        is_during_shift=is_during_shift,
    )

    return RiskAssessmentResult(
        timestamp=timestamp,
        risk_level=risk_level,
        risk_score=risk_score,
        effective_wbgt_c=effective_wbgt,
        primary_risk_factors=factors,
        explanation=explanation,
        recommended_controls=recommended_controls,
        is_during_shift=is_during_shift,
    )


def assess_hourly_forecast_risk(
    forecast_results: List[Dict[str, Any]],
    workforce_profile: WorkforceProfile,
) -> List[RiskAssessmentResult]:
    """
    Batch evaluate occupational heat risk for every hour in a forecast series.
    """
    assessments: List[RiskAssessmentResult] = []

    for item in forecast_results:
        ts = item["timestamp"]
        try:
            hr = int(ts.split("T")[1].split(":")[0])
            is_active = workforce_profile.is_shift_active(hr)
        except (IndexError, ValueError):
            is_active = True

        result = calculate_occupational_risk(
            wbgt_c=float(item.get("wbgt_c", 20.0)),
            temperature_c=float(item.get("temp_c", 22.0)),
            humidity=float(item.get("humidity", 50.0)),
            wind_kmh=float(item.get("wind_kmh", 10.0)),
            radiation=float(item.get("radiation", item.get("shortwave_radiation", 0.0))),
            work_intensity=workforce_profile.work_intensity,
            clothing_or_ppe=workforce_profile.clothing_or_ppe,
            acclimatization_status=workforce_profile.acclimatization_status,
            timestamp=ts,
            is_during_shift=is_active,
        )
        assessments.append(result)

    return assessments
