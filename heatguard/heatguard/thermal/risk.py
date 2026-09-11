"""
Risk classification for heatguard.

Two independent scales are used because they answer different questions:

- Heat Index: general public heat risk (NWS scale), based on shade/indoor
  perceived temperature.
- WBGT: outdoor exertion / occupational heat stress risk (ACSM / OSHA-style
  flag system), accounts for sun, wind and humidity directly.

Both are reported, plus a single combined verdict (the more severe of the
two) for callers that just want one answer.
"""

from enum import IntEnum


class RiskLevel(IntEnum):
    """Ordered so comparisons (max/min) work directly."""
    LOW = 0
    CAUTION = 1
    EXTREME_CAUTION = 2
    DANGER = 3
    EXTREME_DANGER = 4

    def __str__(self):
        return self.name.replace("_", " ").title()


# (upper_bound_c_exclusive, level) — checked in order, first match wins.
# Values are in Celsius, converted from the standard NWS Fahrenheit table.
_HEAT_INDEX_THRESHOLDS_C = [
    (27.0, RiskLevel.LOW),
    (32.0, RiskLevel.CAUTION),
    (39.0, RiskLevel.EXTREME_CAUTION),
    (51.0, RiskLevel.DANGER),
    (float("inf"), RiskLevel.EXTREME_DANGER),
]

# ACSM/OSHA-style WBGT flag thresholds, in Celsius.
_WBGT_THRESHOLDS_C = [
    (27.8, RiskLevel.LOW),               # Green flag
    (29.4, RiskLevel.CAUTION),           # Yellow flag
    (31.1, RiskLevel.EXTREME_CAUTION),   # Orange flag
    (32.2, RiskLevel.DANGER),            # Red flag
    (float("inf"), RiskLevel.EXTREME_DANGER),  # Black flag
]


def _classify(value_c, thresholds):
    for upper_bound, level in thresholds:
        if value_c < upper_bound:
            return level
    return thresholds[-1][1]  # fallback, shouldn't be reached


def classify_heat_index(heat_index_c):
    """Classify general public heat risk from heat index (°C)."""
    return _classify(heat_index_c, _HEAT_INDEX_THRESHOLDS_C)


def classify_wbgt(wbgt_c):
    """Classify outdoor exertion heat risk from WBGT (°C)."""
    return _classify(wbgt_c, _WBGT_THRESHOLDS_C)


def calculate_risk(heat_index_c, wbgt_c):
    """
    Combine both metrics into a single risk assessment.

    Returns a dict with the individual levels and a combined "verdict"
    (the more severe of the two), so callers can either show one number
    or break it down by context (general vs. outdoor exertion).
    """
    heat_index_level = classify_heat_index(heat_index_c)
    wbgt_level = classify_wbgt(wbgt_c)
    verdict = max(heat_index_level, wbgt_level)

    return {
        "heat_index_level": heat_index_level,
        "wbgt_level": wbgt_level,
        "verdict": verdict,
    }