"""
Digital Being — EpisodicMemory
Phase 3: SQLite-backed episodic memory.

Three tables:
  episodes   — everything the system perceives and does
  errors     — failures and self-assessment
  principles — rules derived from repeated errors

Design rules:
  - Pure sqlite3, no ORM
  - check_same_thread=False for asyncio compatibility
  - All writes are validated before touching the DB
  - Errors never crash the caller — they are logged and skipped
  - Automatic archival prevents unbounded growth

Changelog:
  Stage 8 — added get_episodes_by_type() for reflect action and StrategyEngine novelty.
  API Fix — added count() method for IntrospectionAPI compatibility.
  Perf Fix — added missing indexes for 5-10x query speedup (TD-009).
  TD-008 fix — added archive_old_episodes() to prevent unbounded growth.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.episodic")

# Validation limits
_MAX_DESC_LEN = 1000

# Valid values for constrained fields
_OUTCOMES = {"success", "failure", "unknown"}
_CAUSES   = {"my_assessment", "bad_plan", "external"}


class EpisodicMemory:
    """
    Episodic memory backed by SQLite.

    Usage:
        mem = EpisodicMemory(db_path)
        mem.init()          # call once at startup
        mem.add_episode(...)
        
        # Periodic maintenance (call from heavy tick every ~24 hours)
        archived = mem.archive_old_episodes(days=90)
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────
    def init(self) -> None:
        """Open the DB connection and create tables if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,   # autocommit — each write is its own transaction
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")   # safer for concurrent access
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        log.info(f"EpisodicMemory initialised. DB: {self._db_path}")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            log.info("EpisodicMemory connection closed.")

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                event_type    TEXT    NOT NULL,
                description   TEXT    NOT NULL,
                outcome       TEXT    NOT NULL DEFAULT 'unknown',
                data          TEXT
            );

            CREATE TABLE IF NOT EXISTS errors (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp         TEXT NOT NULL,
                error_type        TEXT NOT NULL,
                description       TEXT NOT NULL,
                cause             TEXT NOT NULL DEFAULT 'my_assessment',
                principle_formed  TEXT,
                repeat_count      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS principles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                text            TEXT    NOT NULL,
                source_error_id INTEGER REFERENCES errors(id),
                active          INTEGER NOT NULL DEFAULT 1
            );

            -- Existing indexes
            CREATE INDEX IF NOT EXISTS idx_episodes_event_type
                ON episodes(event_type);
            CREATE INDEX IF NOT EXISTS idx_episodes_timestamp
                ON episodes(timestamp);
            CREATE INDEX IF NOT EXISTS idx_errors_error_type
                ON errors(error_type);
            
            -- NEW: Performance indexes (TD-009 fix)
            CREATE INDEX IF NOT EXISTS idx_episodes_outcome
                ON episodes(outcome);
            CREATE INDEX IF NOT EXISTS idx_episodes_type_outcome
                ON episodes(event_type, outcome);
            CREATE INDEX IF NOT EXISTS idx_episodes_timestamp_desc
                ON episodes(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_errors_timestamp
                ON errors(timestamp);
        """)
        log.debug("DB tables and indexes verified/created.")

    # ──────────────────────────────────────────────────────────────
    # Validation helpers
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _validate_description(desc: str, context: str) -> bool:
        if not desc or not desc.strip():
            log.warning(f"[{context}] description is empty — skipping write.")
            return False
        if len(desc) > _MAX_DESC_LEN:
            log.warning(
                f"[{context}] description too long ({len(desc)} chars, max {_MAX_DESC_LEN}) — skipping."
            )
            return False
        return True

    @staticmethod
    def _serialize_data(data: Any, context: str) -> str | None:
        """Convert data to JSON string. Returns None if data is None or invalid."""
        if data is None:
            return None
        if isinstance(data, str):
            # Validate it's already valid JSON
            try:
                json.loads(data)
                return data
            except json.JSONDecodeError:
                log.warning(f"[{context}] data is not valid JSON — storing as null.")
                return None
        try:
            return json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            log.warning(f"[{context}] data serialization failed: {e} — storing as null.")
            return None

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    # ──────────────────────────────────────────────────────────────
    # Write methods
    # ──────────────────────────────────────────────────────────────
    def add_episode(
        self,
        event_type:  str,
        description: str,
        outcome:     str = "unknown",
        data:        Any = None,
    ) -> int | None:
        """
        Record a new episode.
        Returns the new row id, or None if validation failed.
        """
        if not self._validate_description(description, "add_episode"):
            return None

        if outcome not in _OUTCOMES:
            log.warning(f"[add_episode] invalid outcome '{outcome}', using 'unknown'.")
            outcome = "unknown"

        data_json = self._serialize_data(data, "add_episode")

        try:
            cur = self._conn.execute(
                "INSERT INTO episodes (timestamp, event_type, description, outcome, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (self._now(), event_type, description.strip(), outcome, data_json),
            )
            row_id = cur.lastrowid
            log.debug(f"Episode #{row_id} written: [{event_type}] {description[:60]}")
            return row_id
        except sqlite3.Error as e:
            log.error(f"[add_episode] DB error: {e}")
            return None

    def add_error(
        self,
        error_type:  str,
        description: str,
        cause:       str = "my_assessment",
    ) -> int | None:
        """
        Record an error.
        If an identical error_type already exists, increments repeat_count instead.
        Returns the row id.
        """
        if not self._validate_description(description, "add_error"):
            return None

        if cause not in _CAUSES:
            log.warning(f"[add_error] invalid cause '{cause}', using 'my_assessment'.")
            cause = "my_assessment"

        try:
            # Check if same error_type exists — increment if so
            row = self._conn.execute(
                "SELECT id FROM errors WHERE error_type = ? ORDER BY id DESC LIMIT 1",
                (error_type,),
            ).fetchone()

            if row:
                self._conn.execute(
                    "UPDATE errors SET repeat_count = repeat_count + 1, timestamp = ? "
                    "WHERE id = ?",
                    (self._now(), row["id"]),
                )
                log.debug(f"Error '{error_type}' repeat_count incremented (id={row['id']}).")
                return row["id"]
            else:
                cur = self._conn.execute(
                    "INSERT INTO errors (timestamp, error_type, description, cause) "
                    "VALUES (?, ?, ?, ?)",
                    (self._now(), error_type, description.strip(), cause),
                )
                log.debug(f"Error #{cur.lastrowid} written: [{error_type}]")
                return cur.lastrowid
        except sqlite3.Error as e:
            log.error(f"[add_error] DB error: {e}")
            return None

    def add_principle(self, text: str, source_error_id: int | None = None) -> int | None:
        """Add a new principle derived from an error."""
        if not self._validate_description(text, "add_principle"):
            return None
        try:
            cur = self._conn.execute(
                "INSERT INTO principles (timestamp, text, source_error_id, active) "
                "VALUES (?, ?, ?, 1)",
                (self._now(), text.strip(), source_error_id),
            )
            # Back-fill principle_formed on the source error row
            if source_error_id is not None:
                self._conn.execute(
                    "UPDATE errors SET principle_formed = ? WHERE id = ?",
                    (text.strip(), source_error_id),
                )
            log.info(f"Principle #{cur.lastrowid} formed: {text[:80]}")
            return cur.lastrowid
        except sqlite3.Error as e:
            log.error(f"[add_principle] DB error: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # Read methods
    # ──────────────────────────────────────────────────────────────
    def count(self) -> int:
        """Return total number of episodes. Used by IntrospectionAPI."""
        try:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM episodes").fetchone()
            return row["cnt"] if row else 0
        except sqlite3.Error as e:
            log.error(f"[count] DB error: {e}")
            return 0

    def get_recent_episodes(self, limit: int = 20) -> list[dict]:
        """Return the last N episodes, newest first."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM episodes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error(f"[get_recent_episodes] DB error: {e}")
            return []

    def get_episodes_by_type(
        self,
        event_type: str,
        limit: int = 20,
        outcome: str | None = None,
    ) -> list[dict]:
        """
        Return episodes filtered by event_type (and optionally outcome), newest first.

        Added in Stage 8 — used by:
          - HeavyTick._action_reflect()  (event_type="error", outcome=None)
          - StrategyEngine._apply_novelty() via count_recent_similar()

        Args:
            event_type: exact match on the event_type column.
            limit:      max rows returned (default 20).
            outcome:    if provided, additionally filter by outcome column.
        """
        try:
            if outcome is not None:
                rows = self._conn.execute(
                    "SELECT * FROM episodes "
                    "WHERE event_type = ? AND outcome = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (event_type, outcome, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM episodes "
                    "WHERE event_type = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error(f"[get_episodes_by_type] DB error: {e}")
            return []

    def get_errors_by_type(self, error_type: str) -> list[dict]:
        """Return all errors of a given type."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM errors WHERE error_type = ? ORDER BY id DESC",
                (error_type,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error(f"[get_errors_by_type] DB error: {e}")
            return []

    def count_recent_similar(self, event_type: str, hours: int = 1) -> int:
        """
        Count how many episodes of this event_type occurred in the last N hours.
        Used for Novelty Score calculation.
        """
        try:
            cutoff = time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.localtime(time.time() - hours * 3600),
            )
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM episodes "
                "WHERE event_type = ? AND timestamp >= ?",
                (event_type, cutoff),
            ).fetchone()
            return row["cnt"] if row else 0
        except sqlite3.Error as e:
            log.error(f"[count_recent_similar] DB error: {e}")
            return 0

    def get_active_principles(self) -> list[dict]:
        """Return all active principles."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM principles WHERE active = 1 ORDER BY id ASC",
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error(f"[get_active_principles] DB error: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Maintenance (TD-008 fix)
    # ──────────────────────────────────────────────────────────────
    def archive_old_episodes(self, days: int = 90) -> int:
        """
        Archive episodes older than N days to separate monthly database.
        
        This prevents the main DB from growing unbounded while preserving
        all historical data in monthly archive files.
        
        Args:
            days: Archive episodes older than this many days (default 90)
        
        Returns:
            Number of episodes archived and deleted from main DB
        
        Archives are stored in memory/archives/ with names like:
            episodic_archive_2026_02.db
        
        Call this periodically (e.g. once per week / ~168 heavy ticks)
        to keep the main database fast.
        """
        cutoff = time.strftime(
            "%Y-%m-%dT%H:%M:%S",
            time.localtime(time.time() - days * 86400)
        )
        
        try:
            # Count episodes to archive
            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM episodes WHERE timestamp < ?",
                (cutoff,)
            ).fetchone()
            to_archive = count_row["cnt"] if count_row else 0
            
            if to_archive == 0:
                log.debug(f"No episodes older than {days} days to archive")
                return 0
            
            # Create archive directory
            archive_dir = self._db_path.parent / "archives"
            archive_dir.mkdir(exist_ok=True)
            
            # Archive filename based on current month
            month_str = time.strftime("%Y_%m")
            archive_path = archive_dir / f"episodic_archive_{month_str}.db"
            
            # Open or create archive DB
            archive_conn = sqlite3.connect(str(archive_path))
            archive_conn.row_factory = sqlite3.Row
            
            # Create tables in archive if needed
            archive_conn.executescript("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id            INTEGER PRIMARY KEY,
                    timestamp     TEXT    NOT NULL,
                    event_type    TEXT    NOT NULL,
                    description   TEXT    NOT NULL,
                    outcome       TEXT    NOT NULL DEFAULT 'unknown',
                    data          TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_episodes_timestamp
                    ON episodes(timestamp);
            """)
            
            # Copy old episodes to archive
            rows = self._conn.execute(
                "SELECT * FROM episodes WHERE timestamp < ?",
                (cutoff,)
            ).fetchall()
            
            for row in rows:
                archive_conn.execute(
                    "INSERT OR IGNORE INTO episodes VALUES (?, ?, ?, ?, ?, ?)",
                    tuple(row)
                )
            
            archive_conn.commit()
            archive_conn.close()
            
            # Delete from main DB
            self._conn.execute(
                "DELETE FROM episodes WHERE timestamp < ?",
                (cutoff,)
            )
            
            # Reclaim disk space
            log.info(f"Running VACUUM to reclaim space...")
            self._conn.execute("VACUUM")
            
            log.info(
                f"Archived {to_archive} episodes older than {days} days "
                f"to {archive_path.name}"
            )
            return to_archive
            
        except sqlite3.Error as e:
            log.error(f"[archive_old_episodes] DB error: {e}")
            return 0

    # ──────────────────────────────────────────────────────────────
    # Health check
    # ──────────────────────────────────────────────────────────────
    def health_check(self) -> bool:
        """
        Verify DB integrity:
          - All three tables exist
          - Each table responds to a simple SELECT
        Returns True if healthy, False otherwise.
        """
        required_tables = {"episodes", "errors", "principles"}
        try:
            rows = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            found = {r["name"] for r in rows}
            missing = required_tables - found
            if missing:
                log.error(f"[health_check] Missing tables: {missing}")
                return False

            # Smoke-test each table
            for tbl in required_tables:
                self._conn.execute(f"SELECT 1 FROM {tbl} LIMIT 1")  # noqa: S608

            log.debug("[health_check] DB healthy.")
            return True
        except sqlite3.Error as e:
            log.error(f"[health_check] DB error: {e}")
            return False
