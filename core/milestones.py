"""
Digital Being — Milestones
Stage 5: Track achievements.

Each milestone has:
  - name (unique ID)
  - description
  - achieved (bool)
  - timestamp (when achieved)

Data stored in memory/milestones.json.
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

_DEFAULT_MILESTONES: dict = {
    "first_principle":       {"desc": "Сформировал первый принцип",           "achieved": False},
    "first_dream":           {"desc": "Первый сон",                             "achieved": False},
    "first_error_reflection":{"desc": "Рефлексия ошибок",                      "achieved": False},
    "first_diary_entry":     {"desc": "Первая запись в дневнике",              "achieved": False},
    "goal_resumed":          {"desc": "Восстановил цель после restart",         "achieved": False},
    "attention_focused":     {"desc": "Использовал систему внимания",          "achieved": False},
    "first_question":        {"desc": "Сгенерировал первый вопрос",            "achieved": False},
    "first_answer":          {"desc": "Нашёл первый ответ",                    "achieved": False},
    "first_self_mod":        {"desc": "Первое самоизменение",                  "achieved": False},
    "belief_formed":         {"desc": "Сформировал убеждение о мире",          "achieved": False},
    "contradiction_resolved":{"desc": "Разрешил противоречие",                 "achieved": False},
    "first_shell_exec":      {"desc": "Выполнил первую shell-команду",         "achieved": False},
    "first_user_message":    {"desc": "Получил первое сообщение от пользователя", "achieved": False},
    "first_user_reply":      {"desc": "Ответил пользователю",                 "achieved": False},
    "meta_insight":          {"desc": "Осознал паттерн своего мышления",       "achieved": False},
}


class Milestones:
    """
    Track system achievements.

    Usage:
        milestones = Milestones(bus)
        milestones.load(path)
        milestones.achieve("first_principle", "...context...")
    """

    def __init__(self, bus: "EventBus") -> None:
        self._bus   = bus
        self._path: Path | None = None
        self._data: dict = dict(_DEFAULT_MILESTONES)

    # ────────────────────────────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────────────────────────────
    def load(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    stored = json.load(f)
                # Merge defaults + stored (in case we add new milestones)
                for key in _DEFAULT_MILESTONES:
                    if key not in stored:
                        stored[key] = _DEFAULT_MILESTONES[key]
                self._data = stored
                log.info(f"Milestones loaded from {path.name}.")
            except (json.JSONDecodeError, OSError) as e:
                log.error(f"Could not load milestones: {e}. Using defaults.")
        else:
            self._save()
            log.info(f"Milestones initialized from defaults.")

    # ────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────
    def achieve(self, milestone_name: str, context: str = "") -> None:
        """
        Mark a milestone as achieved if it wasn't already.
        Publishes milestone.achieved event.
        """
        if milestone_name not in self._data:
            log.warning(f"[achieve] Unknown milestone: '{milestone_name}'")
            return

        entry = self._data[milestone_name]
        if entry["achieved"]:
            log.debug(f"[achieve] Already achieved: {milestone_name}")
            return

        entry["achieved"]  = True
        entry["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        entry["context"]   = context[:200] if context else ""

        self._save()
        log.info(f"🏆 Milestone achieved: {milestone_name} — {entry['desc']}")

        # Publish event (fire-and-forget)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(
                    self._bus.publish("milestone.achieved", {
                        "name": milestone_name,
                        "desc": entry["desc"],
                        "context": context[:200],
                    })
                )
            )
        except Exception as e:
            log.debug(f"[achieve] Could not publish event: {e}")

    def is_achieved(self, milestone_name: str) -> bool:
        entry = self._data.get(milestone_name)
        return entry["achieved"] if entry else False

    def to_dict(self) -> dict:
        """Return full milestone data for API/introspection."""
        return dict(self._data)

    # ────────────────────────────────────────────────────────────
    # Persistence
    # ────────────────────────────────────────────────────────────
    def _save(self) -> None:
        """Atomically save milestones.json using .tmp + replace()."""
        if self._path is None:
            return
        tmp_path = self._path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self._path)  # atomic
            log.debug("Milestones saved.")
        except OSError as e:
            log.error(f"[_save] Failed to save milestones: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
