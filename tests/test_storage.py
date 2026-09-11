"""
Test suite for HeatGuard SQLite persistence layer.
Covers database initialization, migrations, CRUD operations, relationships,
cascading deletes, batch operations, and application reload simulation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import pytest

from heatguard.risk.models import OccupationalRiskLevel, RecommendedControl, RiskAssessmentResult, RiskFactor
from heatguard.storage import (
    ActionPlanRecord,
    DatabaseConnectionManager,
    HeatGuardRepository,
    MigrationManager,
    OrganizationRecord,
    RiskAssessmentRecord,
    SiteRecord,
    WbgtCalculationRecord,
    WeatherSnapshotRecord,
    WorkforceProfileRecord,
    get_repository,
    init_db,
)
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
def temp_db_path(tmp_path: Path):
    """Provides a temporary file-based SQLite database path."""
    db_file = tmp_path / "test_heatguard.db"
    return str(db_file)


@pytest.fixture
def repo(temp_db_path: str):
    """Initializes and yields a clean repository on a temporary SQLite database."""
    conn_mgr = DatabaseConnectionManager(temp_db_path)
    repository = HeatGuardRepository(conn_mgr)
    repository.initialize_database()
    yield repository
    conn_mgr.close()


def test_database_initialization_and_migrations(temp_db_path: str):
    """Verify migration table creation and idempotent versioning."""
    conn_mgr = DatabaseConnectionManager(temp_db_path)
    migration_mgr = MigrationManager(conn_mgr)

    # Initially version 0
    assert migration_mgr.get_current_version() == 0
    assert migration_mgr.get_applied_versions() == []

    # Run migrations
    applied = migration_mgr.run_migrations()
    assert applied == [1]
    assert migration_mgr.get_current_version() == 1
    assert migration_mgr.get_applied_versions() == [1]

    # Running migrations again is idempotent
    second_run = migration_mgr.run_migrations()
    assert second_run == []
    assert migration_mgr.get_current_version() == 1

    conn_mgr.close()


def test_organization_crud(repo: HeatGuardRepository):
    """Verify organization save, get, list, update, and delete."""
    org = Organization(id="org-infra-01", name="Infrastructure Corp")
    saved = repo.save_organization(org)
    assert saved.id == "org-infra-01"
    assert saved.name == "Infrastructure Corp"

    # Get by ID
    fetched = repo.get_organization("org-infra-01")
    assert fetched is not None
    assert fetched.name == "Infrastructure Corp"

    # Update name
    updated_org = Organization(id="org-infra-01", name="Infrastructure Global Corp")
    repo.save_organization(updated_org)
    fetched_updated = repo.get_organization("org-infra-01")
    assert fetched_updated is not None
    assert fetched_updated.name == "Infrastructure Global Corp"

    # List
    all_orgs = repo.list_organizations()
    assert len(all_orgs) == 1
    assert all_orgs[0].id == "org-infra-01"

    # Delete
    deleted = repo.delete_organization("org-infra-01")
    assert deleted is True
    assert repo.get_organization("org-infra-01") is None


def test_site_crud(repo: HeatGuardRepository):
    """Verify site creation, retrieval by id and name, and listing."""
    org = Organization(id="org-infra", name="Civil Works")
    repo.save_organization(org)

    site = Site(
        id="site-metro-01",
        organization_id=org.id,
        name="Metro Phase 3",
        latitude=12.9237,
        longitude=77.6833,
        timezone="Asia/Kolkata",
    )
    saved = repo.save_site(site)
    assert saved.id == "site-metro-01"
    assert saved.name == "Metro Phase 3"
    assert pytest.approx(saved.latitude) == 12.9237
    assert pytest.approx(saved.longitude) == 77.6833

    # Fetch by ID
    by_id = repo.get_site("site-metro-01")
    assert by_id is not None
    assert by_id.name == "Metro Phase 3"
    domain_site = by_id.to_domain()
    assert domain_site.id == site.id
    assert domain_site.latitude == site.latitude

    # Fetch by Name
    by_name = repo.get_site_by_name("Metro Phase 3")
    assert by_name is not None
    assert by_name.id == "site-metro-01"

    # List sites
    sites = repo.list_sites(organization_id=org.id)
    assert len(sites) == 1
    assert sites[0].id == "site-metro-01"

    # Delete site
    assert repo.delete_site("site-metro-01") is True
    assert repo.get_site("site-metro-01") is None


def test_workforce_profile_crud(repo: HeatGuardRepository):
    """Verify saving, updating, and querying workforce profile attributes."""
    org = Organization(id="org-infra", name="Civil Works")
    repo.save_organization(org)

    site = Site(
        id="site-metro-01",
        organization_id=org.id,
        name="Metro Phase 3",
        latitude=12.9237,
        longitude=77.6833,
    )
    repo.save_site(site)

    wf = WorkforceProfile(
        id="wf-metro-01",
        site_id=site.id,
        number_of_workers=140,
        work_type=WorkType.CONSTRUCTION,
        work_intensity=WorkIntensity.HEAVY,
        shift_start="07:30",
        shift_end="16:30",
        clothing_or_ppe=ClothingPPE.HI_VIS_VEST_HELMET.value,
        acclimatization_status=AcclimatizationStatus.MIXED,
    )
    saved_wf = repo.save_workforce_profile(wf)
    assert saved_wf.workers == 140
    assert saved_wf.work_type == "Construction"
    assert saved_wf.work_intensity == "Heavy"

    # Retrieve by site_id
    retrieved = repo.get_workforce_profile(site.id)
    assert retrieved is not None
    assert retrieved.id == "wf-metro-01"
    assert retrieved.workers == 140
    assert retrieved.shift_start == "07:30"
    assert retrieved.shift_end == "16:30"

    # Convert to domain
    wf_domain = retrieved.to_domain()
    assert wf_domain.number_of_workers == 140
    assert wf_domain.work_type == WorkType.CONSTRUCTION
    assert wf_domain.is_shift_active(10) is True
    assert wf_domain.is_shift_active(20) is False

    # Update profile
    wf_updated = WorkforceProfile(
        id="wf-metro-01",
        site_id=site.id,
        number_of_workers=180,
        work_type=WorkType.CONSTRUCTION,
        work_intensity=WorkIntensity.HEAVY,
        shift_start="06:00",
        shift_end="14:00",
        clothing_or_ppe=ClothingPPE.HI_VIS_VEST_HELMET.value,
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    repo.save_workforce_profile(wf_updated)
    retrieved_updated = repo.get_workforce_profile(site.id)
    assert retrieved_updated is not None
    assert retrieved_updated.workers == 180
    assert retrieved_updated.shift_start == "06:00"
    assert retrieved_updated.acclimatization == "Acclimatized"


def test_weather_and_wbgt_batch_operations(repo: HeatGuardRepository):
    """Verify batch insert and retrieval of weather observations and WBGT calculations."""
    org = Organization(id="org-infra", name="Civil Works")
    repo.save_organization(org)
    site = Site(id="site-blr", organization_id=org.id, name="Bengaluru Hub", latitude=12.97, longitude=77.59)
    repo.save_site(site)

    # Weather snapshots
    snapshots = [
        WeatherSnapshotRecord(
            id=f"ws-{i}",
            site_id=site.id,
            timestamp=f"2026-06-15T{i:02d}:00:00",
            temperature_c=25.0 + i,
            relative_humidity=60.0 - i,
            wind_speed_kmh=12.0,
            solar_radiation=200.0 * i,
        )
        for i in range(5)
    ]
    inserted_ws = repo.save_weather_snapshots_batch(snapshots)
    assert inserted_ws == 5

    stored_ws = repo.get_weather_snapshots(site.id, limit=3)
    assert len(stored_ws) == 3
    # Ordered descending by timestamp
    assert stored_ws[0].timestamp == "2026-06-15T04:00:00"

    # WBGT calculations
    wbgt_calcs = [
        WbgtCalculationRecord(
            id=f"wbgt-{i}",
            site_id=site.id,
            timestamp=f"2026-06-15T{i:02d}:00:00",
            wbgt_c=22.0 + (i * 1.5),
            effective_wbgt_c=24.0 + (i * 1.5),
            heat_index_c=26.0 + i,
        )
        for i in range(5)
    ]
    inserted_wbgt = repo.save_wbgt_calculations_batch(wbgt_calcs)
    assert inserted_wbgt == 5

    stored_wbgt = repo.get_wbgt_calculations(site.id, limit=10)
    assert len(stored_wbgt) == 5
    assert pytest.approx(stored_wbgt[0].effective_wbgt_c) == 30.0


def test_risk_assessment_and_action_plan_persistence(repo: HeatGuardRepository):
    """Verify saving risk assessment outcomes and action plan protocols."""
    org = Organization(id="org-infra", name="Civil Works")
    repo.save_organization(org)
    site = Site(id="site-blr", organization_id=org.id, name="Bengaluru Hub", latitude=12.97, longitude=77.59)
    repo.save_site(site)

    # Risk Assessment
    risk_rec = RiskAssessmentRecord(
        id="risk-001",
        site_id=site.id,
        timestamp="2026-06-15T14:00:00",
        wbgt=31.2,
        risk_level=OccupationalRiskLevel.HIGH.value,
        risk_score=78.5,
        explanation="High metabolic load combined with ambient WBGT 31.2°C exceeds threshold.",
    )
    repo.save_risk_assessment(risk_rec)

    latest_risk = repo.get_latest_risk_assessment(site.id)
    assert latest_risk is not None
    assert latest_risk.wbgt == 31.2
    assert latest_risk.risk_level == "HIGH"
    assert latest_risk.risk_score == 78.5
    assert "exceeds threshold" in latest_risk.explanation

    # Action Plan
    controls = [
        {"category": "Hydration", "action": "Enforce 250mL cool water every 20 mins", "priority": "Mandatory"},
        {"category": "Work/Rest", "action": "Implement 30m work / 30m rest cycle", "priority": "High"},
    ]
    plan = ActionPlanRecord(
        id="plan-001",
        site_id=site.id,
        timestamp="2026-06-15T14:00:00",
        risk_tier="HIGH",
        peak_period="12:00 – 15:00",
        action_summary="Mandatory heat controls for 120 workers.",
        controls_json=json.dumps(controls),
    )
    repo.save_action_plan(plan)

    latest_plan = repo.get_latest_action_plan(site.id)
    assert latest_plan is not None
    assert latest_plan.risk_tier == "HIGH"
    assert latest_plan.peak_period == "12:00 – 15:00"
    assert len(latest_plan.controls_list) == 2
    assert latest_plan.controls_list[0]["category"] == "Hydration"


def test_seed_default_presets(repo: HeatGuardRepository):
    """Verify seeding default sites and workforce profiles into an empty database."""
    # Ensure empty
    assert repo.list_sites() == []

    # Seed
    repo.seed_default_presets()
    sites = repo.list_sites()
    assert len(sites) == 4

    site_names = [s.name for s in sites]
    assert "Bengaluru Metro Site" in site_names
    assert "Electronic City Site" in site_names
    assert "Whitefield Site" in site_names
    assert "Outer Ring Road Site" in site_names

    # Check that workforce profiles were also seeded
    metro_site = repo.get_site_by_name("Bengaluru Metro Site")
    assert metro_site is not None
    metro_wf = repo.get_workforce_profile(metro_site.id)
    assert metro_wf is not None
    assert metro_wf.workers == 140
    assert metro_wf.work_intensity == "Heavy"

    # Seeding again without force does not duplicate
    repo.seed_default_presets()
    assert len(repo.list_sites()) == 4


def test_cascade_delete_integrity(repo: HeatGuardRepository):
    """Verify SQLite foreign key cascading deletion."""
    org = Organization(id="org-test-cascade", name="Test Org")
    repo.save_organization(org)

    site = Site(
        id="site-test-cascade",
        organization_id=org.id,
        name="Temporary Facility",
        latitude=13.0,
        longitude=77.0,
    )
    repo.save_site(site)

    wf = WorkforceProfile(
        id="wf-test-cascade",
        site_id=site.id,
        number_of_workers=50,
        work_type=WorkType.UTILITIES,
        work_intensity=WorkIntensity.LIGHT,
        shift_start="08:00",
        shift_end="16:00",
        clothing_or_ppe="Standard",
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    repo.save_workforce_profile(wf)

    # Deleting site cascades to workforce profile
    assert repo.delete_site(site.id) is True
    assert repo.get_site(site.id) is None
    assert repo.get_workforce_profile(site.id) is None


def test_site_reload_simulation_after_restart(temp_db_path: str):
    """
    Simulate application restart:
    1. Instance A saves custom sites and modified workforce profiles.
    2. Instance A closes.
    3. Instance B initializes from the same SQLite file and must reload all saved sites and profiles.
    """
    conn_mgr_a = DatabaseConnectionManager(temp_db_path)
    repo_a = HeatGuardRepository(conn_mgr_a)
    repo_a.initialize_database()

    org = Organization(id="org-solar", name="Renewable Power Corp")
    repo_a.save_organization(org)

    custom_site = Site(
        id="site-mysuru-solar",
        organization_id=org.id,
        name="Mysuru Solar Array Alpha",
        latitude=12.2958,
        longitude=76.6394,
    )
    repo_a.save_site(custom_site)

    custom_wf = WorkforceProfile(
        id="wf-mysuru-solar",
        site_id=custom_site.id,
        number_of_workers=95,
        work_type=WorkType.UTILITIES,
        work_intensity=WorkIntensity.HEAVY,
        shift_start="06:30",
        shift_end="15:30",
        clothing_or_ppe=ClothingPPE.HI_VIS_VEST_HELMET.value,
        acclimatization_status=AcclimatizationStatus.UNACCLIMATIZED,
    )
    repo_a.save_workforce_profile(custom_wf)

    # Close instance A (app shutdown)
    conn_mgr_a.close()

    # Launch instance B (app restart)
    conn_mgr_b = DatabaseConnectionManager(temp_db_path)
    repo_b = HeatGuardRepository(conn_mgr_b)
    repo_b.initialize_database()

    # Verify site was reloaded
    reloaded_sites = repo_b.list_sites()
    assert any(s.id == "site-mysuru-solar" for s in reloaded_sites)

    reloaded_site = repo_b.get_site("site-mysuru-solar")
    assert reloaded_site is not None
    assert reloaded_site.name == "Mysuru Solar Array Alpha"
    assert pytest.approx(reloaded_site.latitude) == 12.2958
    assert pytest.approx(reloaded_site.longitude) == 76.6394

    # Verify workforce profile was reloaded
    reloaded_wf = repo_b.get_workforce_profile("site-mysuru-solar")
    assert reloaded_wf is not None
    assert reloaded_wf.workers == 95
    assert reloaded_wf.shift_start == "06:30"
    assert reloaded_wf.shift_end == "15:30"
    assert reloaded_wf.acclimatization == "Unacclimatized"

    conn_mgr_b.close()


def test_worker_privacy_guarantee(repo: HeatGuardRepository):
    """
    Verify schema compliance: workforce table contains ONLY aggregated cohort parameters
    and absolutely NO personal identifiable information (no names, worker IDs, health records).
    """
    with repo.conn_mgr.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(workforce_profiles);")
        columns = [row["name"] for row in cur.fetchall()]

    allowed_columns = {
        "id",
        "site_id",
        "workers",
        "work_type",
        "work_intensity",
        "ppe",
        "acclimatization",
        "shift_start",
        "shift_end",
        "updated_at",
    }
    assert set(columns) == allowed_columns
    assert "worker_name" not in columns
    assert "email" not in columns
    assert "ssn" not in columns
    assert "medical_history" not in columns
