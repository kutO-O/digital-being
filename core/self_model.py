"""
Digital Being — SelfModel
Phase 6: Identity, principles, history, drift detection.

Two layers:
  Locked  — core_values: never modified after Cold Start
  Flexible — formed_principles: grow and merge over time

self_model.json schema:
  {
    "identity": {
      "name": str,
      "purpose": str,
      "core_values": list[str],    # locked
      "formed_principles": list[str],
      "version": int
    },
    "history": [{"version": int, "change": str, "timestamp": str}]
  }
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.self_model")

# Locked core values — hardcoded, never loaded from file
_CORE_VALUES: list[str] = [
    "exploration",
    "stability",
    "growth",
    "self_preservation",
]

_SELF_SNAPSHOTS_DIR_KEY = "self_snapshots"
_MAX_WEEKLY_VERSION_CHANGE = 3


class SelfModel:
    """
    Stores and evolves the system’s identity.

    Lifecycle:
        sm = SelfModel(bus)
        sm.load(self_model_path, seed_path)   # once at startup
        sm.subscribe()                         # wire EventBus
    """

    def __init__(self, bus: "EventBus") -> None:
        self._bus  = bus
        self._path: Path | None = None
        self._snapshots_dir: Path | None = None

        self._identity: dict = {
            "name":              "Digital Being",
            "purpose":           "",
            "core_values":       list(_CORE_VALUES),
            "formed_principles": [],
            "version":           1,
        }
        self._history: list[dict] = []

    # ────────────────────────────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────────────────────────────
    def load(
        self,
        self_model_path: Path,
        seed_path: Path,
        snapshots_dir: Path,
    ) -> None:
        """
        Load from self_model.json.
        If file does not exist — Cold Start from seed.yaml.
        """
        self._path          = self_model_path
        self._snapshots_dir = snapshots_dir
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        if self_model_path.exists():
            self._load_existing(self_model_path)
        else:
            self._cold_start(seed_path, self_model_path)

    def _load_existing(self, path: Path) -> None:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._identity = data.get("identity", self._identity)
            self._history  = data.get("history", [])
            # Always enforce locked core_values from code, not from file
            self._identity["core_values"] = list(_CORE_VALUES)
            log.info(
                f"SelfModel loaded. Name='{self._identity['name']}' "
                f"Version={self._identity['version']} "
                f"Principles={len(self._identity['formed_principles'])}"
            )
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"SelfModel load failed: {e}. Falling back to defaults.")

    def _cold_start(self, seed_path: Path, out_path: Path) -> None:
        """Create self_model.json from seed.yaml on first run."""
        name    = "Digital Being"
        purpose = ""

        if seed_path.exists():
            try:
                import yaml
                with seed_path.open("r", encoding="utf-8") as f:
                    seed = yaml.safe_load(f)
                identity_seed = seed.get("identity", {})
                name    = identity_seed.get("name", name)
                purpose = identity_seed.get("purpose", purpose)
                if isinstance(purpose, str):
                    purpose = purpose.strip()
            except Exception as e:
                log.warning(f"Cold Start: could not read seed.yaml: {e}")

        self._identity = {
            "name":              name,
            "purpose":           purpose,
            "core_values":       list(_CORE_VALUES),
            "formed_principles": [],
            "version":           1,
        }
        self._history = []
        self._record_history("Инициализация из seed.yaml (Cold Start)")
        self._save()
        log.info(f"SelfModel Cold Start complete. Name='{name}'.")

    def subscribe(self) -> None:
        """Wire EventBus handlers."""
        self._bus.subscribe("self.principle_added", self._on_principle_added)
        log.debug("SelfModel subscribed to self.principle_added.")

    # ────────────────────────────────────────────────────────────
    # Read API
    # ────────────────────────────────────────────────────────────
    def get_identity(self) -> dict:
        return dict(self._identity)

    def get_core_values(self) -> list[str]:
        """Locked — always returns the hardcoded list."""
        return list(_CORE_VALUES)

    def get_principles(self) -> list[str]:
        return list(self._identity["formed_principles"])

    def get_version(self) -> int:
        return self._identity["version"]

    def get_history(self) -> list[dict]:
        return list(self._history)

    # ────────────────────────────────────────────────────────────
    # Write API
    # ────────────────────────────────────────────────────────────
    async def add_principle(self, text: str) -> bool:
        """
        Add a new principle. Deduplicates by exact text.
        Bumps version, records history, saves, publishes self.principle_added.
        Returns True if added, False if duplicate.
        """
        text = text.strip()
        if not text:
            log.warning("[add_principle] Empty text — skipping.")
            return False

        existing = self._identity["formed_principles"]
        if text in existing:
            log.debug(f"[add_principle] Duplicate principle, skipping: '{text[:60]}'")
            return False

        existing.append(text)
        self._bump_version()
        self._record_history(f"Добавлен принцип: {text[:120]}")
        self._save()

        log.info(f"Principle added (v{self.get_version()}): '{text[:80]}'")
        await self._bus.publish("self.principle_added", {
            "text":    text,
            "version": self.get_version(),
        })
        return True

    def merge_principles(self, p1: str, p2: str, merged: str) -> bool:
        """
        Replace two principles with one more precise merged principle.
        Returns True if successful.
        """
        principles = self._identity["formed_principles"]
        if p1 not in principles or p2 not in principles:
            log.warning(
                f"[merge_principles] One or both principles not found. "
                f"p1='{p1[:40]}' p2='{p2[:40]}'"
            )
            return False

        principles.remove(p1)
        principles.remove(p2)
        merged = merged.strip()
        if merged not in principles:
            principles.append(merged)

        self._bump_version()
        self._record_history(
            f"Объединены принципы: ['{p1[:60]}'] + ['{p2[:60]}'] → '{merged[:80]}'"
        )
        self._save()
        log.info(f"Principles merged into: '{merged[:80]}'")
        return True

    def update_purpose(self, new_purpose: str) -> None:
        """
        Update purpose (only via LLM reflection / Dream Mode).
        Bumps version, records history, saves.
        """
        old = self._identity.get("purpose", "")
        new_purpose = new_purpose.strip()
        self._identity["purpose"] = new_purpose
        self._bump_version()
        self._record_history(
            f"Обновлена цель: '{old[:80]}' → '{new_purpose[:80]}'"
        )
        self._save()
        log.info(f"Purpose updated (v{self.get_version()}).")

    # ────────────────────────────────────────────────────────────
    # Prompt context
    # ────────────────────────────────────────────────────────────
    def to_prompt_context(self) -> str:
        """
        Short string block for insertion into an LLM prompt.
        Format:
          Я: Digital Being
          Цель: ...
          Принципы: [...]
          Версия: 3
        """
        principles = self._identity["formed_principles"]
        p_str = ", ".join(principles) if principles else "нет"
        return (
            f"Я: {self._identity['name']}\n"
            f"Цель: {self._identity['purpose'][:200]}\n"
            f"Принципы: [{p_str}]\n"
            f"Версия: {self._identity['version']}"
        )

    # ────────────────────────────────────────────────────────────
    # Drift detection
    # ────────────────────────────────────────────────────────────
    def save_weekly_snapshot(self) -> None:
        """Save current identity snapshot to memory/self_snapshots/YYYY-MM-DD.json."""
        if self._snapshots_dir is None:
            return
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        date_str = time.strftime("%Y-%m-%d")
        out_path = self._snapshots_dir / f"{date_str}.json"
        payload  = {
            "date":    date_str,
            "version": self.get_version(),
            "principles_count": len(self._identity["formed_principles"]),
            "identity": self.get_identity(),
        }
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log.info(f"SelfModel weekly snapshot saved: {out_path.name}")

    async def check_drift(self, value_engine: "ValueEngine | None" = None) -> list[str]:
        """
        Compare current version with snapshot from 7 days ago.
        If version grew by more than _MAX_WEEKLY_VERSION_CHANGE — warn and publish.
        Returns list of warning strings.
        """
        if self._snapshots_dir is None:
            return []

        target_date   = time.strftime(
            "%Y-%m-%d",
            time.localtime(time.time() - 7 * 86400),
        )
        snapshot_path = self._snapshots_dir / f"{target_date}.json"

        if not snapshot_path.exists():
            log.debug(f"[check_drift] No self-snapshot for {target_date}.")
            return []

        try:
            with snapshot_path.open("r", encoding="utf-8") as f:
                past = json.load(f)
            past_version = int(past.get("version", self.get_version()))
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"[check_drift] Could not read snapshot: {e}")
            return []

        delta    = self.get_version() - past_version
        warnings: list[str] = []

        if delta > _MAX_WEEKLY_VERSION_CHANGE:
            msg = (
                f"SELF DRIFT: version grew {past_version} → {self.get_version()} "
                f"(Δ{delta} > max {_MAX_WEEKLY_VERSION_CHANGE}) in 7 days"
            )
            warnings.append(msg)
            log.warning(msg)
            await self._bus.publish("self.drift_detected", {
                "past_version":    past_version,
                "current_version": self.get_version(),
                "delta":           delta,
            })

        return warnings

    # ────────────────────────────────────────────────────────────
    # EventBus handlers
    # ────────────────────────────────────────────────────────────
    async def _on_principle_added(self, data: dict) -> None:
        """Log that a principle was published back through the bus."""
        log.debug(
            f"[self.principle_added received] "
            f"v{data.get('version')} → '{data.get('text', '')[:80]}'"
        )

    # ────────────────────────────────────────────────────────────
    # Internal helpers
    # ────────────────────────────────────────────────────────────
    def _bump_version(self) -> None:
        self._identity["version"] = self._identity.get("version", 1) + 1

    def _record_history(self, change: str) -> None:
        self._history.append({
            "version":   self._identity.get("version", 1),
            "change":    change,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "identity": self._identity,
            "history":  self._history,
        }
        try:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            log.debug(f"SelfModel saved (v{self.get_version()}).")
        except OSError as e:
            log.error(f"SelfModel save failed: {e}")
