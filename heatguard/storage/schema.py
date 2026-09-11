"""
Database schemas, DDL definitions, and migration scripts for HeatGuard.
"""

from typing import Dict, List

# Migration 1: Initial schema
MIGRATION_1_UP: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL,
        description TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sites (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS workforce_profiles (
        id TEXT PRIMARY KEY,
        site_id TEXT NOT NULL,
        workers INTEGER NOT NULL,
        work_type TEXT NOT NULL,
        work_intensity TEXT NOT NULL,
        ppe TEXT NOT NULL,
        acclimatization TEXT NOT NULL,
        shift_start TEXT NOT NULL,
        shift_end TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS weather_snapshots (
        id TEXT PRIMARY KEY,
        site_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        temperature_c REAL NOT NULL,
        relative_humidity REAL NOT NULL,
        wind_speed_kmh REAL NOT NULL,
        solar_radiation REAL NOT NULL DEFAULT 0.0,
        data_source TEXT NOT NULL DEFAULT 'Open-Meteo',
        created_at TEXT NOT NULL,
        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS wbgt_calculations (
        id TEXT PRIMARY KEY,
        site_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        wbgt_c REAL NOT NULL,
        effective_wbgt_c REAL NOT NULL,
        heat_index_c REAL NOT NULL,
        method TEXT NOT NULL DEFAULT 'Liljegren',
        created_at TEXT NOT NULL,
        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_assessments (
        id TEXT PRIMARY KEY,
        site_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        wbgt REAL NOT NULL,
        risk_level TEXT NOT NULL,
        risk_score REAL NOT NULL,
        explanation TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS action_plans (
        id TEXT PRIMARY KEY,
        site_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        risk_tier TEXT NOT NULL,
        peak_period TEXT NOT NULL,
        action_summary TEXT NOT NULL,
        controls_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
    );
    """,
    # Performance and query indices
    "CREATE INDEX IF NOT EXISTS idx_sites_org ON sites(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_workforce_site ON workforce_profiles(site_id);",
    "CREATE INDEX IF NOT EXISTS idx_weather_site_ts ON weather_snapshots(site_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_wbgt_site_ts ON wbgt_calculations(site_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_risk_site_ts ON risk_assessments(site_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_action_site_ts ON action_plans(site_id, timestamp);",
]

# Migration registry ordered by version number
MIGRATIONS: Dict[int, Dict[str, object]] = {
    1: {
        "description": "Initial core schema for organizations, sites, workforce, weather, WBGT, risk, and action plans",
        "up": MIGRATION_1_UP,
    },
}
