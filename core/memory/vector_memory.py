"""
Digital Being — VectorMemory
Stage 9: SQLite-backed embedding store with cosine-similarity search.

Design rules:
  - Pure sqlite3 + numpy, no external vector DB
  - Embeddings stored as BLOB (np.float32.tobytes)
  - Cosine search: batch processing to avoid loading all vectors
  - All DB ops use `with self._conn:` (auto-commit)
  - Errors never crash the caller
  - Dimension validation prevents data corruption
  - Periodic cleanup prevents memory leaks
  - Max vectors limit prevents unbounded growth

Changelog:
  TD-005 fix — added cleanup_old_vectors() to prevent unbounded growth.
  TD-010 fix — added embedding dimension validation.
  P0 fix (2026-02-23) — batch processing, max_vectors limit, memory leak prevention.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger("digital_being.vector_memory")

# Constants
DEFAULT_MAX_VECTORS = 10_000  # Prevent unbounded growth
DEFAULT_BATCH_SIZE = 1000      # Process in batches to save memory
DEFAULT_CLEANUP_DAYS = 30      # Auto-cleanup after 30 days


class VectorMemory:
    """
    Stores and searches text embeddings with memory leak prevention.

    Usage:
        vm = VectorMemory(db_path, expected_dim=768, max_vectors=10000)
        vm.init()
        vm.add(episode_id=42, event_type="monologue", text="...", embedding=[...])
        results = vm.search(query_embedding=[...], top_k=5)
        
        # Automatic cleanup when limit exceeded
        # Or manual: vm.cleanup_old_vectors(days=30)
    """

    def __init__(
        self,
        db_path: Path,
        expected_dim: int = 768,
        max_vectors: int = DEFAULT_MAX_VECTORS,
        auto_cleanup: bool = True,
    ) -> None:
        self._db_path = db_path
        self._expected_dim = expected_dim
        self._max_vectors = max_vectors
        self._auto_cleanup = auto_cleanup
        self._conn: sqlite3.Connection | None = None
        
        # Statistics
        self._stats = {
            "total_searches": 0,
            "total_adds": 0,
            "total_cleanups": 0,
            "last_cleanup_time": 0,
        }

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
        
        # Check if cleanup needed on init
        if self._auto_cleanup:
            self._maybe_cleanup()
        
        log.info(
            f"VectorMemory initialised. DB: {self._db_path}, "
            f"expected_dim={self._expected_dim}, max_vectors={self._max_vectors}"
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
                    created_at  REAL      NOT NULL,
                    access_count INTEGER  DEFAULT 0,
                    last_access REAL
                );
                CREATE INDEX IF NOT EXISTS idx_vectors_event_type
                    ON vectors(event_type);
                CREATE INDEX IF NOT EXISTS idx_vectors_created_at
                    ON vectors(created_at);
                CREATE INDEX IF NOT EXISTS idx_vectors_access
                    ON vectors(access_count DESC, last_access DESC);
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
        Triggers automatic cleanup if max_vectors exceeded.
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
                    "(episode_id, event_type, text, embedding, created_at, last_access) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (episode_id, event_type, text, blob, time.time(), time.time()),
                )
                row_id = cur.lastrowid
            
            self._stats["total_adds"] += 1
            log.debug(f"VectorMemory: stored id={row_id} [{event_type}] ep={episode_id}")
            
            # Check if cleanup needed
            if self._auto_cleanup:
                self._maybe_cleanup()
            
            return row_id
        except sqlite3.Error as e:
            log.error(f"VectorMemory.add() DB error: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # Search (memory-efficient batch processing)
    # ──────────────────────────────────────────────────────────────
    def search(
        self,
        query_embedding:   list[float],
        top_k:             int = 5,
        event_type_filter: str | None = None,
        batch_size:        int = DEFAULT_BATCH_SIZE,
    ) -> list[dict]:
        """
        Find top_k most similar records by cosine similarity.
        Uses batch processing to avoid loading all vectors into memory.

        Returns list of dicts:
            {"id", "episode_id", "event_type", "text", "score", "created_at"}

        Returns [] if DB is empty or query_embedding is invalid.
        """
        arr = self._validate_embedding(query_embedding)
        if arr is None:
            return []

        self._stats["total_searches"] += 1

        try:
            # Get total count first
            if event_type_filter:
                count_row = self._conn.execute(
                    "SELECT COUNT(*) as cnt FROM vectors WHERE event_type = ?",
                    (event_type_filter,),
                ).fetchone()
            else:
                count_row = self._conn.execute(
                    "SELECT COUNT(*) as cnt FROM vectors"
                ).fetchone()
            
            total_count = count_row["cnt"] if count_row else 0
            
            if total_count == 0:
                return []
            
            # If total count is manageable, use simple approach
            if total_count <= batch_size:
                return self._search_simple(arr, top_k, event_type_filter)
            
            # Otherwise, use batch processing
            return self._search_batched(arr, top_k, event_type_filter, batch_size, total_count)
            
        except sqlite3.Error as e:
            log.error(f"VectorMemory.search() DB error: {e}")
            return []

    def _search_simple(
        self,
        query_arr: np.ndarray,
        top_k: int,
        event_type_filter: str | None,
    ) -> list[dict]:
        """Simple search for small datasets - loads all vectors."""
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
            log.error(f"VectorMemory._search_simple() DB error: {e}")
            return []

        if not rows:
            return []

        scored: list[tuple[float, Any]] = []

        for row in rows:
            try:
                vec = np.frombuffer(row["embedding"], dtype=np.float32)
                score = self._cosine_similarity(query_arr, vec)
                scored.append((score, row))
            except Exception as e:
                log.debug(f"VectorMemory._search_simple(): skip row id={row['id']}: {e}")
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        # Update access stats for top results
        self._update_access_stats([row["id"] for _, row in top])

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
            f"VectorMemory._search_simple(): top_k={top_k} "
            f"candidates={len(rows)} results={len(results)}"
        )
        return results

    def _search_batched(
        self,
        query_arr: np.ndarray,
        top_k: int,
        event_type_filter: str | None,
        batch_size: int,
        total_count: int,
    ) -> list[dict]:
        """Batch processing for large datasets - memory efficient."""
        log.debug(
            f"VectorMemory: using batched search for {total_count} vectors "
            f"(batch_size={batch_size})"
        )
        
        # Keep track of top-k across all batches
        all_scored: list[tuple[float, dict]] = []
        
        offset = 0
        while offset < total_count:
            try:
                if event_type_filter:
                    rows = self._conn.execute(
                        "SELECT id, episode_id, event_type, text, embedding, created_at "
                        "FROM vectors WHERE event_type = ? LIMIT ? OFFSET ?",
                        (event_type_filter, batch_size, offset),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        "SELECT id, episode_id, event_type, text, embedding, created_at "
                        "FROM vectors LIMIT ? OFFSET ?",
                        (batch_size, offset),
                    ).fetchall()
                
                if not rows:
                    break
                
                # Score this batch
                for row in rows:
                    try:
                        vec = np.frombuffer(row["embedding"], dtype=np.float32)
                        score = self._cosine_similarity(query_arr, vec)
                        
                        result = {
                            "id":         row["id"],
                            "episode_id": row["episode_id"],
                            "event_type": row["event_type"],
                            "text":       row["text"],
                            "score":      float(score),
                            "created_at": row["created_at"],
                        }
                        all_scored.append((score, result))
                    except Exception as e:
                        log.debug(f"VectorMemory._search_batched(): skip row id={row['id']}: {e}")
                        continue
                
                offset += batch_size
                
            except sqlite3.Error as e:
                log.error(f"VectorMemory._search_batched() batch error: {e}")
                break
        
        # Sort all results and get top-k
        all_scored.sort(key=lambda x: x[0], reverse=True)
        top_results = [result for _, result in all_scored[:top_k]]
        
        # Update access stats for top results
        self._update_access_stats([r["id"] for r in top_results])
        
        log.debug(
            f"VectorMemory._search_batched(): top_k={top_k} "
            f"total_candidates={len(all_scored)} results={len(top_results)}"
        )
        return top_results

    def _update_access_stats(self, vector_ids: list[int]) -> None:
        """Update access statistics for LRU cleanup."""
        if not vector_ids:
            return
        
        try:
            placeholders = ",".join("?" * len(vector_ids))
            with self._conn:
                self._conn.execute(
                    f"UPDATE vectors SET access_count = access_count + 1, "
                    f"last_access = ? WHERE id IN ({placeholders})",
                    [time.time()] + vector_ids,
                )
        except sqlite3.Error as e:
            log.warning(f"Failed to update access stats: {e}")

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

    def get_stats(self) -> dict:
        """Get memory and usage statistics."""
        return {
            "total_vectors": self.count(),
            "max_vectors": self._max_vectors,
            "total_searches": self._stats["total_searches"],
            "total_adds": self._stats["total_adds"],
            "total_cleanups": self._stats["total_cleanups"],
            "last_cleanup_time": self._stats["last_cleanup_time"],
            "auto_cleanup_enabled": self._auto_cleanup,
        }

    # ──────────────────────────────────────────────────────────────
    # Maintenance (TD-005 fix + auto cleanup)
    # ──────────────────────────────────────────────────────────────
    def _maybe_cleanup(self) -> None:
        """Check if cleanup needed and trigger if necessary."""
        current_count = self.count()
        
        if current_count > self._max_vectors:
            # Exceeded limit - cleanup based on LRU
            to_delete = current_count - self._max_vectors + 100  # Delete extra for buffer
            log.warning(
                f"VectorMemory: limit exceeded ({current_count} > {self._max_vectors}). "
                f"Cleaning up {to_delete} least accessed vectors."
            )
            self._cleanup_lru(to_delete)

    def _cleanup_lru(self, count: int) -> int:
        """
        Delete least recently used vectors.
        Uses access_count and last_access for smart cleanup.
        """
        try:
            with self._conn:
                # Delete vectors with lowest access_count and oldest last_access
                cur = self._conn.execute(
                    "DELETE FROM vectors WHERE id IN ("
                    "  SELECT id FROM vectors "
                    "  ORDER BY access_count ASC, last_access ASC "
                    "  LIMIT ?"
                    ")",
                    (count,),
                )
            deleted = cur.rowcount
            
            if deleted > 0:
                self._stats["total_cleanups"] += 1
                self._stats["last_cleanup_time"] = time.time()
                log.info(f"VectorMemory: LRU cleanup removed {deleted} vectors.")
                
                # VACUUM to reclaim space
                try:
                    log.debug("VectorMemory: running VACUUM...")
                    self._conn.execute("VACUUM")
                except sqlite3.Error as e:
                    log.warning(f"VectorMemory: VACUUM failed: {e}")
            
            return deleted
        except sqlite3.Error as e:
            log.error(f"VectorMemory._cleanup_lru() error: {e}")
            return 0

    def delete_old(self, days: int = DEFAULT_CLEANUP_DAYS) -> int:
        """
        Delete vectors older than `days` days.
        Returns number of deleted rows.
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
                self._stats["total_cleanups"] += 1
                self._stats["last_cleanup_time"] = time.time()
                log.info(f"VectorMemory.delete_old(): deleted {deleted} records older than {days}d.")
            
            return deleted
        except sqlite3.Error as e:
            log.error(f"VectorMemory.delete_old() DB error: {e}")
            return 0

    def cleanup_old_vectors(self, days: int = DEFAULT_CLEANUP_DAYS) -> int:
        """
        Smart cleanup: delete old vectors and reclaim space.
        
        Args:
            days: Delete vectors older than this
        
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
