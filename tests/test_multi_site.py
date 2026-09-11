"""
Test suite for HeatGuard multi-site management and organization rollups.
"""

from pathlib import Path
import pytest

from heatguard.risk.models import OccupationalRiskLevel
from heatguard.risk.multi_site import (
    OrganizationOverview,
    SiteSummary,
    evaluate_organization_overview,
    evaluate_site_summary,
)
from heatguard.storage import DatabaseConnectionManager, HeatGuardRepository
from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    Organization,
    Site,
    WorkforceProfile,
    WorkIntensity,
    WorkType,
)


@pytest.fixture
def temp_repo(tmp_path: Path):
    """Provides a fresh repository on a temporary SQLite DB."""
    db_file = tmp_path / "test_multi_site.db"
    conn_mgr = DatabaseConnectionManager(str(db_file))
    repo = HeatGuardRepository(conn_mgr)
    repo.initialize_database()
    yield repo
    conn_mgr.close()


def mock_forecast_fetcher(latitude: float, longitude: float, **kwargs):
    """Deterministic forecast generator for multi-site tests."""
    # Vary base temperature by latitude to simulate micro-climates
    base_temp = 28.0 + (latitude - 12.0) * 2.0
    return [
        {
            "timestamp": f"2026-06-15T{hour:02d}:00:00",
            "temp_c": base_temp + (4.0 if 11 <= hour <= 15 else 0.0),
            "humidity": 65.0,
            "wind_kmh": 12.0,
            "radiation": 600.0 if 10 <= hour <= 16 else 50.0,
            "wbgt_c": 28.5 + (3.0 if 12 <= hour <= 15 else 0.0),
            "is_fallback": False,
            "data_source": "Mock Forecast Service",
        }
        for hour in range(24)
    ]


def test_abc_construction_seeding(temp_repo: HeatGuardRepository):
    """Verify ABC Construction and its 4 canonical worksites are seeded properly."""
    temp_repo.seed_default_presets()

    org = temp_repo.get_organization("org-abc")
    assert org is not None
    assert org.name == "ABC Construction"

    sites = temp_repo.list_sites(organization_id="org-abc")
    assert len(sites) == 4

    site_names = [s.name for s in sites]
    assert "Bengaluru Metro Site" in site_names
    assert "Electronic City Site" in site_names
    assert "Whitefield Site" in site_names
    assert "Outer Ring Road Site" in site_names


def test_evaluate_site_summary(temp_repo: HeatGuardRepository):
    """Verify evaluation of a single site summary."""
    temp_repo.seed_default_presets()
    metro_site = temp_repo.get_site("site-blr-metro")
    assert metro_site is not None

    wf = temp_repo.get_workforce_profile(metro_site.id)
    summary = evaluate_site_summary(metro_site, wf, forecast_fetcher=mock_forecast_fetcher)

    assert summary.site_id == "site-blr-metro"
    assert summary.name == "Bengaluru Metro Site"
    assert summary.workers == 140
    assert summary.work_type == "Construction"
    assert summary.current_wbgt > 0
    assert summary.peak_wbgt >= summary.current_wbgt
    assert isinstance(summary.current_risk_level, OccupationalRiskLevel)
    assert isinstance(summary.peak_risk_level, OccupationalRiskLevel)
    assert len(summary.peak_risk_period) > 0


def test_evaluate_organization_overview_kpis(temp_repo: HeatGuardRepository):
    """
    Verify organization overview computes:
    - TOTAL SITES
    - TOTAL WORKERS
    - HIGH-RISK SITES
    - CRITICAL SITES
    """
    temp_repo.seed_default_presets()

    overview = evaluate_organization_overview(
        repo=temp_repo,
        org_id="org-abc",
        forecast_fetcher=mock_forecast_fetcher,
    )

    assert overview.org_id == "org-abc"
    assert overview.org_name == "ABC Construction"
    assert overview.total_sites == 4
    # Workers: 140 + 95 + 110 + 165 = 510
    assert overview.total_workers == 510

    # Ensure risk categorization exists
    total_categorized = (
        overview.low_risk_sites_count
        + overview.moderate_risk_sites_count
        + overview.high_risk_sites_count
        + overview.critical_risk_sites_count
    )
    assert total_categorized == 4
    assert len(overview.sites) == 4

    # Every site must have the required fields
    for s in overview.sites:
        assert s.location_str != ""
        assert s.workers > 0
        assert s.work_type != ""
        assert s.current_wbgt > 0
        assert s.peak_wbgt > 0
        assert s.current_risk_level in (
            OccupationalRiskLevel.LOW,
            OccupationalRiskLevel.MODERATE,
            OccupationalRiskLevel.HIGH,
            OccupationalRiskLevel.CRITICAL,
        )
        assert s.peak_risk_period != ""
