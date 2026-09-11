"""
b2b_compliance.py
Operational compliance, work-rest schedules, and gig-economy triggers
based on OSHA, ACGIH, and ISO 7243 occupational heat stress standards.
"""

try:
    from heatguard.thermal.risk import RiskLevel
except ImportError:
    from risk import RiskLevel

# ACGIH / OSHA standard guidelines for outdoor labor & platform ops
COMPLIANCE_MATRIX = {
    RiskLevel.LOW: {
        "flag_color": "Green",
        "hex": "#27ae60",
        "work_rest_cycle": "Continuous work (Normal supervision)",
        "rest_mins_per_hour": 0,
        "water_intake_hr": "0.5 L / hour",
        "gig_sla_adjustment": "Normal (No SLA relaxation)",
        "hazard_pay_active": False,
        "hazard_pay_multiplier": 1.0,
        "site_action": "Routine hydration reminders.",
    },
    RiskLevel.CAUTION: {
        "flag_color": "Yellow",
        "hex": "#f1c40f",
        "work_rest_cycle": "45 min work / 15 min rest",
        "rest_mins_per_hour": 15,
        "water_intake_hr": "0.75 L / hour",
        "gig_sla_adjustment": "+5 mins buffer on delivery routes",
        "hazard_pay_active": False,
        "hazard_pay_multiplier": 1.0,
        "site_action": "Set up shaded cooling zones; verify water availability.",
    },
    RiskLevel.EXTREME_CAUTION: {
        "flag_color": "Orange",
        "hex": "#e67e22",
        "work_rest_cycle": "30 min work / 30 min rest",
        "rest_mins_per_hour": 30,
        "water_intake_hr": "1.0 L / hour",
        "gig_sla_adjustment": "+10 mins buffer; auto-reroute to cooling hubs",
        "hazard_pay_active": True,
        "hazard_pay_multiplier": 1.15,
        "site_action": "Mandatory buddy system; postpone high-metabolic-rate tasks.",
    },
    RiskLevel.DANGER: {
        "flag_color": "Red",
        "hex": "#e74c3c",
        "work_rest_cycle": "15 min work / 45 min rest",
        "rest_mins_per_hour": 45,
        "water_intake_hr": "1.0 - 1.25 L / hour",
        "gig_sla_adjustment": "+20 mins buffer; pause non-essential dispatches",
        "hazard_pay_active": True,
        "hazard_pay_multiplier": 1.30,
        "site_action": "Halt heavy equipment operations outdoors; mandatory misting.",
    },
    RiskLevel.EXTREME_DANGER: {
        "flag_color": "Black",
        "hex": "#2c3e50",
        "work_rest_cycle": "STOP WORK — All outdoor labor suspended",
        "rest_mins_per_hour": 60,
        "water_intake_hr": "Emergency protocol",
        "gig_sla_adjustment": "Platform service pause / shutdown in zone",
        "hazard_pay_active": True,
        "hazard_pay_multiplier": 1.50,
        "site_action": "CRITICAL: Evacuate exposed workers to air-conditioned shelters.",
    },
}


def get_operational_advisory(risk_verdict: RiskLevel, wbgt_c: float, work_type="Heavy Labor"):
    """
    Returns structured B2B advisory data for dispatchers, safety officers,
    and platform ops managers.
    """
    profile = COMPLIANCE_MATRIX[risk_verdict]

    work_rest = profile["work_rest_cycle"]
    if "Very Heavy" in work_type and risk_verdict >= RiskLevel.EXTREME_CAUTION:
        work_rest = "15 min work / 45 min rest (Elevated exertion penalty)"

    return {
        "risk_level_str": str(risk_verdict),
        "flag_color": profile["flag_color"],
        "color_hex": profile["hex"],
        "work_rest_cycle": work_rest,
        "rest_minutes": profile["rest_mins_per_hour"],
        "hydration_target": profile["water_intake_hr"],
        "gig_sla": profile["gig_sla_adjustment"],
        "hazard_pay": profile["hazard_pay_active"],
        "surge_multiplier": f"{profile['hazard_pay_multiplier']}x" if profile["hazard_pay_active"] else "Standard",
        "site_action": profile["site_action"],
    }