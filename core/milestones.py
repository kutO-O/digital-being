"""
Digital Being — Milestones
Stage 11: Added get_achieved() and get_pending() for IntrospectionAPI.
API Fix: Added to_dict() method for compatibility.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.event_bus import EventBus

log = logging.getLogger("digital_being.milestones")

_PREDEFINED: list[str] = [
    "first_principle",
    "first_autonomous_action",
    "first_disagreement",
    "first_error_reflection",
    "first_vector_change",
]


class Milestones:

    def __init__(self, bus: "EventBus") -> None:
        self._bus  = bus
        self._path: Path | None = None
        self._data: dict[str, dict | None] = {
            name: None for name in _PREDEFINED
        }

    # ─ Lifecycle ──────────────────────────────────────────────────────────
    def load(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    saved = json.load(f)
                for name in _PREDEFINED:
                    if name in saved:
                        self._data[name] = saved[name]
                achieved = sum(1 for v in self._data.values() if v is not None)
                log.info(f"Milestones loaded: {achieved}/{len(_PREDEFINED)} achieved.")
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Milestones load failed: {e}. Starting fresh.")
        else:
            self._save()
            log.info("Milestones file created (all milestones pending).")

    def subscribe(self) -> None:
        self._bus.subscribe("self.principle_added", self._on_principle_added)
        log.debug("Milestones subscribed to self.principle_added.")

    # ─ Core API ─────────────────────────────────────────────────────────
    def achieve(self, milestone_name: str, description: str) -> bool:
        if milestone_name not in self._data:
            log.debug(f"[achieve] Unknown milestone: '{milestone_name}'")
            return False
        if self._data[milestone_name] is not None:
            log.debug(f"[achieve] Already achieved: '{milestone_name}'")
            return False
        self._data[milestone_name] = {
            "achieved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "description": description,
        }
        self._save()
        log.info(f"★ MILESTONE: '{milestone_name}' — {description}")
        return True

    def is_achieved(self, milestone_name: str) -> bool:
        return self._data.get(milestone_name) is not None

    def get_all(self) -> dict:
        result = {}
        for name, record in self._data.items():
            result[name] = {"achieved": record is not None, "detail": record}
        return result

    def to_dict(self) -> dict:
        """Return full milestone data in dict format for API."""
        achieved = sum(1 for v in self._data.values() if v is not None)
        return {
            "achieved": self.get_achieved(),
            "pending": self.get_pending(),
            "total": len(_PREDEFINED),
            "achieved_count": achieved,
            "progress": achieved / len(_PREDEFINED) if _PREDEFINED else 0.0,
        }

    def get_achieved(self) -> list[dict]:
        """Return list of achieved milestones with detail. Stage 11."""
        return [
            {"name": name, **record}
            for name, record in self._data.items()
            if record is not None
        ]

    def get_pending(self) -> list[str]:
        """Return list of milestone names not yet achieved. Stage 11."""
        return [name for name, record in self._data.items() if record is None]

    def summary(self) -> str:
        achieved = sum(1 for v in self._data.values() if v is not None)
        return f"milestones={achieved}/{len(_PREDEFINED)}"

    # ─ EventBus ─────────────────────────────────────────────────────────
    async def _on_principle_added(self, data: dict) -> None:
        text = data.get("text", "")
        self.achieve(
            "first_principle",
            f"Первый принцип сформирован: '{text[:80]}'",
        )

    # ─ Persistence ────────────────────────────────────────────────────────
    def _save(self) -> None:
        if self._path is None:
            return
        try:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.error(f"Milestones save failed: {e}")
