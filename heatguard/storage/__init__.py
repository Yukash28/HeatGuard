"""
HeatGuard Persistence and Storage package.
Provides thread-safe SQLite data access for organizations, sites,
workforce profiles, weather observations, WBGT metrics, risk assessments, and action plans.
"""

from pathlib import Path
from typing import Optional

from heatguard.storage.connection import DEFAULT_DB_PATH, DatabaseConnectionManager
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
from heatguard.storage.repository import HeatGuardRepository

_GLOBAL_REPO: Optional[HeatGuardRepository] = None


def get_repository(db_path: Optional[str | Path] = None) -> HeatGuardRepository:
    """
    Get or create a singleton repository instance for the given database path.
    If db_path is None, the default application database is used.
    """
    global _GLOBAL_REPO
    if db_path is not None:
        conn_mgr = DatabaseConnectionManager(db_path)
        return HeatGuardRepository(conn_mgr)

    if _GLOBAL_REPO is None:
        _GLOBAL_REPO = HeatGuardRepository()
    return _GLOBAL_REPO


def init_db(db_path: Optional[str | Path] = None, seed: bool = True) -> HeatGuardRepository:
    """
    Initialize database schema and seed default presets if requested.
    Returns the ready-to-use repository.
    """
    repo = get_repository(db_path)
    repo.initialize_database()
    if seed:
        repo.seed_default_presets()
    return repo


__all__ = [
    "ActionPlanRecord",
    "DatabaseConnectionManager",
    "HeatGuardRepository",
    "MigrationManager",
    "OrganizationRecord",
    "RiskAssessmentRecord",
    "SiteRecord",
    "WbgtCalculationRecord",
    "WeatherSnapshotRecord",
    "WorkforceProfileRecord",
    "get_repository",
    "init_db",
    "DEFAULT_DB_PATH",
]
