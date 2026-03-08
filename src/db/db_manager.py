"""
Thin SQLite wrapper for local database operations.

Provides a simple, consistent interface that can be swapped for a
Supabase (PostgreSQL) adapter in Phase 9 without changing caller code.

Usage:
    db = DBManager()
    with db.connect() as conn:
        db.execute(conn, "INSERT INTO ...", (val1, val2))
        rows = db.fetch_all(conn, "SELECT * FROM raw_jobs")
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from loguru import logger

from config.settings import DATA_DIR
from src.db.models import initialize_db


# ---------------------------------------------------------------------------
# Database file location
# ---------------------------------------------------------------------------
DB_PATH = DATA_DIR / "db" / "jobs.db"


class DBManager:
    """
    SQLite connection manager and query executor.

    All public methods accept an open connection as their first argument.
    This keeps transaction control in the caller's hands.

    Why not use an ORM?
    SQLite here is a local scratch-pad. Phase 9 replaces it with Supabase.
    The thin wrapper (vs ORM) makes that migration a one-file change.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_initialized()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager that yields an open SQLite connection.

        Commits on clean exit, rolls back on exception.
        Always closes the connection.

        Usage:
            with db.connect() as conn:
                db.insert(conn, ...)
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row      # Rows accessible as dicts
        conn.execute("PRAGMA journal_mode=WAL")   # Better concurrent writes
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def execute(
        self, conn: sqlite3.Connection, sql: str, params: tuple = ()
    ) -> sqlite3.Cursor:
        """Execute a single SQL statement (INSERT, UPDATE, DELETE)."""
        return conn.execute(sql, params)

    def execute_many(
        self, conn: sqlite3.Connection, sql: str, rows: list[tuple]
    ) -> int:
        """Execute a statement for multiple rows. Returns row count."""
        cursor = conn.executemany(sql, rows)
        return cursor.rowcount

    def fetch_one(
        self, conn: sqlite3.Connection, sql: str, params: tuple = ()
    ) -> dict | None:
        """Return a single row as a dict, or None if not found."""
        cursor = conn.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(
        self, conn: sqlite3.Connection, sql: str, params: tuple = ()
    ) -> list[dict]:
        """Return all matching rows as a list of dicts."""
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def insert(
        self,
        conn: sqlite3.Connection,
        table: str,
        data: dict,
        or_ignore: bool = False,
    ) -> int | None:
        """
        Insert a dict into a table.

        Args:
            conn:      Open connection.
            table:     Table name.
            data:      Column → value mapping.
            or_ignore: If True, silently skip on UNIQUE constraint violations.

        Returns:
            The rowid of the inserted row, or None if skipped (or_ignore=True).
        """
        if not data:
            return None
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conflict = "OR IGNORE" if or_ignore else ""
        sql = f"INSERT {conflict} INTO {table} ({cols}) VALUES ({placeholders})"
        cursor = conn.execute(sql, tuple(data.values()))
        return cursor.lastrowid if cursor.lastrowid else None

    def exists(
        self, conn: sqlite3.Connection, table: str, where_col: str, where_val: Any
    ) -> bool:
        """Check if a row with the given column value exists."""
        row = self.fetch_one(
            conn,
            f"SELECT 1 FROM {table} WHERE {where_col} = ? LIMIT 1",
            (where_val,),
        )
        return row is not None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def to_json(value: Any) -> str:
        """Serialize a Python value to a JSON string for TEXT columns."""
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def from_json(value: str | None) -> Any:
        """Deserialize a JSON string from a TEXT column."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def _ensure_initialized(self) -> None:
        """Create all tables on first run (idempotent)."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            initialize_db(conn)
            conn.commit()
        finally:
            conn.close()
        logger.debug(f"[db] Database initialized at {self.db_path}")
