"""
Accepted occupational heat-risk controls and safety intervention catalog.
Follows hierarchy of controls: elimination/scheduling, engineering, administrative, and PPE.
"""

from typing import List

from heatguard.risk.models import OccupationalRiskLevel, RecommendedControl
from heatguard.workforce.models import AcclimatizationStatus, WorkIntensity


def get_recommended_controls(
    risk_level: OccupationalRiskLevel,
    work_intensity: WorkIntensity,
    acclimatization_status: AcclimatizationStatus,
    is_during_shift: bool,
) -> List[RecommendedControl]:
    """
    Generate targeted, accepted occupational controls based on evaluated risk level
    and cohort characteristics.
    """
    controls: List[RecommendedControl] = []

    if risk_level == OccupationalRiskLevel.LOW:
        controls.append(
            RecommendedControl(
                category="Hydration",
                action="Provide continuous access to cool, potable drinking water (at least 0.5 L/hour per worker).",
                priority="Routine",
            )
        )
        controls.append(
            RecommendedControl(
                category="Rest/Recovery",
                action="Maintain standard shift rest breaks under shaded conditions.",
                priority="Routine",
            )
        )
        controls.append(
            RecommendedControl(
                category="Monitoring",
                action="Encourage workers to self-monitor for mild dehydration or fatigue.",
                priority="Routine",
            )
        )

    elif risk_level == OccupationalRiskLevel.MODERATE:
        controls.append(
            RecommendedControl(
                category="Hydration",
                action="Actively prompt hydration: consume 0.75 L/hour in 15–20 minute intervals.",
                priority="High",
            )
        )
        controls.append(
            RecommendedControl(
                category="Rest/Recovery",
                action="Implement structured work-rest schedule: 45 min work / 15 min rest per hour in shade.",
                priority="High",
            )
        )
        controls.append(
            RecommendedControl(
                category="Shade/Cooling",
                action="Establish shaded rest areas within 2 minutes walk of the work zone with airflow.",
                priority="High",
            )
        )
        controls.append(
            RecommendedControl(
                category="Monitoring",
                action="Enforce a 2-person buddy system to observe peer alertness and fatigue.",
                priority="Routine",
            )
        )

    elif risk_level == OccupationalRiskLevel.HIGH:
        controls.append(
            RecommendedControl(
                category="Rest/Recovery",
                action="Mandatory work-rest schedule: 30 min work / 30 min rest per hour under active cooling/shade.",
                priority="Mandatory",
            )
        )
        controls.append(
            RecommendedControl(
                category="Hydration",
                action="Mandatory hydration: 1.0 L/hour cool water with electrolyte replenishment.",
                priority="Mandatory",
            )
        )
        controls.append(
            RecommendedControl(
                category="Workload",
                action="Rotate strenuous tasks; provide mechanical lifting aids to reduce internal metabolic heat.",
                priority="High",
            )
        )
        controls.append(
            RecommendedControl(
                category="Shade/Cooling",
                action="Deploy active cooling stations (misting fans, cold towels, or air-conditioned rest vehicle).",
                priority="High",
            )
        )
        controls.append(
            RecommendedControl(
                category="Scheduling",
                action="Reschedule high-exertion tasks to early morning (before 10:00) or post-sunset hours.",
                priority="High",
            )
        )
        controls.append(
            RecommendedControl(
                category="Monitoring",
                action="Supervisors must conduct active thermal wellness checks every 30 minutes.",
                priority="Mandatory",
            )
        )

    elif risk_level == OccupationalRiskLevel.CRITICAL:
        controls.append(
            RecommendedControl(
                category="Work-Rest",
                action="STOP WORK ORDER: Suspend all non-essential outdoor heavy physical labor immediately.",
                priority="Mandatory",
            )
        )
        controls.append(
            RecommendedControl(
                category="Shade/Cooling",
                action="Evacuate exposed workforce to air-conditioned shelter or emergency cooling stations.",
                priority="Mandatory",
            )
        )
        controls.append(
            RecommendedControl(
                category="Hydration",
                action="Provide chilled fluids and electrolyte solutions; initiate aggressive passive/active cooling.",
                priority="Mandatory",
            )
        )
        controls.append(
            RecommendedControl(
                category="Emergency Preparedness",
                action="Designate on-site safety lead to monitor cohort; verify rapid emergency transport readiness.",
                priority="Mandatory",
            )
        )
        controls.append(
            RecommendedControl(
                category="Monitoring",
                action="Maintain 100% continuous direct supervisory and peer surveillance.",
                priority="Mandatory",
            )
        )

    # Targeted Acclimatization Control
    if acclimatization_status in (AcclimatizationStatus.UNACCLIMATIZED, AcclimatizationStatus.MIXED):
        if risk_level in (OccupationalRiskLevel.MODERATE, OccupationalRiskLevel.HIGH, OccupationalRiskLevel.CRITICAL):
            controls.append(
                RecommendedControl(
                    category="Acclimatization",
                    action=(
                        "Cohort includes unacclimatized workers: Enforce a graduated exposure protocol "
                        "(e.g. 50% shift exposure on Day 1, ramping by 10-20% daily) and assign to lighter duties."
                    ),
                    priority="High" if risk_level == OccupationalRiskLevel.MODERATE else "Mandatory",
                )
            )

    return controls
