"""
HeatGuard Occupational Heat Risk Module.
Translates thermal stress and workforce parameters into actionable operational assessments.
"""

from heatguard.risk.controls import get_recommended_controls
from heatguard.risk.engine import (
    assess_hourly_forecast_risk,
    calculate_occupational_risk,
    get_action_threshold_wbgt,
    get_clothing_adjustment_value,
)
from heatguard.risk.models import (
    OccupationalRiskLevel,
    RecommendedControl,
    RiskAssessmentResult,
    RiskFactor,
)

__all__ = [
    "OccupationalRiskLevel",
    "RiskFactor",
    "RecommendedControl",
    "RiskAssessmentResult",
    "calculate_occupational_risk",
    "assess_hourly_forecast_risk",
    "get_action_threshold_wbgt",
    "get_clothing_adjustment_value",
    "get_recommended_controls",
]
