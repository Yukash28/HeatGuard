"""Integration and package verification tests for HeatGuard."""

import pytest
from heatguard.thermal.heat_index import calculate_heat_index
from heatguard.thermal.risk import RiskLevel, calculate_risk
from heatguard.thermal.b2b_compliance import get_operational_advisory
from heatguard.thermal.wbgt import calculate_wbgt


def test_package_exports():
    """Verify core thermal engine functions can be imported from root package."""
    assert callable(calculate_heat_index)
    assert callable(calculate_risk)
    assert callable(calculate_wbgt)
    assert callable(get_operational_advisory)


def test_b2b_advisory_generation():
    """Verify B2B advisory correctly handles risk verdict."""
    advisory = get_operational_advisory(RiskLevel.DANGER, 31.8, work_type="Heavy Labor")
    assert advisory["flag_color"] == "Red"
    assert advisory["rest_minutes"] == 45
    assert advisory["hazard_pay"] is True
