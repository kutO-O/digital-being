"""
Digital Being — DreamMode
Stage 11: Added get_state() method for IntrospectionAPI.
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
    "last_run":      "",
    "run_count":     0,
    "last_insights": [],
}

_MIN_EPISODES = 5


class DreamMode:

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

    # ─ Public API ────────────────────────────────────────────────────────
    def should_run(self) -> bool:
        last = self._state.get("last_run", "")
        if not last:
            return True
        try:
            t = time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S"))
            return (time.time() - t) / 3600 >= self._interval_h
        except (ValueError, OverflowError):
            return True

    def get_state(self) -> dict:
        """Return current dream state dict. Stage 11."""
        return dict(self._state)

    def run(self) -> dict:
        log.info("DreamMode: starting run.")
        try:
            return self._run_inner()
        except Exception as e:
            log.error(f"DreamMode: unhandled error in run(): {e}", exc_info=True)
            return {"error": str(e)}

    # ─ Internal cycle ─────────────────────────────────────────────────
    def _run_inner(self) -> dict:
        episodes = self._episodic.get_recent_episodes(20)
        if len(episodes) < _MIN_EPISODES:
            log.info(
                f"DreamMode: only {len(episodes)} episodes — "
                f"minimum {_MIN_EPISODES} required. Skipping."
            )
            self._touch_last_run()
            return {"skipped": True, "reason": "not_enough_episodes"}

        recent_vectors = self._vector_mem.get_recent(10)
        values_summary = self._values.to_prompt_context()
        current_vector = self._strategy.get_longterm().get("vector", "")
        principles     = self._self_model.get_principles()

        episodes_summary = "\n".join(
            f"[{e.get('event_type', '?')}] {e.get('description', '')[:200]}"
            for e in episodes
        )
        principles_str = "\n".join(f"  \u2022 {p}" for p in principles) if principles else "  \u2022 \u043d\u0435\u0442"

        prompt = (
            f"\u0422\u044b \u2014 Digital Being, \u0430\u043d\u0430\u043b\u0438\u0437\u0438\u0440\u0443\u0435\u0448\u044c \u0441\u0432\u043e\u0439 \u043e\u043f\u044b\u0442 \u0437\u0430 \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 \u0447\u0430\u0441\u044b.\n\n"
            f"\u041d\u0435\u0434\u0430\u0432\u043d\u0438\u0435 \u044d\u043f\u0438\u0437\u043e\u0434\u044b (\u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 20):\n{episodes_summary}\n\n"
            f"\u0422\u0435\u043a\u0443\u0449\u0438\u0435 \u0446\u0435\u043d\u043d\u043e\u0441\u0442\u0438:\n{values_summary}\n\n"
            f"\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0432\u0435\u043a\u0442\u043e\u0440 \u0440\u0430\u0437\u0432\u0438\u0442\u0438\u044f: {current_vector}\n\n"
            f"\u041f\u0440\u0438\u043d\u0446\u0438\u043f\u044b:\n{principles_str}\n\n"
            f"\u0417\u0430\u0434\u0430\u0447\u0438:\n"
            f"1. \u0412\u044b\u0434\u0435\u043b\u0438 2-3 \u043a\u043b\u044e\u0447\u0435\u0432\u044b\u0445 \u0438\u043d\u0441\u0430\u0439\u0442\u0430 \u0438\u0437 \u043e\u043f\u044b\u0442\u0430\n"
            f"2. \u041d\u0430\u0439\u0434\u0438 \u043f\u043e\u0432\u0442\u043e\u0440\u044f\u044e\u0449\u0438\u0435\u0441\u044f \u043f\u0430\u0442\u0442\u0435\u0440\u043d\u044b \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f\n"
            f"3. \u041f\u0440\u0435\u0434\u043b\u043e\u0436\u0438 \u043e\u0431\u043d\u043e\u0432\u043b\u0451\u043d\u043d\u044b\u0439 \u0434\u043e\u043b\u0433\u043e\u0441\u0440\u043e\u0447\u043d\u044b\u0439 \u0432\u0435\u043a\u0442\u043e\u0440 (1 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435)\n"
            f"4. \u0415\u0441\u043b\u0438 \u043d\u0443\u0436\u043d\u043e \u2014 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0438 \u043d\u043e\u0432\u044b\u0439 \u043f\u0440\u0438\u043d\u0446\u0438\u043f (1 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0438\u043b\u0438 null)\n\n"
            f"\u041e\u0442\u0432\u0435\u0447\u0430\u0439 \u0441\u0442\u0440\u043e\u0433\u043e JSON \u0431\u0435\u0437 \u043f\u043e\u044f\u0441\u043d\u0435\u043d\u0438\u0439:\n"
            f'{{\n'
            f'  "insights": ["...", "..."],\n'
            f'  "patterns": ["...", "..."],\n'
            f'  "new_vector": "...",\n'
            f'  "new_principle": "..." \u0438\u043b\u0438 null\n'
            f'}}'
        )
        system = (
            "\u0422\u044b \u2014 Digital Being. \u0410\u043d\u0430\u043b\u0438\u0437\u0438\u0440\u0443\u0439 \u0447\u0435\u0441\u0442\u043d\u043e \u0438 \u0433\u043b\u0443\u0431\u043e\u043a\u043e. "
            "\u041e\u0442\u0432\u0435\u0447\u0430\u0439 \u0422\u041e\u041b\u042c\u041a\u041e \u0432\u0430\u043b\u0438\u0434\u043d\u044b\u043c JSON-\u043e\u0431\u044a\u0435\u043a\u0442\u043e\u043c."
        )

        raw      = self._ollama.chat(prompt, system)
        analysis = self._parse_json(raw)

        if not analysis:
            log.warning("DreamMode: LLM returned unparseable response.")
            self._touch_last_run()
            return {"skipped": True, "reason": "llm_parse_error"}

        insights      = analysis.get("insights", []) or []
        new_vector    = (analysis.get("new_vector") or "").strip()
        new_principle = (analysis.get("new_principle") or "").strip()

        vector_updated = False
        if new_vector and new_vector != current_vector:
            self._strategy.update_longterm(new_vector)
            vector_updated = True
            log.info(f"DreamMode: long-term vector updated: '{new_vector[:120]}'")

        principle_added = False
        if new_principle and new_principle.lower() not in ("null", "none", ""):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
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

        for insight in insights[:5]:
            text = str(insight).strip()[:1000]
            if text:
                self._episodic.add_episode("dream_insight", text, outcome="success")

        self._vector_mem.delete_old(days=30)

        self._state["last_run"]      = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._state["run_count"]     = self._state.get("run_count", 0) + 1
        self._state["last_insights"] = [str(i)[:200] for i in insights[:5]]
        self._save_state()

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

    # ─ State persistence ─────────────────────────────────────────────
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
        self._state["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_state()

    # ─ Helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _parse_json(raw: str) -> dict | None:
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
