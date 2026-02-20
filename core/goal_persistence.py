"""
Digital Being — GoalPersistence
Stage 15: Goal Persistence + Recovery.

Responsibilities:
  - Persist the active goal to disk (memory/goal_state.json) atomically.
  - Detect interruptions on restart and provide resume context for LLM.
  - Track total completed goals and resume count for analytics.

All file writes are atomic: write to tmp → os.replace.
Thread-safe for normal use (no concurrent writers expected).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.goal_persistence")

_EMPTY_STATE: dict = {
    "active_goal": None,
    "interrupted_at": None,
    "resume_count": 0,
    "total_goals_completed": 0,
}


class GoalPersistence:
    """
    Persists the current active goal and recovers it on restart.

    Usage::

        gp = GoalPersistence(memory_dir=Path("memory"))
        gp.load()

        if gp.was_interrupted():
            log.info(gp.get_resume_context())

        gp.set_active(goal_dict, tick=1)
        # ... action ...
        gp.mark_completed(tick=1)

        # On shutdown:
        gp.mark_interrupted()
    """

    def __init__(self, memory_dir: Path) -> None:
        self._path  = memory_dir / "goal_state.json"
        self._state: dict = dict(_EMPTY_STATE)

    # ──────────────────────────────────────────────────────────────
    # Load / Save
    # ──────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load state from disk.
        Creates an empty state file if none exists.
        """
        if not self._path.exists():
            log.info("GoalPersistence: no state file found — starting fresh.")
            self._state = dict(_EMPTY_STATE)
            self._save()
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            # Merge with defaults so new keys never cause KeyError
            self._state = {**_EMPTY_STATE, **data}
            log.info(
                "GoalPersistence: loaded. "
                f"interrupted_at={self._state.get('interrupted_at')} "
                f"total_completed={self._state.get('total_goals_completed')} "
                f"resume_count={self._state.get('resume_count')}"
            )
        except Exception as e:
            log.error(f"GoalPersistence: failed to load state — {e}. Starting fresh.")
            self._state = dict(_EMPTY_STATE)

    def _save(self) -> None:
        """
        Atomic write: goal_state.json.tmp → goal_state.json.
        Must be fast and reliable — called from shutdown handler.
        """
        tmp = self._path.with_suffix(".json.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self._path)
        except Exception as e:
            log.error(f"GoalPersistence: failed to save state — {e}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────
    # Write API
    # ──────────────────────────────────────────────────────────────

    def set_active(self, goal: dict, tick: int) -> None:
        """
        Persist `goal` as the current active goal.

        Requires `goal` to contain a ``"goal"`` key (string description).
        Logs a warning and returns without saving if the key is missing.
        """
        if "goal" not in goal:
            log.warning(
                "GoalPersistence.set_active(): goal dict has no 'goal' key — skipping save."
            )
            return

        entry: dict[str, Any] = {
            "goal":        goal["goal"],
            "action_type": goal.get("action_type", "observe"),
            "risk_level":  goal.get("risk_level",  "low"),
            "started_at":  _now_iso(),
            "tick_started": tick,
            "status":      "active",
        }
        self._state["active_goal"]    = entry
        self._state["interrupted_at"] = None   # clear previous interruption mark
        self._save()
        log.debug(f"GoalPersistence: active goal set → '{goal['goal'][:80]}' tick={tick}")

    def mark_completed(self, tick: int) -> None:
        """
        Mark the active goal as completed.
        Increments total_goals_completed and clears interrupted_at.
        """
        ag = self._state.get("active_goal")
        if ag is None:
            log.debug("GoalPersistence.mark_completed(): no active goal to complete.")
            return

        ag["status"]       = "completed"
        ag["completed_at"] = _now_iso()
        ag["tick_ended"]   = tick

        self._state["total_goals_completed"] = (
            self._state.get("total_goals_completed", 0) + 1
        )
        self._state["interrupted_at"] = None
        self._save()
        log.debug(
            f"GoalPersistence: goal completed. "
            f"total={self._state['total_goals_completed']}"
        )

    def mark_interrupted(self) -> None:
        """
        Mark the current goal as interrupted (called in shutdown handler).
        Designed to be fast and safe — never raises.
        """
        try:
            ag = self._state.get("active_goal")
            if ag is None:
                return                          # nothing active — nothing to mark

            if ag.get("status") == "completed":
                return                          # already finished cleanly

            ts = _now_iso()
            ag["status"]                 = "interrupted"
            self._state["interrupted_at"] = ts
            self._save()
            log.info(
                f"GoalPersistence: marked interrupted at {ts}. "
                f"Goal: '{ag.get('goal','?')[:80]}'"
            )
        except Exception as e:
            # shutdown context — log but never re-raise
            log.error(f"GoalPersistence.mark_interrupted(): {e}")

    def increment_resume(self) -> None:
        """Increment the resume counter (called once after first recovery tick)."""
        self._state["resume_count"] = self._state.get("resume_count", 0) + 1
        self._save()
        log.debug(f"GoalPersistence: resume_count={self._state['resume_count']}")

    # ──────────────────────────────────────────────────────────────
    # Read API
    # ──────────────────────────────────────────────────────────────

    def get_active(self) -> dict | None:
        """
        Return the active goal dict if its status is 'active' or 'interrupted'.
        Returns None otherwise.
        """
        ag = self._state.get("active_goal")
        if ag is None:
            return None
        if ag.get("status") in ("active", "interrupted"):
            return ag
        return None

    def was_interrupted(self) -> bool:
        """
        Return True if the last stored goal status is 'interrupted'.
        Returns False if active_goal is None.
        """
        ag = self._state.get("active_goal")
        if ag is None:
            return False
        return ag.get("status") == "interrupted"

    def get_resume_context(self) -> str:
        """
        Build a Russian-language prompt fragment for LLM goal selection
        when the system is recovering from an interruption.

        Only call this when was_interrupted() == True.
        """
        ag = self._state.get("active_goal")
        if ag is None:
            return ""

        interrupted_at = self._state.get("interrupted_at") or ag.get("started_at", "неизвестно")
        return (
            f"ВАЖНО: Система была прервана. "
            f"Последняя цель: \"{ag.get('goal', '?')}\""
            f" (action_type={ag.get('action_type', '?')},"
            f" прервана в {interrupted_at}).\n"
            f"Реши: продолжить эту цель или выбрать новую?"
        )

    def get_stats(self) -> dict:
        """Return analytics snapshot for IntrospectionAPI."""
        return {
            "total_completed": self._state.get("total_goals_completed", 0),
            "resume_count":    self._state.get("resume_count", 0),
            "interrupted":     self.was_interrupted(),
        }


# ──────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string without microseconds."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
