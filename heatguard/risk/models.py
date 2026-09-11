"""
Domain models for the HeatGuard Occupational Heat Risk Engine.
Provides strongly-typed schemas for risk levels, factor breakdowns, explanations, and controls.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List


class OccupationalRiskLevel(str, Enum):
    """
    Occupational heat-risk classification levels.
    Designed for operational decision support and safety interventions.
    """
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def color_hex(self) -> str:
        """Hex color code for UI rendering."""
        mapping = {
            self.LOW: "#27ae60",       # Green
            self.MODERATE: "#f39c12",  # Amber / Yellow
            self.HIGH: "#e67e22",      # Orange
            self.CRITICAL: "#c0392b",  # Red
        }
        return mapping[self]

    @property
    def flag_name(self) -> str:
        mapping = {
            self.LOW: "Green Flag",
            self.MODERATE: "Yellow Flag",
            self.HIGH: "Orange Flag",
            self.CRITICAL: "Red / Black Flag",
        }
        return mapping[self]


@dataclass(frozen=True)
class RiskFactor:
    """Individual driver contributing to the overall occupational risk score."""
    category: str
    factor: str
    severity: str  # "low", "moderate", "high", "critical"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RecommendedControl:
    """Actionable heat-illness prevention control."""
    category: str
    action: str
    priority: str  # "Routine", "High", "Mandatory"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class RiskAssessmentResult:
    """
    Structured outcome of the occupational heat risk evaluation for a single hour.
    """
    timestamp: str
    risk_level: OccupationalRiskLevel
    risk_score: float  # 0.0 to 100.0
    effective_wbgt_c: float
    primary_risk_factors: List[RiskFactor]
    explanation: str
    recommended_controls: List[RecommendedControl]
    is_during_shift: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "risk_level": self.risk_level.value,
            "risk_score": round(self.risk_score, 1),
            "effective_wbgt_c": round(self.effective_wbgt_c, 2),
            "primary_risk_factors": [f.to_dict() for f in self.primary_risk_factors],
            "explanation": self.explanation,
            "recommended_controls": [c.to_dict() for c in self.recommended_controls],
            "is_during_shift": self.is_during_shift,
        }
