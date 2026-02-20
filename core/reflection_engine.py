"""
Digital Being — ReflectionEngine
Stage 13: Deep self-analysis every N ticks.

Each time should_run() returns True, run() is called synchronously
(via run_in_executor from HeavyTick) and performs:
  Step 1 — Collect material (episodes, values, conflicts, principles,
            emotions, long-term vector)
  Step 2 — Single LLM call: structured JSON reflection
  Step 3 — Apply results:
            • optionally add new principle to SelfModel
            • write reflection + contradictions to EpisodicMemory
            • update EmotionEngine
            • persist reflection_log.json (max 20 entries)
            • publish reflection.completed event

Design rules:
  - run() is SYNCHRONOUS — always call via loop.run_in_executor
  - run() NEVER raises — all errors are caught and logged
  - reflection_log.json is capped at MAX_LOG_ENTRIES (20)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.emotion_engine import EmotionEngine
    from core.event_bus import EventBus
    from core.memory.episodic import EpisodicMemory
    from core.ollama_client import OllamaClient
    from core.self_model import SelfModel
    from core.strategy_engine import StrategyEngine
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.reflection_engine")

MAX_LOG_ENTRIES = 20

_SYSTEM_PROMPT = (
    "Ты — Digital Being. Автономная система, проводящая глубокую "
    "рефлексию своего поведения. Отвечай только валидным JSON."
)

_USER_PROMPT_TMPL = """\
Ты — Digital Being. Проводишь глубокую рефлексию своего поведения.

Последние действия:
{actions_summary}

Заявленные принципы:
{principles}

Текущие ценности: {values_summary}
Конфликты: {conflicts}
Эмоции: {emotion_context}
Долгосрочный вектор: {longterm_vector}

Вопросы для рефлексии:
1. Есть ли противоречия между моими принципами и реальными действиями?
2. Какие паттерны я замечаю в своём поведении?
3. Что нужно скорректировать?
4. Предложи 1 новый или уточнённый принцип (или null если не нужно)

Отвечай строго JSON:
{{
  "reflection_text": "свободный текст рефлексии (2-3 предложения)",
  "contradictions": ["...", "..."],
  "patterns": ["...", "..."],
  "adjustments": ["...", "..."],
  "new_principle": "..." или null
}}
"""


class ReflectionEngine:
    """
    Periodic deep self-reflection engine.

    Usage (from HeavyTick):
        if reflection_engine.should_run(tick_count):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: reflection_engine.run(tick_count)
            )
    """

    def __init__(
        self,
        episodic:        "EpisodicMemory",
        value_engine:    "ValueEngine",
        self_model:      "SelfModel",
        emotion_engine:  "EmotionEngine",
        strategy_engine: "StrategyEngine",
        ollama:          "OllamaClient",
        event_bus:       "EventBus",
        memory_dir:      Path,
        every_n_ticks:   int = 10,
    ) -> None:
        self._episodic        = episodic
        self._values          = value_engine
        self._self_model      = self_model
        self._emotions        = emotion_engine
        self._strategy        = strategy_engine
        self._ollama          = ollama
        self._bus             = event_bus
        self._memory_dir      = Path(memory_dir)
        self._every_n         = max(1, every_n_ticks)
        self._log_path        = self._memory_dir / "reflection_log.json"

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    def should_run(self, tick_count: int) -> bool:
        """Return True if a deep reflection should run on this tick."""
        return tick_count > 0 and tick_count % self._every_n == 0

    def run(self, tick_count: int) -> dict:
        """
        Execute a full reflection cycle synchronously.
        NEVER raises — all exceptions are caught and logged.
        Returns dict with keys: contradictions, adjustments, reflection_text.
        """
        log.info(f"[ReflectionEngine] Starting reflection at tick #{tick_count}.")
        try:
            return self._run_internal(tick_count)
        except Exception as e:
            log.error(f"[ReflectionEngine] Unexpected error: {e}")
            return {
                "reflection_text": "Рефлексия не удалась",
                "contradictions": [],
                "adjustments": [],
            }

    # ──────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────
    def _run_internal(self, tick_count: int) -> dict:
        # ── Step 1: Collect material ───────────────────────────────
        episodes  = self._episodic.get_recent_episodes(10) or []
        values    = self._values.get_scores()
        conflicts = self._values.get_conflicts()
        principles = self._self_model.get_principles()
        emotion_ctx = (
            self._emotions.to_prompt_context()
            if self._emotions is not None else ""
        )
        longterm_data = self._strategy.get_longterm() if self._strategy else {}
        longterm_vector = longterm_data.get("vector", "не определён")

        # Format materials for the prompt
        actions_summary = self._format_episodes(episodes)
        principles_text = self._format_principles(principles)
        values_summary  = self._format_values(values)
        conflicts_text  = json.dumps(conflicts, ensure_ascii=False) if conflicts else "нет"

        # ── Step 2: LLM reflection ────────────────────────────────
        prompt = _USER_PROMPT_TMPL.format(
            actions_summary=actions_summary,
            principles=principles_text,
            values_summary=values_summary,
            conflicts=conflicts_text,
            emotion_context=emotion_ctx or "нет данных",
            longterm_vector=longterm_vector,
        )

        parsed = self._call_llm(prompt)

        reflection_text = parsed.get("reflection_text", "Рефлексия не удалась")
        contradictions  = self._ensure_list(parsed.get("contradictions", []))
        adjustments     = self._ensure_list(parsed.get("adjustments",    []))
        new_principle   = parsed.get("new_principle")  # str or None

        # ── Step 3: Apply results ─────────────────────────────────
        # 3a. Add new principle if provided
        if new_principle and isinstance(new_principle, str):
            new_principle = new_principle.strip()
            if new_principle:
                try:
                    self._self_model.add_principle(new_principle[:500])
                    log.info(
                        f"[ReflectionEngine] New principle added: "
                        f"'{new_principle[:80]}'"
                    )
                except Exception as e:
                    log.error(f"[ReflectionEngine] add_principle() failed: {e}")

        # 3b. Write reflection to EpisodicMemory
        try:
            self._episodic.add_episode(
                "reflection",
                reflection_text[:1000],
                outcome="success",
                data={"tick": tick_count},
            )
        except Exception as e:
            log.error(f"[ReflectionEngine] episodic.add_episode(reflection) failed: {e}")

        # 3c. Write each contradiction to EpisodicMemory
        for contradiction in contradictions:
            try:
                self._episodic.add_episode(
                    "contradiction",
                    str(contradiction)[:1000],
                    outcome="warning",
                    data={"tick": tick_count},
                )
            except Exception as e:
                log.error(f"[ReflectionEngine] episodic.add_episode(contradiction) failed: {e}")

        # 3d. Update EmotionEngine
        try:
            if self._emotions is not None:
                outcome_label = "success" if not contradictions else "neutral"
                self._emotions.update(
                    event_type="reflect",
                    outcome=outcome_label,
                    value_scores=(
                        self._values.get_scores()
                        if hasattr(self._values, "get_scores") else {}
                    ),
                )
        except Exception as e:
            log.error(f"[ReflectionEngine] emotion_engine.update() failed: {e}")

        # 3e. Persist reflection_log.json
        self._save_log_entry(
            tick=tick_count,
            reflection_text=reflection_text,
            contradictions_count=len(contradictions),
            adjustments_count=len(adjustments),
        )

        # 3f. Publish event
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(
                    self._bus.publish(
                        "reflection.completed",
                        {
                            "tick":           tick_count,
                            "contradictions": len(contradictions),
                        },
                    )
                )
            )
        except Exception as e:
            log.error(f"[ReflectionEngine] publish reflection.completed failed: {e}")

        log.info(
            f"[ReflectionEngine] Done. "
            f"contradictions={len(contradictions)} "
            f"adjustments={len(adjustments)} "
            f"new_principle={'yes' if new_principle else 'no'}"
        )

        return {
            "reflection_text": reflection_text,
            "contradictions":  contradictions,
            "adjustments":     adjustments,
        }

    # ──────────────────────────────────────────────────────────────
    # LLM call
    # ──────────────────────────────────────────────────────────────
    def _call_llm(self, prompt: str) -> dict:
        """Call OllamaClient, parse JSON. Returns empty dict on any failure."""
        try:
            raw = self._ollama.chat(prompt, _SYSTEM_PROMPT)
        except Exception as e:
            log.error(f"[ReflectionEngine] LLM call failed: {e}")
            return {}

        if not raw:
            log.warning("[ReflectionEngine] LLM returned empty response.")
            return {}

        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Fallback: extract first {...} block
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start: end + 1])
            except json.JSONDecodeError:
                pass

        log.warning("[ReflectionEngine] Could not parse LLM JSON response.")
        return {}

    # ──────────────────────────────────────────────────────────────
    # Reflection log (memory/reflection_log.json)
    # ──────────────────────────────────────────────────────────────
    def _save_log_entry(
        self,
        tick:                 int,
        reflection_text:      str,
        contradictions_count: int,
        adjustments_count:    int,
    ) -> None:
        """Append entry to reflection_log.json, keeping max MAX_LOG_ENTRIES."""
        entry: dict[str, Any] = {
            "tick":                 tick,
            "timestamp":            time.strftime("%Y-%m-%dT%H:%M:%S"),
            "reflection_text":      reflection_text,
            "contradictions_count": contradictions_count,
            "adjustments_count":    adjustments_count,
        }
        try:
            self._memory_dir.mkdir(parents=True, exist_ok=True)
            log_data: list = []
            if self._log_path.exists():
                try:
                    log_data = json.loads(self._log_path.read_text(encoding="utf-8"))
                    if not isinstance(log_data, list):
                        log_data = []
                except (json.JSONDecodeError, OSError):
                    log_data = []

            log_data.append(entry)

            # Keep only the last MAX_LOG_ENTRIES
            if len(log_data) > MAX_LOG_ENTRIES:
                log_data = log_data[-MAX_LOG_ENTRIES:]

            self._log_path.write_text(
                json.dumps(log_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.error(f"[ReflectionEngine] Failed to save reflection log: {e}")

    def load_log(self) -> list:
        """Return the full reflection log (list of dicts). Empty list on error."""
        try:
            if not self._log_path.exists():
                return []
            data = json.loads(self._log_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception as e:
            log.error(f"[ReflectionEngine] Failed to read reflection log: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Prompt formatting helpers
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _format_episodes(episodes: list) -> str:
        if not episodes:
            return "нет данных"
        lines = []
        for ep in episodes:
            event_type  = ep.get("event_type", "?")
            outcome     = ep.get("outcome",    "?")
            description = ep.get("description", "")[:150]
            lines.append(f"{event_type} \u2192 {outcome}: {description}")
        return "\n".join(lines)

    @staticmethod
    def _format_principles(principles: list) -> str:
        if not principles:
            return "принципы ещё не сформированы"
        lines = []
        for p in principles:
            # principles may be strings or dicts with 'text' key
            if isinstance(p, dict):
                text = p.get("text", str(p))
            else:
                text = str(p)
            lines.append(f"\u2022 {text}")
        return "\n".join(lines)

    @staticmethod
    def _format_values(scores: dict) -> str:
        if not scores:
            return "нет данных"
        parts = [f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
                 for k, v in scores.items()]
        return ", ".join(parts)

    @staticmethod
    def _ensure_list(value: Any) -> list:
        if isinstance(value, list):
            return [str(x) for x in value if x]
        return []
