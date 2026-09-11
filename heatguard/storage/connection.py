"""
Database connection management for HeatGuard SQLite persistence.
Supports file-based databases with WAL mode and in-memory databases for testing.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Generator, Optional


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "heatguard.db"


class DatabaseConnectionManager:
    """Manages SQLite connections, pragmas, and directory creation."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            self.db_path = str(DEFAULT_DB_PATH)
        else:
            self.db_path = str(db_path)

        self._is_memory = self.db_path in (":memory:", "file::memory:?cache=shared")

        if not self._is_memory:
            # Ensure parent directory exists
            parent_dir = Path(self.db_path).parent
            parent_dir.mkdir(parents=True, exist_ok=True)
            self._shared_conn = None
        else:
            # Keep a persistent connection for in-memory DB so it doesn't vanish between contexts
            self._shared_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._apply_pragmas(self._shared_conn)

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Enforce relational integrity and robust concurrency pragmas."""
        conn.execute("PRAGMA foreign_keys = ON;")
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a configured SQLite connection wrapped in transaction management."""
        if self._shared_conn is not None:
            # For in-memory DB, reuse persistent connection
            yield self._shared_conn
        else:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            self._apply_pragmas(conn)
            try:
                yield conn
            finally:
                conn.close()

    def close(self) -> None:
        """Close shared connection if open."""
        if self._shared_conn is not None:
            try:
                self._shared_conn.close()
            except Exception:
                pass
            self._shared_conn = None
