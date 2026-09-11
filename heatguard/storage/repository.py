"""
Repository layer providing clean CRUD and query interfaces for HeatGuard SQLite persistence.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from heatguard.risk.models import RiskAssessmentResult
from heatguard.storage.connection import DatabaseConnectionManager
from heatguard.storage.migrations import MigrationManager
from heatguard.storage.models import (
    ActionPlanRecord,
    OrganizationRecord,
    RiskAssessmentRecord,
    SiteRecord,
    WbgtCalculationRecord,
    WeatherSnapshotRecord,
    WorkforceProfileRecord,
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

logger = logging.getLogger(__name__)


class HeatGuardRepository:
    """Repository handling all database operations for HeatGuard."""

    def __init__(self, connection_manager: Optional[DatabaseConnectionManager] = None):
        self.conn_mgr = connection_manager or DatabaseConnectionManager()
        self.migration_mgr = MigrationManager(self.conn_mgr)

    def initialize_database(self) -> List[int]:
        """Run all pending schema migrations."""
        return self.migration_mgr.run_migrations()

    # =========================================================================
    # Organization CRUD
    # =========================================================================

    def save_organization(self, org: Organization | OrganizationRecord) -> OrganizationRecord:
        """Insert or update an organization."""
        record = org if isinstance(org, OrganizationRecord) else OrganizationRecord.from_domain(org)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO organizations (id, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name;
                """,
                (record.id, record.name, record.created_at or now_iso),
            )
            conn.commit()

        return record

    def get_organization(self, org_id: str) -> Optional[OrganizationRecord]:
        """Fetch organization by id."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, created_at FROM organizations WHERE id = ?;", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return OrganizationRecord(id=row["id"], name=row["name"], created_at=row["created_at"])

    def list_organizations(self) -> List[OrganizationRecord]:
        """List all organizations ordered by name."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, created_at FROM organizations ORDER BY name ASC;")
            return [
                OrganizationRecord(id=r["id"], name=r["name"], created_at=r["created_at"])
                for r in cur.fetchall()
            ]

    def delete_organization(self, org_id: str) -> bool:
        """Delete an organization and cascade delete its sites."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM organizations WHERE id = ?;", (org_id,))
            conn.commit()
            return cur.rowcount > 0

    # =========================================================================
    # Site CRUD
    # =========================================================================

    def save_site(self, site: Site | SiteRecord) -> SiteRecord:
        """Insert or update a site."""
        record = site if isinstance(site, SiteRecord) else SiteRecord.from_domain(site)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO sites (id, organization_id, name, latitude, longitude, timezone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    organization_id = excluded.organization_id,
                    name = excluded.name,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    timezone = excluded.timezone,
                    updated_at = excluded.updated_at;
                """,
                (
                    record.id,
                    record.organization_id,
                    record.name,
                    float(record.latitude),
                    float(record.longitude),
                    record.timezone,
                    record.created_at or now_iso,
                    now_iso,
                ),
            )
            conn.commit()

        record.updated_at = now_iso
        return record

    def get_site(self, site_id: str) -> Optional[SiteRecord]:
        """Fetch a site by its unique ID."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, organization_id, name, latitude, longitude, timezone, created_at, updated_at
                FROM sites WHERE id = ?;
                """,
                (site_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return SiteRecord(
                id=row["id"],
                organization_id=row["organization_id"],
                name=row["name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timezone=row["timezone"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_site_by_name(self, name: str) -> Optional[SiteRecord]:
        """Fetch a site by its display name."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, organization_id, name, latitude, longitude, timezone, created_at, updated_at
                FROM sites WHERE name = ?;
                """,
                (name,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return SiteRecord(
                id=row["id"],
                organization_id=row["organization_id"],
                name=row["name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timezone=row["timezone"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_sites(self, organization_id: Optional[str] = None) -> List[SiteRecord]:
        """List all sites, optionally filtered by organization."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            if organization_id:
                cur.execute(
                    """
                    SELECT id, organization_id, name, latitude, longitude, timezone, created_at, updated_at
                    FROM sites WHERE organization_id = ? ORDER BY name ASC;
                    """,
                    (organization_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, organization_id, name, latitude, longitude, timezone, created_at, updated_at
                    FROM sites ORDER BY name ASC;
                    """
                )

            return [
                SiteRecord(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    name=r["name"],
                    latitude=float(r["latitude"]),
                    longitude=float(r["longitude"]),
                    timezone=r["timezone"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in cur.fetchall()
            ]

    def delete_site(self, site_id: str) -> bool:
        """Delete a site by ID and cascade delete related records."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM sites WHERE id = ?;", (site_id,))
            conn.commit()
            return cur.rowcount > 0

    # =========================================================================
    # WorkforceProfile CRUD
    # =========================================================================

    def save_workforce_profile(
        self, profile: WorkforceProfile | WorkforceProfileRecord
    ) -> WorkforceProfileRecord:
        """Insert or update a workforce profile for a site."""
        record = (
            profile
            if isinstance(profile, WorkforceProfileRecord)
            else WorkforceProfileRecord.from_domain(profile)
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO workforce_profiles (
                    id, site_id, workers, work_type, work_intensity, ppe, acclimatization, shift_start, shift_end, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    site_id = excluded.site_id,
                    workers = excluded.workers,
                    work_type = excluded.work_type,
                    work_intensity = excluded.work_intensity,
                    ppe = excluded.ppe,
                    acclimatization = excluded.acclimatization,
                    shift_start = excluded.shift_start,
                    shift_end = excluded.shift_end,
                    updated_at = excluded.updated_at;
                """,
                (
                    record.id,
                    record.site_id,
                    int(record.workers),
                    record.work_type,
                    record.work_intensity,
                    record.ppe,
                    record.acclimatization,
                    record.shift_start,
                    record.shift_end,
                    now_iso,
                ),
            )
            conn.commit()

        record.updated_at = now_iso
        return record

    def get_workforce_profile(self, site_id: str) -> Optional[WorkforceProfileRecord]:
        """Fetch the workforce profile assigned to a given site."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, workers, work_type, work_intensity, ppe, acclimatization, shift_start, shift_end, updated_at
                FROM workforce_profiles WHERE site_id = ? ORDER BY updated_at DESC LIMIT 1;
                """,
                (site_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return WorkforceProfileRecord(
                id=row["id"],
                site_id=row["site_id"],
                workers=int(row["workers"]),
                work_type=row["work_type"],
                work_intensity=row["work_intensity"],
                ppe=row["ppe"],
                acclimatization=row["acclimatization"],
                shift_start=row["shift_start"],
                shift_end=row["shift_end"],
                updated_at=row["updated_at"],
            )

    def get_workforce_profile_by_id(self, profile_id: str) -> Optional[WorkforceProfileRecord]:
        """Fetch workforce profile by primary key."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, workers, work_type, work_intensity, ppe, acclimatization, shift_start, shift_end, updated_at
                FROM workforce_profiles WHERE id = ?;
                """,
                (profile_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return WorkforceProfileRecord(
                id=row["id"],
                site_id=row["site_id"],
                workers=int(row["workers"]),
                work_type=row["work_type"],
                work_intensity=row["work_intensity"],
                ppe=row["ppe"],
                acclimatization=row["acclimatization"],
                shift_start=row["shift_start"],
                shift_end=row["shift_end"],
                updated_at=row["updated_at"],
            )

    def list_workforce_profiles(self) -> List[WorkforceProfileRecord]:
        """List all workforce profiles."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, workers, work_type, work_intensity, ppe, acclimatization, shift_start, shift_end, updated_at
                FROM workforce_profiles ORDER BY updated_at DESC;
                """
            )
            return [
                WorkforceProfileRecord(
                    id=r["id"],
                    site_id=r["site_id"],
                    workers=int(r["workers"]),
                    work_type=r["work_type"],
                    work_intensity=r["work_intensity"],
                    ppe=r["ppe"],
                    acclimatization=r["acclimatization"],
                    shift_start=r["shift_start"],
                    shift_end=r["shift_end"],
                    updated_at=r["updated_at"],
                )
                for r in cur.fetchall()
            ]

    # =========================================================================
    # Weather Snapshots
    # =========================================================================

    def save_weather_snapshot(self, record: WeatherSnapshotRecord) -> WeatherSnapshotRecord:
        """Insert a single weather snapshot."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO weather_snapshots (
                    id, site_id, timestamp, temperature_c, relative_humidity, wind_speed_kmh, solar_radiation, data_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.id,
                    record.site_id,
                    record.timestamp,
                    float(record.temperature_c),
                    float(record.relative_humidity),
                    float(record.wind_speed_kmh),
                    float(record.solar_radiation),
                    record.data_source,
                    record.created_at or now_iso,
                ),
            )
            conn.commit()
        return record

    def save_weather_snapshots_batch(self, records: List[WeatherSnapshotRecord]) -> int:
        """Batch insert weather snapshots."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT OR REPLACE INTO weather_snapshots (
                    id, site_id, timestamp, temperature_c, relative_humidity, wind_speed_kmh, solar_radiation, data_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        r.id,
                        r.site_id,
                        r.timestamp,
                        float(r.temperature_c),
                        float(r.relative_humidity),
                        float(r.wind_speed_kmh),
                        float(r.solar_radiation),
                        r.data_source,
                        r.created_at or now_iso,
                    )
                    for r in records
                ],
            )
            conn.commit()
            return len(records)

    def get_weather_snapshots(self, site_id: str, limit: int = 24) -> List[WeatherSnapshotRecord]:
        """Fetch recent weather snapshots for a site."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, timestamp, temperature_c, relative_humidity, wind_speed_kmh, solar_radiation, data_source, created_at
                FROM weather_snapshots
                WHERE site_id = ?
                ORDER BY timestamp DESC
                LIMIT ?;
                """,
                (site_id, limit),
            )
            return [
                WeatherSnapshotRecord(
                    id=r["id"],
                    site_id=r["site_id"],
                    timestamp=r["timestamp"],
                    temperature_c=float(r["temperature_c"]),
                    relative_humidity=float(r["relative_humidity"]),
                    wind_speed_kmh=float(r["wind_speed_kmh"]),
                    solar_radiation=float(r["solar_radiation"]),
                    data_source=r["data_source"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    # =========================================================================
    # WBGT Calculations
    # =========================================================================

    def save_wbgt_calculation(self, calc: WbgtCalculationRecord) -> WbgtCalculationRecord:
        """Insert a single WBGT calculation record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO wbgt_calculations (
                    id, site_id, timestamp, wbgt_c, effective_wbgt_c, heat_index_c, method, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    calc.id,
                    calc.site_id,
                    calc.timestamp,
                    float(calc.wbgt_c),
                    float(calc.effective_wbgt_c),
                    float(calc.heat_index_c),
                    calc.method,
                    calc.created_at or now_iso,
                ),
            )
            conn.commit()
        return calc

    def save_wbgt_calculations_batch(self, calcs: List[WbgtCalculationRecord]) -> int:
        """Batch insert WBGT calculation records."""
        if not calcs:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT OR REPLACE INTO wbgt_calculations (
                    id, site_id, timestamp, wbgt_c, effective_wbgt_c, heat_index_c, method, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        c.id,
                        c.site_id,
                        c.timestamp,
                        float(c.wbgt_c),
                        float(c.effective_wbgt_c),
                        float(c.heat_index_c),
                        c.method,
                        c.created_at or now_iso,
                    )
                    for c in calcs
                ],
            )
            conn.commit()
            return len(calcs)

    def get_wbgt_calculations(self, site_id: str, limit: int = 24) -> List[WbgtCalculationRecord]:
        """Fetch recent WBGT calculations for a site."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, timestamp, wbgt_c, effective_wbgt_c, heat_index_c, method, created_at
                FROM wbgt_calculations
                WHERE site_id = ?
                ORDER BY timestamp DESC
                LIMIT ?;
                """,
                (site_id, limit),
            )
            return [
                WbgtCalculationRecord(
                    id=r["id"],
                    site_id=r["site_id"],
                    timestamp=r["timestamp"],
                    wbgt_c=float(r["wbgt_c"]),
                    effective_wbgt_c=float(r["effective_wbgt_c"]),
                    heat_index_c=float(r["heat_index_c"]),
                    method=r["method"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    # =========================================================================
    # Risk Assessments
    # =========================================================================

    def save_risk_assessment(self, record: RiskAssessmentRecord) -> RiskAssessmentRecord:
        """Insert or update a risk assessment record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO risk_assessments (
                    id, site_id, timestamp, wbgt, risk_level, risk_score, explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.id,
                    record.site_id,
                    record.timestamp,
                    float(record.wbgt),
                    record.risk_level,
                    float(record.risk_score),
                    record.explanation,
                    record.created_at or now_iso,
                ),
            )
            conn.commit()
        return record

    def save_risk_assessments_batch(self, assessments: List[RiskAssessmentRecord]) -> int:
        """Batch insert risk assessment records."""
        if not assessments:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT OR REPLACE INTO risk_assessments (
                    id, site_id, timestamp, wbgt, risk_level, risk_score, explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        a.id,
                        a.site_id,
                        a.timestamp,
                        float(a.wbgt),
                        a.risk_level,
                        float(a.risk_score),
                        a.explanation,
                        a.created_at or now_iso,
                    )
                    for a in assessments
                ],
            )
            conn.commit()
            return len(assessments)

    def get_risk_assessments(self, site_id: str, limit: int = 24) -> List[RiskAssessmentRecord]:
        """Fetch recent risk assessments for a site."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, timestamp, wbgt, risk_level, risk_score, explanation, created_at
                FROM risk_assessments
                WHERE site_id = ?
                ORDER BY timestamp DESC
                LIMIT ?;
                """,
                (site_id, limit),
            )
            return [
                RiskAssessmentRecord(
                    id=r["id"],
                    site_id=r["site_id"],
                    timestamp=r["timestamp"],
                    wbgt=float(r["wbgt"]),
                    risk_level=r["risk_level"],
                    risk_score=float(r["risk_score"]),
                    explanation=r["explanation"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    def get_latest_risk_assessment(self, site_id: str) -> Optional[RiskAssessmentRecord]:
        """Fetch the most recent risk assessment for a site."""
        records = self.get_risk_assessments(site_id, limit=1)
        return records[0] if records else None

    # =========================================================================
    # Action Plans
    # =========================================================================

    def save_action_plan(self, plan: ActionPlanRecord) -> ActionPlanRecord:
        """Insert or update an action plan record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO action_plans (
                    id, site_id, timestamp, risk_tier, peak_period, action_summary, controls_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    plan.id,
                    plan.site_id,
                    plan.timestamp,
                    plan.risk_tier,
                    plan.peak_period,
                    plan.action_summary,
                    plan.controls_json,
                    plan.created_at or now_iso,
                ),
            )
            conn.commit()
        return plan

    def get_latest_action_plan(self, site_id: str) -> Optional[ActionPlanRecord]:
        """Fetch the latest action plan for a site."""
        plans = self.list_action_plans(site_id, limit=1)
        return plans[0] if plans else None

    def list_action_plans(self, site_id: str, limit: int = 10) -> List[ActionPlanRecord]:
        """Fetch action plans for a site ordered by creation date."""
        with self.conn_mgr.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, site_id, timestamp, risk_tier, peak_period, action_summary, controls_json, created_at
                FROM action_plans
                WHERE site_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (site_id, limit),
            )
            return [
                ActionPlanRecord(
                    id=r["id"],
                    site_id=r["site_id"],
                    timestamp=r["timestamp"],
                    risk_tier=r["risk_tier"],
                    peak_period=r["peak_period"],
                    action_summary=r["action_summary"],
                    controls_json=r["controls_json"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    # =========================================================================
    # Seeding Default Presets
    # =========================================================================

    def seed_default_presets(self, org_id: str = "org-abc", force: bool = False) -> None:
        """
        Preload ABC Construction and its canonical worksites into SQLite.
        Guarantees presence of multi-site demonstration sites.
        """
        existing_org = self.get_organization(org_id)
        if existing_org and not force:
            logger.debug("Organization %s already exists. Skipping seed.", org_id)
            return

        # Create ABC Construction organization
        org = Organization(id=org_id, name="ABC Construction")
        self.save_organization(org)

        presets = [
            {
                "id": "site-blr-metro",
                "name": "Bengaluru Metro Site",
                "coords": (12.9716, 77.5946),
                "workers": 140,
                "work_type": WorkType.CONSTRUCTION,
                "intensity": WorkIntensity.HEAVY,
                "acclimatization": AcclimatizationStatus.MIXED,
                "shift": ("08:00", "17:00"),
                "ppe": ClothingPPE.HI_VIS_VEST_HELMET.value,
            },
            {
                "id": "site-ecity",
                "name": "Electronic City Site",
                "coords": (12.8452, 77.6602),
                "workers": 95,
                "work_type": WorkType.UTILITIES,
                "intensity": WorkIntensity.MODERATE,
                "acclimatization": AcclimatizationStatus.ACCLIMATIZED,
                "shift": ("08:30", "17:30"),
                "ppe": ClothingPPE.STANDARD_WORKWEAR.value,
            },
            {
                "id": "site-whitefield",
                "name": "Whitefield Site",
                "coords": (12.9698, 77.7499),
                "workers": 110,
                "work_type": WorkType.WAREHOUSE_LOGISTICS,
                "intensity": WorkIntensity.MODERATE,
                "acclimatization": AcclimatizationStatus.ACCLIMATIZED,
                "shift": ("07:00", "16:00"),
                "ppe": ClothingPPE.STANDARD_WORKWEAR.value,
            },
            {
                "id": "site-orr",
                "name": "Outer Ring Road Site",
                "coords": (12.9237, 77.6833),
                "workers": 165,
                "work_type": WorkType.ROAD_HIGHWAY,
                "intensity": WorkIntensity.HEAVY,
                "acclimatization": AcclimatizationStatus.MIXED,
                "shift": ("08:00", "17:00"),
                "ppe": ClothingPPE.HI_VIS_VEST_HELMET.value,
            },
        ]

        for p in presets:
            site = Site(
                id=p["id"],
                organization_id=org_id,
                name=p["name"],
                latitude=p["coords"][0],
                longitude=p["coords"][1],
                timezone="Asia/Kolkata",
            )
            self.save_site(site)

            wf = WorkforceProfile(
                id=f"wf-{p['id']}",
                site_id=site.id,
                number_of_workers=p["workers"],
                work_type=p["work_type"],
                work_intensity=p["intensity"],
                shift_start=p["shift"][0],
                shift_end=p["shift"][1],
                clothing_or_ppe=p["ppe"],
                acclimatization_status=p["acclimatization"],
            )
            self.save_workforce_profile(wf)

        logger.info("Successfully seeded %d worksites for ABC Construction.", len(presets))


