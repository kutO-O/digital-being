"""
Digital Being — DreamMode
Stage 10: Periodic introspection cycle.

Runs every `interval_hours` (default 6) when the system is not busy.
Analyses recent episodes, finds patterns, updates the long-term vector
and optionally adds a new principle.

Design rules:
  - run() is SYNCHRONOUS — called via run_in_executor from the async loop
  - All errors are caught and logged; Dream Mode never crashes the system
  - Skips silently if fewer than 5 episodes exist
  - State persisted to memory/dream_state.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.ollama_client import OllamaClient
    from core.self_model import SelfModel
    from core.strategy_engine import StrategyEngine
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.dream_mode")

_DEFAULT_STATE: dict = {
    "last_run":     "",
    "run_count":    0,
    "last_insights": [],
}

_MIN_EPISODES = 5   # skip Dream if fewer episodes exist


class DreamMode:
    """
    Periodic introspection: analyse experience, update long-term vector.

    Lifecycle:
        dm = DreamMode(episodic, vector_memory, strategy, values, self_model,
                       ollama, event_bus, memory_dir, interval_hours)
        # In async loop:
        if dm.should_run():
            await loop.run_in_executor(None, dm.run)
    """

    def __init__(
        self,
        episodic:       "EpisodicMemory",
        vector_memory:  "VectorMemory",
        strategy:       "StrategyEngine",
        values:         "ValueEngine",
        self_model:     "SelfModel",
        ollama:         "OllamaClient",
        event_bus:      "EventBus",
        memory_dir:     Path,
        interval_hours: float = 6.0,
    ) -> None:
        self._episodic      = episodic
        self._vector_mem    = vector_memory
        self._strategy      = strategy
        self._values        = values
        self._self_model    = self_model
        self._ollama        = ollama
        self._bus           = event_bus
        self._state_path    = memory_dir / "dream_state.json"
        self._interval_h    = interval_hours
        self._state: dict   = {}
        self._load_state()

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    def should_run(self) -> bool:
        """True if interval_hours have passed since last run (or never ran)."""
        last = self._state.get("last_run", "")
        if not last:
            return True
        try:
            t = time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S"))
            return (time.time() - t) / 3600 >= self._interval_h
        except (ValueError, OverflowError):
            return True

    def run(self) -> dict:
        """
        Full Dream cycle. SYNCHRONOUS — call via run_in_executor.
        Returns result dict. Never raises.
        """
        log.info("DreamMode: starting run.")
        try:
            return self._run_inner()
        except Exception as e:
            log.error(f"DreamMode: unhandled error in run(): {e}", exc_info=True)
            return {"error": str(e)}

    # ──────────────────────────────────────────────────────────────
    # Internal cycle
    # ──────────────────────────────────────────────────────────────
    def _run_inner(self) -> dict:
        # ─ Step 1: Collect material ─────────────────────────────
        episodes = self._episodic.get_recent_episodes(20)

        if len(episodes) < _MIN_EPISODES:
            log.info(
                f"DreamMode: only {len(episodes)} episodes — "
                f"minimum {_MIN_EPISODES} required. Skipping."
            )
            self._touch_last_run()   # prevent immediate re-check
            return {"skipped": True, "reason": "not_enough_episodes"}

        recent_vectors  = self._vector_mem.get_recent(10)
        values_summary  = self._values.to_prompt_context()
        current_vector  = self._strategy.get_longterm().get("vector", "")
        principles      = self._self_model.get_principles()

        # ─ Step 2: Build prompt ──────────────────────────────
        episodes_summary = "\n".join(
            f"[{e.get('event_type','?')}] {e.get('description','')[:200]}"
            for e in episodes
        )
        principles_str = "\n".join(f"  • {p}" for p in principles) if principles else "  • нет"

        prompt = (
            f"Ты — Digital Being, анализируешь свой опыт за последние часы.\n\n"
            f"Недавние эпизоды (последние 20):\n{episodes_summary}\n\n"
            f"Текущие ценности:\n{values_summary}\n\n"
            f"Текущий вектор развития: {current_vector}\n\n"
            f"Принципы:\n{principles_str}\n\n"
            f"Задачи:\n"
            f"1. Выдели 2-3 ключевых инсайта из опыта\n"
            f"2. Найди повторяющиеся паттерны поведения\n"
            f"3. Предложи обновлённый долгосрочный вектор (1 предложение)\n"
            f"4. Если нужно — предложи новый принцип (1 предложение или null)\n\n"
            f"Отвечай строго JSON без пояснений:\n"
            f'{{\n'
            f'  "insights": ["...", "..."],\n'
            f'  "patterns": ["...", "..."],\n'
            f'  "new_vector": "...",\n'
            f'  "new_principle": "..." \u0438\u043b\u0438 null\n'
            f'}}'
        )
        system = (
            "Ты — Digital Being. Анализируй честно и глубоко. "
            "Отвечай ТОЛЬКО валидным JSON-объектом."
        )

        raw = self._ollama.chat(prompt, system)
        analysis = self._parse_json(raw)

        if not analysis:
            log.warning("DreamMode: LLM returned unparseable response.")
            self._touch_last_run()
            return {"skipped": True, "reason": "llm_parse_error"}

        insights      = analysis.get("insights", []) or []
        new_vector    = (analysis.get("new_vector") or "").strip()
        new_principle = (analysis.get("new_principle") or "").strip()

        # ─ Step 3: Apply results ────────────────────────────
        vector_updated = False
        if new_vector and new_vector != current_vector:
            self._strategy.update_longterm(new_vector)
            vector_updated = True
            log.info(f"DreamMode: long-term vector updated: '{new_vector[:120]}'")

        principle_added = False
        if new_principle and new_principle.lower() not in ("null", "none", ""):
            # add_principle is async — run via asyncio in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside run_in_executor — schedule as future
                    future = asyncio.run_coroutine_threadsafe(
                        self._self_model.add_principle(new_principle[:500]),
                        loop,
                    )
                    principle_added = future.result(timeout=5)
                else:
                    principle_added = loop.run_until_complete(
                        self._self_model.add_principle(new_principle[:500])
                    )
            except Exception as e:
                log.warning(f"DreamMode: add_principle failed: {e}")

        # Save insights to EpisodicMemory
        for insight in insights[:5]:   # cap at 5
            text = str(insight).strip()[:1000]
            if text:
                self._episodic.add_episode(
                    "dream_insight",
                    text,
                    outcome="success",
                )

        # Vector DB maintenance
        self._vector_mem.delete_old(days=30)

        # ─ Step 4: Save state ──────────────────────────────
        self._state["last_run"]      = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._state["run_count"]     = self._state.get("run_count", 0) + 1
        self._state["last_insights"] = [str(i)[:200] for i in insights[:5]]
        self._save_state()

        # Publish event (fire-and-forget from sync context)
        self._publish_completed(
            insights_count=len(insights),
            vector_updated=vector_updated,
            principle_added=principle_added,
        )

        result = {
            "insights":           insights,
            "patterns":           analysis.get("patterns", []),
            "vector_updated":     vector_updated,
            "principle_added":    principle_added,
            "episodes_processed": len(episodes),
            "run_count":          self._state["run_count"],
        }
        log.info(
            f"DreamMode: completed. "
            f"insights={len(insights)} "
            f"vector_updated={vector_updated} "
            f"principle_added={principle_added}"
        )
        return result

    # ──────────────────────────────────────────────────────────────
    # State persistence
    # ──────────────────────────────────────────────────────────────
    def _load_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        if self._state_path.exists():
            try:
                with self._state_path.open(encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info(
                    f"DreamMode state loaded. "
                    f"run_count={self._state.get('run_count', 0)} "
                    f"last_run='{self._state.get('last_run', 'never')}'"
                )
                return
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"DreamMode: could not load state: {e}. Using defaults.")
        self._state = dict(_DEFAULT_STATE)

    def _save_state(self) -> None:
        try:
            tmp = self._state_path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            tmp.replace(self._state_path)
            log.debug("DreamMode: state saved.")
        except OSError as e:
            log.error(f"DreamMode: failed to save state: {e}")

    def _touch_last_run(self) -> None:
        """Update last_run without incrementing run_count (skipped run)."""
        self._state["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_state()

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        """Tolerant JSON parser. Returns None on failure."""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None

    def _publish_completed(self, insights_count: int, vector_updated: bool, principle_added: bool) -> None:
        """Fire-and-forget event publish from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._bus.publish("dream.completed", {
                        "insights_count":  insights_count,
                        "vector_updated":  vector_updated,
                        "principle_added": principle_added,
                        "run_count":       self._state.get("run_count", 0),
                    }),
                    loop,
                )
        except Exception as e:
            log.debug(f"DreamMode: could not publish dream.completed: {e}")
