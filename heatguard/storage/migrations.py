"""
Migration management and runner for HeatGuard SQLite database.
Ensures version-controlled, idempotent, transactional schema updates.
"""

from datetime import datetime, timezone
import logging
from typing import List, Tuple

from heatguard.storage.connection import DatabaseConnectionManager
from heatguard.storage.schema import MIGRATIONS

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database schema discovery, validation, and migration execution."""

    def __init__(self, connection_manager: DatabaseConnectionManager):
        self.conn_mgr = connection_manager

    def get_applied_versions(self) -> List[int]:
        """Return a sorted list of applied migration versions."""
        with self.conn_mgr.get_connection() as conn:
            # Check if schema_migrations exists
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';"
            )
            if not cur.fetchone():
                return []

            cur.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
            rows = cur.fetchall()
            return [int(row["version"]) for row in rows]

    def get_current_version(self) -> int:
        """Return the highest applied migration version (0 if none)."""
        versions = self.get_applied_versions()
        return max(versions) if versions else 0

    def run_migrations(self) -> List[int]:
        """
        Execute all pending migrations in ascending order within individual transactions.
        Returns list of newly applied version numbers.
        """
        applied_versions = set(self.get_applied_versions())
        pending_versions = sorted([v for v in MIGRATIONS.keys() if v not in applied_versions])

        newly_applied: List[int] = []

        if not pending_versions:
            logger.info("Database schema is up to date at version %d.", self.get_current_version())
            return newly_applied

        for version in pending_versions:
            migration = MIGRATIONS[version]
            description = str(migration["description"])
            ddl_statements = migration["up"]

            logger.info("Applying migration %d: %s", version, description)

            with self.conn_mgr.get_connection() as conn:
                try:
                    cur = conn.cursor()
                    cur.execute("BEGIN TRANSACTION;")
                    for stmt in ddl_statements:  # type: ignore
                        cur.execute(stmt)

                    now_iso = datetime.now(timezone.utc).isoformat()
                    cur.execute(
                        """
                        INSERT INTO schema_migrations (version, applied_at, description)
                        VALUES (?, ?, ?);
                        """,
                        (version, now_iso, description),
                    )
                    conn.commit()
                    newly_applied.append(version)
                    logger.info("Successfully applied migration %d.", version)
                except Exception as exc:
                    conn.rollback()
                    logger.error("Failed to apply migration %d: %s", version, exc)
                    raise RuntimeError(f"Database migration {version} failed: {exc}") from exc

        return newly_applied
