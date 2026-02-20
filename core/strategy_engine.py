"""
Digital Being — StrategyEngine
Stage 9: select_goal() accepts optional semantic_ctx for richer LLM context.
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
    from core.ollama_client import OllamaClient
    from core.value_engine import ValueEngine
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.strategy")

_DEFAULT_LONGTERM = "Исследовать среду, накапливать знания, развиваться"
_DEFAULT_WEEKLY   = "Наблюдать и изучать файловую структуру"

_DEFAULT_STRATEGY: dict = {
    "now": {
        "goal":        "наблюдать за средой",
        "action_type": "observe",
        "created_at":  "",
    },
    "weekly": {
        "direction":  _DEFAULT_WEEKLY,
        "updated_at": "",
    },
    "longterm": {
        "vector":     _DEFAULT_LONGTERM,
        "formed_at":  "",
        "updated_at": "",
    },
}

_NOVELTY_RULES: dict[str, tuple[int, str]] = {
    "observe": (5, "analyze"),
    "write":   (3, "reflect"),
}

_SAFE_GOAL: dict = {
    "goal":        "наблюдать за средой",
    "reasoning":   "стратегия недоступна — используется дефолт",
    "action_type": "observe",
    "risk_level":  "low",
}


class StrategyEngine:

    def __init__(self, memory_dir: Path, event_bus: "EventBus | None" = None) -> None:
        self._path      = memory_dir / "strategy.json"
        self._bus       = event_bus
        self._data: dict = {}

    # ─ Lifecycle ───────────────────────────────────────────────────────────
    def load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            try:
                with self._path.open(encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = self._deep_merge(_DEFAULT_STRATEGY, loaded)
                log.info(f"StrategyEngine loaded from {self._path}")
                return
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"StrategyEngine: could not read {self._path}: {e}. Using defaults.")
        ts = self._now()
        self._data = json.loads(json.dumps(_DEFAULT_STRATEGY))
        self._data["now"]["created_at"]     = ts
        self._data["weekly"]["updated_at"]   = ts
        self._data["longterm"]["formed_at"]  = ts
        self._data["longterm"]["updated_at"] = ts
        self._save()
        log.info("StrategyEngine: cold start — defaults written.")

    def _save(self) -> None:
        try:
            tmp = self._path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            tmp.replace(self._path)
        except OSError as e:
            log.error(f"StrategyEngine: failed to save: {e}")

    # ─ NOW ───────────────────────────────────────────────────────────────
    def set_now(self, goal: str, action_type: str) -> None:
        self._data["now"] = {"goal": goal, "action_type": action_type, "created_at": self._now()}
        self._save()

    def get_now(self) -> dict:
        return dict(self._data.get("now", _DEFAULT_STRATEGY["now"]))

    # ─ WEEKLY ───────────────────────────────────────────────────────────
    def update_weekly(self, direction: str) -> None:
        self._data["weekly"] = {"direction": direction, "updated_at": self._now()}
        self._save()
        log.info(f"Weekly direction updated: '{direction[:120]}'")

    def get_weekly(self) -> dict:
        return dict(self._data.get("weekly", _DEFAULT_STRATEGY["weekly"]))

    def should_update_weekly(self) -> bool:
        return self._hours_since(self._data.get("weekly", {}).get("updated_at", "")) >= 24

    # ─ LONGTERM ─────────────────────────────────────────────────────────
    def update_longterm(self, vector: str) -> None:
        now = self._now()
        if not self._data["longterm"].get("formed_at"):
            self._data["longterm"]["formed_at"] = now
        self._data["longterm"]["vector"]     = vector
        self._data["longterm"]["updated_at"] = now
        self._save()
        log.info(f"Long-term vector updated: '{vector[:120]}'")
        if self._bus is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self._bus.publish("strategy.vector_changed", {"vector": vector})
                )
            except RuntimeError:
                pass

    def get_longterm(self) -> dict:
        return dict(self._data.get("longterm", _DEFAULT_STRATEGY["longterm"]))

    def should_update_longterm(self) -> bool:
        return self._hours_since(self._data.get("longterm", {}).get("updated_at", "")) >= 24 * 7

    # ─ LLM context ──────────────────────────────────────────────────────
    def to_prompt_context(self) -> str:
        weekly   = self._data.get("weekly",   {}).get("direction", _DEFAULT_WEEKLY)
        longterm = self._data.get("longterm", {}).get("vector",    _DEFAULT_LONGTERM)
        return (
            f"Недельное направление: {weekly}\n"
            f"Долгосрочный вектор: {longterm}"
        )

    # ─ Goal selection ───────────────────────────────────────────────────
    async def select_goal(
        self,
        value_engine: "ValueEngine",
        world_model:  "WorldModel",
        episodic:     "EpisodicMemory",
        ollama:       "OllamaClient",
        semantic_ctx: str = "",          # Stage 9: injected by HeavyTick
    ) -> dict:
        """
        Select next goal. Max 1 LLM call.
        semantic_ctx: formatted string from VectorMemory search.
        """
        try:
            forced_type = self._apply_novelty(episodic)
            mode        = value_engine.get_mode()
            c_expl      = value_engine.get_conflict_winner("exploration_vs_stability")
            c_act       = value_engine.get_conflict_winner(
                "action_vs_caution",
                risk_score=0.25 if mode in ("curious", "normal") else 0.5,
            )

            force_note = (
                f"\nВАЖНО: из-за низкой новизны ОБЯЗАТЕЛЬНО используй "
                f'action_type="{forced_type}".' if forced_type else ""
            )
            sem_block = f"\n{semantic_ctx}\n" if semantic_ctx else ""

            prompt = (
                f"{self.to_prompt_context()}\n"
                f"{sem_block}"
                f"Текущий режим: {mode}\n"
                f"Конфликты: exploration_vs_stability={c_expl}, action_vs_caution={c_act}\n"
                f"{force_note}\n"
                f"Выбери ONE цель. JSON:\n"
                f'{{"goal": "...", "reasoning": "...", '
                f'"action_type": "observe|analyze|write|reflect", '
                f'"risk_level": "low|medium|high"}}'
            )
            system = (
                "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON-объектом."
            )

            loop = asyncio.get_event_loop()
            raw  = await loop.run_in_executor(None, lambda: ollama.chat(prompt, system))
            goal = self._parse_goal_json(raw)

            if forced_type and goal.get("action_type") in ("observe", "write"):
                log.info(
                    f"Novelty enforcement: LLM chose '{goal['action_type']}' "
                    f"but forcing '{forced_type}'."
                )
                goal["action_type"] = forced_type

            return goal

        except Exception as e:
            log.error(f"select_goal failed: {e}")
            return dict(_SAFE_GOAL)

    # ─ Novelty ──────────────────────────────────────────────────────────
    def _apply_novelty(self, episodic: "EpisodicMemory") -> str | None:
        for action_type, (max_count, forced) in _NOVELTY_RULES.items():
            count = episodic.count_recent_similar(f"heavy_tick.{action_type}", hours=2)
            if count > max_count:
                log.info(
                    f"Novelty enforcement: '{action_type}' appeared {count}x "
                    f"in 2h (max {max_count}) — switching to '{forced}'."
                )
                return forced
        return None

    # ─ Helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _parse_goal_json(raw: str) -> dict:
        if not raw:
            return dict(_SAFE_GOAL)
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
        log.warning("StrategyEngine: could not parse LLM goal JSON. Using default.")
        return dict(_SAFE_GOAL)

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _hours_since(ts_str: str) -> float:
        if not ts_str:
            return float("inf")
        try:
            t = time.mktime(time.strptime(ts_str, "%Y-%m-%dT%H:%M:%S"))
            return (time.time() - t) / 3600
        except (ValueError, OverflowError):
            return float("inf")

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = json.loads(json.dumps(base))
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = StrategyEngine._deep_merge(result[k], v)
            else:
                result[k] = v
        return result
