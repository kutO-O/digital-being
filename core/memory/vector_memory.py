"""
Digital Being — VectorMemory
Stage 9: SQLite-backed embedding store with cosine-similarity search.

Design rules:
  - Pure sqlite3 + numpy, no external vector DB
  - Embeddings stored as BLOB (np.float32.tobytes)
  - Cosine search: load all (optionally filtered) vectors, rank in-process
  - All DB ops use `with self._conn:` (auto-commit)
  - Errors never crash the caller
  - Dimension validation prevents data corruption
  - Periodic cleanup prevents memory leaks

Changelog:
  TD-005 fix — added cleanup_old_vectors() to prevent unbounded growth.
  TD-010 fix — added embedding dimension validation.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger("digital_being.vector_memory")


class VectorMemory:
    """
    Stores and searches text embeddings.

    Usage:
        vm = VectorMemory(db_path, expected_dim=768)
        vm.init()
        vm.add(episode_id=42, event_type="monologue", text="...", embedding=[...])
        results = vm.search(query_embedding=[...], top_k=5)
        
        # Periodic maintenance (call from heavy tick every ~24 hours)
        vm.cleanup_old_vectors(days=30)
    """

    def __init__(self, db_path: Path, expected_dim: int = 768) -> None:
        self._db_path = db_path
        self._expected_dim = expected_dim  # TD-010: validate dimensions
        self._conn: sqlite3.Connection | None = None

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────
    def init(self) -> None:
        """Open DB connection and create table + indexes if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_table()
        log.info(
            f"VectorMemory initialised. DB: {self._db_path}, "
            f"expected_dim={self._expected_dim}"
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            log.info("VectorMemory connection closed.")

    def _create_table(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id  INTEGER,
                    event_type  TEXT,
                    text        TEXT,
                    embedding   BLOB      NOT NULL,
                    created_at  REAL      NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_vectors_event_type
                    ON vectors(event_type);
                CREATE INDEX IF NOT EXISTS idx_vectors_created_at
                    ON vectors(created_at);
            """)
        log.debug("VectorMemory: table verified/created.")

    # ──────────────────────────────────────────────────────────────
    # Validation (TD-010)
    # ──────────────────────────────────────────────────────────────
    def _validate_embedding(self, embedding: list[float]) -> np.ndarray | None:
        """
        Validate embedding and convert to numpy array.
        Returns None if invalid, otherwise normalized float32 array.
        """
        if not embedding:
            return None
        
        # Check dimension
        if len(embedding) != self._expected_dim:
            log.error(
                f"Embedding dimension mismatch: expected {self._expected_dim}, "
                f"got {len(embedding)}. Rejecting."
            )
            return None
        
        # Convert and validate values
        arr = np.array(embedding, dtype=np.float32)
        
        if np.any(np.isnan(arr)):
            log.error("Embedding contains NaN - rejecting")
            return None
        
        if np.any(np.isinf(arr)):
            log.error("Embedding contains Inf - rejecting")
            return None
        
        return arr

    # ──────────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────────
    def add(
        self,
        episode_id: int,
        event_type: str,
        text:       str,
        embedding:  list[float],
    ) -> int | None:
        """
        Store an embedding.
        Validates dimension and values before storing.
        Returns new row id, or None on failure/validation error.
        """
        arr = self._validate_embedding(embedding)
        if arr is None:
            return None

        blob = arr.tobytes()
        try:
            with self._conn:
                cur = self._conn.execute(
                    "INSERT INTO vectors "
                    "(episode_id, event_type, text, embedding, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (episode_id, event_type, text, blob, time.time()),
                )
                row_id = cur.lastrowid
            log.debug(f"VectorMemory: stored id={row_id} [{event_type}] ep={episode_id}")
            return row_id
        except sqlite3.Error as e:
            log.error(f"VectorMemory.add() DB error: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────────────
    def search(
        self,
        query_embedding:   list[float],
        top_k:             int = 5,
        event_type_filter: str | None = None,
    ) -> list[dict]:
        """
        Find top_k most similar records by cosine similarity.

        Returns list of dicts:
            {"id", "episode_id", "event_type", "text", "score", "created_at"}

        Returns [] if DB is empty or query_embedding is invalid.
        """
        arr = self._validate_embedding(query_embedding)
        if arr is None:
            return []

        try:
            if event_type_filter:
                rows = self._conn.execute(
                    "SELECT id, episode_id, event_type, text, embedding, created_at "
                    "FROM vectors WHERE event_type = ?",
                    (event_type_filter,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, episode_id, event_type, text, embedding, created_at "
                    "FROM vectors"
                ).fetchall()
        except sqlite3.Error as e:
            log.error(f"VectorMemory.search() DB error: {e}")
            return []

        if not rows:
            return []

        scored: list[tuple[float, Any]] = []

        for row in rows:
            try:
                vec = np.frombuffer(row["embedding"], dtype=np.float32)
                score = self._cosine_similarity(arr, vec)
                scored.append((score, row))
            except Exception as e:
                log.debug(f"VectorMemory.search(): skip row id={row['id']}: {e}")
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        results = [
            {
                "id":         row["id"],
                "episode_id": row["episode_id"],
                "event_type": row["event_type"],
                "text":       row["text"],
                "score":      float(score),
                "created_at": row["created_at"],
            }
            for score, row in top
        ]
        log.debug(
            f"VectorMemory.search(): top_k={top_k} filter={event_type_filter!r} "
            f"candidates={len(rows)} results={len(results)}"
        )
        return results

    # ──────────────────────────────────────────────────────────────
    # Read helpers
    # ──────────────────────────────────────────────────────────────
    def count(self) -> int:
        """Total number of stored vectors."""
        try:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM vectors"
            ).fetchone()
            return row["cnt"] if row else 0
        except sqlite3.Error as e:
            log.error(f"VectorMemory.count() DB error: {e}")
            return 0

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Return last N records (no embedding blob — text only), newest first."""
        try:
            rows = self._conn.execute(
                "SELECT id, episode_id, event_type, text, created_at "
                "FROM vectors ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            log.error(f"VectorMemory.get_recent() DB error: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Maintenance (TD-005 fix)
    # ──────────────────────────────────────────────────────────────
    def delete_old(self, days: int = 30) -> int:
        """
        Delete vectors older than `days` days.
        Returns number of deleted rows.
        Simple version: no importance check.
        """
        cutoff = time.time() - days * 86400
        try:
            with self._conn:
                cur = self._conn.execute(
                    "DELETE FROM vectors WHERE created_at < ?",
                    (cutoff,),
                )
            deleted = cur.rowcount
            if deleted > 0:
                log.info(f"VectorMemory.delete_old(): deleted {deleted} records older than {days}d.")
            return deleted
        except sqlite3.Error as e:
            log.error(f"VectorMemory.delete_old() DB error: {e}")
            return 0

    def cleanup_old_vectors(self, days: int = 30, keep_important: bool = False) -> int:
        """
        Smart cleanup: delete old, low-value vectors.
        
        Args:
            days: Delete vectors older than this
            keep_important: If True, preserve vectors from successful episodes
                          (requires episodic DB join - not implemented yet)
        
        Returns:
            Number of deleted vectors
        
        Call this periodically (e.g. once per 24 hours / ~24 heavy ticks)
        to prevent unbounded memory growth.
        """
        deleted = self.delete_old(days)
        
        if deleted > 0:
            # Reclaim disk space
            try:
                log.info("VectorMemory: running VACUUM to reclaim space...")
                self._conn.execute("VACUUM")
                log.info("VectorMemory: VACUUM complete")
            except sqlite3.Error as e:
                log.warning(f"VectorMemory: VACUUM failed: {e}")
        
        return deleted

    def health_check(self) -> bool:
        """
        Verify DB is accessible and table exists.
        Returns True if healthy, False otherwise.
        """
        try:
            self._conn.execute("SELECT COUNT(*) FROM vectors").fetchone()
            return True
        except sqlite3.Error as e:
            log.error(f"VectorMemory health_check failed: {e}")
            return False

    # ──────────────────────────────────────────────────────────────
    # Math
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity in [-1, 1]. Returns 0 if either vector is zero."""
        dot  = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(dot / norm) if norm > 0 else 0.0
