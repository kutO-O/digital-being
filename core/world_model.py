"""
Digital Being — WorldModel
Phase 4: In-memory representation of the file environment.

Rules:
  - 100% read-only: never writes to the filesystem
  - All state lives in memory (file_index, change_log, patterns)
  - Integrates with EventBus (subscribe) and EpisodicMemory (write)
  - Pattern decay runs once per 24 hours via tick counter
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.world_model")

# ──────────────────────────────────────────────────────────────
# Config constants
# ──────────────────────────────────────────────────────────────
_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB
_CHANGE_LOG_MAXLEN   = 100
_ANOMALY_DAYS        = 30                 # days without modification = anomaly candidate
_PATTERN_DECAY_STEP  = 0.05
_PATTERN_ARCHIVE_THR = 0.1               # below this → archived
_PATTERN_ACTIVE_THR  = 0.3               # below this → not "active"
_DECAY_INTERVAL_SEC  = 86400             # 24 hours

_IGNORED_DIRS = {"__pycache__", ".git", "snapshots"}

# Importance score rules — evaluated in order, first match wins
_IMPORTANCE_RULES: list[tuple] = [
    # (matcher_fn, score)
    (lambda p: "memory" in Path(p).parts,               1.0),
    (lambda p: Path(p).name in {
        "self_model.json", "config.yaml", "seed.yaml"},  1.0),
    (lambda p: Path(p).name in {"inbox.txt", "outbox.txt"}, 0.8),
    (lambda p: "logs" in Path(p).parts,                 0.7),
    (lambda p: "sandbox" in Path(p).parts,              0.3),
]
_IMPORTANCE_DEFAULT = 0.5


# ──────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────
@dataclass
class FileEntry:
    path:             str
    size:             int           # bytes
    modified_at:      float         # unix timestamp
    importance_score: float         # 0.0 – 1.0
    last_seen:        float         # unix timestamp of last index update
    deleted:          bool = False


@dataclass
class PatternEntry:
    pattern_type:   str            # temporal | structural | anomaly
    description:    str
    confidence:     float          # 0.0 – 1.0
    last_confirmed: float          # unix timestamp
    created_at:     float          # unix timestamp


@dataclass
class ChangeRecord:
    timestamp:   float
    change_type: str               # created | modified | deleted
    path:        str


# ──────────────────────────────────────────────────────────────
# WorldModel
# ──────────────────────────────────────────────────────────────
class WorldModel:
    """
    In-memory model of the file environment.

    Lifecycle:
        wm = WorldModel(bus, mem)
        wm.subscribe()          # wire EventBus handlers
        await wm.scan(root)     # initial full scan
        # ... runs forever via EventBus events
    """

    def __init__(self, bus: "EventBus", mem: "EpisodicMemory") -> None:
        self._bus  = bus
        self._mem  = mem

        self.file_index:      dict[str, FileEntry]   = {}
        self.change_log:      deque[ChangeRecord]    = deque(maxlen=_CHANGE_LOG_MAXLEN)
        self.patterns:        list[PatternEntry]     = []
        self.archived_patterns: list[PatternEntry]  = []

        self._last_decay_time: float = time.time()

    # ────────────────────────────────────────────────────────────
    # EventBus wiring
    # ────────────────────────────────────────────────────────────
    def subscribe(self) -> None:
        """Register all EventBus handlers."""
        self._bus.subscribe("world.file_changed", self._on_file_changed)
        self._bus.subscribe("world.file_created", self._on_file_created)
        self._bus.subscribe("world.file_deleted", self._on_file_deleted)
        log.debug("WorldModel subscribed to world.file_* events.")

    # ────────────────────────────────────────────────────────────
    # Scan
    # ────────────────────────────────────────────────────────────
    async def scan(self, root_path: Path) -> int:
        """
        Full recursive scan of root_path.
        Updates file_index. Returns number of files indexed.
        Publishes world.ready when done.
        """
        count = 0
        now   = time.time()

        for dirpath, dirnames, filenames in os.walk(root_path):
            # Prune ignored directories in-place (prevents os.walk from descending)
            dirnames[:] = [
                d for d in dirnames
                if d not in _IGNORED_DIRS
            ]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                entry = self._build_entry(fpath, now)
                if entry is not None:
                    self.file_index[str(fpath)] = entry
                    count += 1

        log.info(f"WorldModel scan complete. Indexed {count} files.")
        await self._bus.publish("world.ready", {"file_count": count})
        return count

    def _build_entry(self, fpath: Path, now: float) -> FileEntry | None:
        """Stat a file and build a FileEntry. Returns None if file should be skipped."""
        try:
            stat = fpath.stat()
        except OSError:
            return None

        if stat.st_size > _MAX_FILE_SIZE_BYTES:
            log.debug(f"Skipping large file ({stat.st_size // (1024*1024)}MB): {fpath}")
            return None

        return FileEntry(
            path=str(fpath),
            size=stat.st_size,
            modified_at=stat.st_mtime,
            importance_score=self._calc_importance(str(fpath)),
            last_seen=now,
        )

    # ────────────────────────────────────────────────────────────
    # Importance scoring
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _calc_importance(path: str) -> float:
        for matcher, score in _IMPORTANCE_RULES:
            try:
                if matcher(path):
                    return score
            except Exception:
                continue
        return _IMPORTANCE_DEFAULT

    def get_importance(self, path: str) -> float:
        entry = self.file_index.get(path)
        return entry.importance_score if entry else _IMPORTANCE_DEFAULT

    # ────────────────────────────────────────────────────────────
    # File event handlers (async — called by EventBus)
    # ────────────────────────────────────────────────────────────
    async def _on_file_changed(self, data: dict) -> None:
        path = data.get("path", "")
        self.on_file_changed(path)
        await self._post_update()

    async def _on_file_created(self, data: dict) -> None:
        path = data.get("path", "")
        self.on_file_created(path)
        await self._post_update()

    async def _on_file_deleted(self, data: dict) -> None:
        path = data.get("path", "")
        self.on_file_deleted(path)
        await self._post_update()

    async def _post_update(self) -> None:
        """After any file event: publish world.updated and run decay if due."""
        await self._bus.publish("world.updated", {"summary": self.summary()})
        self._maybe_decay()

    # ────────────────────────────────────────────────────────────
    # Sync index update methods (callable without await)
    # ────────────────────────────────────────────────────────────
    def on_file_changed(self, path: str) -> None:
        now   = time.time()
        entry = self.file_index.get(path)
        if entry:
            try:
                stat = Path(path).stat()
                entry.size        = stat.st_size
                entry.modified_at = stat.st_mtime
                entry.last_seen   = now
                entry.deleted     = False
            except OSError:
                pass
        else:
            # File not in index yet — treat as new
            new_entry = self._build_entry(Path(path), now)
            if new_entry:
                self.file_index[path] = new_entry

        self.change_log.append(ChangeRecord(now, "modified", path))
        log.debug(f"WorldModel: file modified → {path}")

    def on_file_created(self, path: str) -> None:
        now       = time.time()
        new_entry = self._build_entry(Path(path), now)
        if new_entry:
            self.file_index[path] = new_entry
        self.change_log.append(ChangeRecord(now, "created", path))
        log.debug(f"WorldModel: file created → {path}")

    def on_file_deleted(self, path: str) -> None:
        now   = time.time()
        entry = self.file_index.get(path)
        if entry:
            entry.deleted   = True
            entry.last_seen = now
        self.change_log.append(ChangeRecord(now, "deleted", path))
        log.debug(f"WorldModel: file deleted → {path}")

    # ────────────────────────────────────────────────────────────
    # Change log
    # ────────────────────────────────────────────────────────────
    def get_recent_changes(self, limit: int = 20) -> list[ChangeRecord]:
        """Return last N changes, newest first."""
        items = list(self.change_log)
        return list(reversed(items))[:limit]

    # ────────────────────────────────────────────────────────────
    # Patterns
    # ────────────────────────────────────────────────────────────
    def add_pattern(
        self,
        pattern_type: str,
        description:  str,
        confidence:   float,
    ) -> PatternEntry:
        now     = time.time()
        pattern = PatternEntry(
            pattern_type=pattern_type,
            description=description,
            confidence=max(0.0, min(1.0, confidence)),
            last_confirmed=now,
            created_at=now,
        )
        self.patterns.append(pattern)
        log.info(f"Pattern added [{pattern_type}] conf={confidence:.2f}: {description[:80]}")

        # Persist to episodic memory
        self._mem.add_episode(
            event_type="world.pattern_found",
            description=f"[{pattern_type}] {description[:900]}",
            outcome="unknown",
            data={"confidence": confidence},
        )
        return pattern

    def decay_patterns(self) -> None:
        """
        Reduce confidence of all patterns by _PATTERN_DECAY_STEP.
        Patterns falling below _PATTERN_ARCHIVE_THR are moved to archived_patterns.
        """
        remaining = []
        archived  = []
        for p in self.patterns:
            p.confidence = round(p.confidence - _PATTERN_DECAY_STEP, 4)
            if p.confidence < _PATTERN_ARCHIVE_THR:
                archived.append(p)
                log.debug(f"Pattern archived (conf={p.confidence:.2f}): {p.description[:60]}")
            else:
                remaining.append(p)

        self.archived_patterns.extend(archived)
        self.patterns = remaining

        log.info(
            f"Pattern decay complete. Active: {len(remaining)}, "
            f"Archived this run: {len(archived)}, "
            f"Total archived: {len(self.archived_patterns)}"
        )

    def get_active_patterns(self) -> list[PatternEntry]:
        """Return patterns with confidence >= _PATTERN_ACTIVE_THR."""
        return [p for p in self.patterns if p.confidence >= _PATTERN_ACTIVE_THR]

    def _maybe_decay(self) -> None:
        """Trigger decay if 24 hours have passed since the last decay."""
        if time.time() - self._last_decay_time >= _DECAY_INTERVAL_SEC:
            self._last_decay_time = time.time()
            self.decay_patterns()

    # ────────────────────────────────────────────────────────────
    # Anomaly detection
    # ────────────────────────────────────────────────────────────
    def detect_anomalies(self) -> list[str]:
        """
        Find files that haven’t been modified in >30 days
        while others around them are actively changing.

        Strategy:
          1. Calculate median age across all non-deleted files
          2. Files older than _ANOMALY_DAYS are candidates
          3. Only flag as anomaly if there ARE recent changes (system is active)
             — avoids false alarms on a completely idle system

        Returns list of paths. Also writes to EpisodicMemory and adds
        a pattern entry for each anomaly found.
        """
        now            = time.time()
        anomaly_cutoff = now - (_ANOMALY_DAYS * 86400)
        recent_cutoff  = now - 86400   # "active" = changed in last 24h

        active_files = [
            e for e in self.file_index.values()
            if not e.deleted and e.modified_at >= recent_cutoff
        ]

        # Only meaningful if system is actively changing
        if len(active_files) < 2:
            return []

        anomalies = [
            e.path for e in self.file_index.values()
            if not e.deleted
            and e.modified_at < anomaly_cutoff
            and e.importance_score >= 0.5   # only care about important files
        ]

        for path in anomalies:
            desc = f"File not modified for >{_ANOMALY_DAYS} days: {path}"
            self._mem.add_episode(
                event_type="world.anomaly",
                description=desc[:1000],
                outcome="unknown",
                data={"path": path},
            )
            self.add_pattern(
                pattern_type="anomaly",
                description=desc,
                confidence=0.6,
            )
            log.warning(f"Anomaly detected: {path}")

        return anomalies

    # ────────────────────────────────────────────────────────────
    # Summary
    # ────────────────────────────────────────────────────────────
    def summary(self) -> str:
        total_files   = sum(1 for e in self.file_index.values() if not e.deleted)
        cutoff_24h    = time.time() - 86400
        changes_24h   = sum(1 for c in self.change_log if c.timestamp >= cutoff_24h)
        active_pats   = len(self.get_active_patterns())
        return (
            f"files={total_files} "
            f"changes_24h={changes_24h} "
            f"active_patterns={active_pats}"
        )
