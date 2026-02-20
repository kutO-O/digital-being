"""
Digital Being — NarrativeEngine
Stage 14: Diary / first-person narrative written every N ticks.

Files produced:
  memory/diary.md          — append-only Markdown diary
  memory/narrative_log.json — last 30 entries as JSON list

Publishes:
  narrative.entry_written  {"tick": N}
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.emotion_engine import EmotionEngine
    from core.memory.episodic import EpisodicMemory
    from core.ollama_client import OllamaClient
    from core.self_model import SelfModel
    from core.strategy_engine import StrategyEngine

log = logging.getLogger("digital_being.narrative_engine")

_MAX_LOG_ENTRIES = 30


class NarrativeEngine:
    """
    Every *every_n_ticks* ticks generates a short first-person diary entry
    via LLM and persists it to disk.

    All I/O is synchronous — designed to run inside run_in_executor.
    The public run() method never raises; all errors are logged.
    """

    def __init__(
        self,
        episodic:        "EpisodicMemory",
        emotion_engine:  "EmotionEngine",
        strategy_engine: "StrategyEngine",
        self_model:      "SelfModel",
        ollama:          "OllamaClient",
        memory_dir:      Path,
        every_n_ticks:   int = 15,
        event_bus=None,
    ) -> None:
        self._episodic   = episodic
        self._emotions   = emotion_engine
        self._strategy   = strategy_engine
        self._self_model = self_model
        self._ollama     = ollama
        self._memory_dir = Path(memory_dir)
        self._every_n    = every_n_ticks
        self._bus        = event_bus

        self._diary_path = self._memory_dir / "diary.md"
        self._log_path   = self._memory_dir / "narrative_log.json"

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    def should_run(self, tick_count: int) -> bool:
        """True when it is time to write a diary entry."""
        return tick_count > 0 and tick_count % self._every_n == 0

    def run(self, tick_count: int) -> dict:
        """
        Generate and persist one diary entry.
        Always returns {"entry": str, "tick": int}.
        Never raises.
        """
        try:
            return self._run_safe(tick_count)
        except Exception as e:  # pragma: no cover
            log.error(f"[NarrativeEngine #{tick_count}] Unexpected error: {e}")
            return {"entry": f"[Тик #{tick_count}] Нет данных для записи.", "tick": tick_count}

    # ──────────────────────────────────────────────────────────────
    # Core logic
    # ──────────────────────────────────────────────────────────────
    def _run_safe(self, tick_count: int) -> dict:
        # ── Step 1: gather context ─────────────────────────────────
        episodes   = self._episodic.get_recent_episodes(8) or []
        em_state   = self._emotions.get_state()   if self._emotions   else {}
        em_dominant = self._emotions.get_dominant() if self._emotions else ("unknown", 0.0)
        lt_vector  = self._strategy.get_longterm().get("vector", "")   if self._strategy else ""
        weekly_dir = self._strategy.get_weekly().get("direction", "")  if self._strategy else ""
        now_goal   = self._strategy.get_now().get("goal", "")          if self._strategy else ""

        # identity / name
        name = "Digital Being"
        if hasattr(self._self_model, "get_identity"):
            identity = self._self_model.get_identity()
            name = identity.get("name", "Digital Being") if isinstance(identity, dict) else "Digital Being"

        # ── Step 2: format prompt helpers ─────────────────────────
        actions_summary = self._format_actions(episodes)
        emotion_summary = self._format_emotions(em_state)
        dominant_emotion = em_dominant[0] if em_dominant else "unknown"

        # ── Step 3: LLM call ──────────────────────────────────────
        entry = self._generate_entry(
            name=name,
            tick_count=tick_count,
            actions_summary=actions_summary,
            emotion_summary=emotion_summary,
            dominant_emotion=dominant_emotion,
            current_goal=now_goal,
            weekly_direction=weekly_dir,
            longterm_vector=lt_vector,
        )

        if not entry or not entry.strip():
            entry = f"[Тик #{tick_count}] Нет данных для записи."

        # ── Step 4: persist ───────────────────────────────────────
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._append_diary(tick_count, ts, entry)
        self._episodic.add_episode(
            "diary_entry",
            entry[:500],
            outcome="success",
            data={"tick": tick_count},
        )
        self._append_log(tick_count, ts, entry)

        # ── Step 5: publish event ─────────────────────────────────
        if self._bus is not None:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._bus.publish("narrative.entry_written", {"tick": tick_count}),
                        loop,
                    )
            except Exception as e:
                log.debug(f"[NarrativeEngine] publish error: {e}")

        log.info(f"[NarrativeEngine #{tick_count}] Entry written ({len(entry)} chars).")
        return {"entry": entry, "tick": tick_count}

    # ──────────────────────────────────────────────────────────────
    # LLM
    # ──────────────────────────────────────────────────────────────
    def _generate_entry(
        self,
        name: str,
        tick_count: int,
        actions_summary: str,
        emotion_summary: str,
        dominant_emotion: str,
        current_goal: str,
        weekly_direction: str,
        longterm_vector: str,
    ) -> str:
        prompt = (
            f"Ты — {name}, автономная цифровая сущность.\n"
            f"Напиши дневниковую запись от первого лица для тика #{tick_count}.\n\n"
            f"Контекст:\n"
            f"Последние действия:\n{actions_summary}\n\n"
            f"Эмоциональное состояние: {emotion_summary}\n"
            f"Доминирующая эмоция: {dominant_emotion}\n"
            f"Текущая цель: {current_goal}\n"
            f"Недельное направление: {weekly_direction}\n"
            f"Долгосрочный вектор: {longterm_vector}\n\n"
            f"Требования к записи:\n"
            f'- От первого лица ("Я наблюдал...", "Мне казалось...")\n'
            f"- 3-5 предложений\n"
            f"- Отражает реальные события и эмоции\n"
            f"- Живой, рефлексивный тон\n"
            f"- БЕЗ JSON, только текст дневниковой записи"
        )
        system = (
            f"Ты — {name}. Пиши кратко, от первого лица, живым языком. "
            f"Только текст дневниковой записи, без заголовков и метаданных."
        )
        try:
            result = self._ollama.chat(prompt, system)
            return (result or "").strip()
        except Exception as e:
            log.warning(f"[NarrativeEngine] LLM call failed: {e}")
            return ""

    # ──────────────────────────────────────────────────────────────
    # Persistence helpers
    # ──────────────────────────────────────────────────────────────
    def _append_diary(self, tick_count: int, ts: str, entry: str) -> None:
        """Append one entry to diary.md. Errors are logged, never raised."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        try:
            with self._diary_path.open("a", encoding="utf-8") as f:
                f.write(f"## Тик #{tick_count} — {ts}\n\n{entry}\n\n---\n\n")
        except Exception as e:
            log.error(f"[NarrativeEngine] Failed to write diary.md: {e}")

    def _append_log(self, tick_count: int, ts: str, entry: str) -> None:
        """Update narrative_log.json atomically (tmp + replace), keep last 30."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        try:
            records: list = []
            if self._log_path.exists():
                try:
                    records = json.loads(self._log_path.read_text(encoding="utf-8"))
                    if not isinstance(records, list):
                        records = []
                except Exception:
                    records = []

            records.append({"tick": tick_count, "timestamp": ts, "entry": entry})
            # keep last N
            records = records[-_MAX_LOG_ENTRIES:]

            # atomic write: tmp file → rename
            tmp_path = self._log_path.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(self._log_path)
        except Exception as e:
            log.error(f"[NarrativeEngine] Failed to write narrative_log.json: {e}")

    # ──────────────────────────────────────────────────────────────
    # Context formatters
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _format_actions(episodes: list) -> str:
        if not episodes:
            return "(нет данных)"
        lines = [
            f"{ep.get('event_type', '?')}: {ep.get('description', '')[:120]}"
            for ep in episodes
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_emotions(state: dict) -> str:
        if not state:
            return "(нет данных)"
        significant = {
            k: v for k, v in state.items()
            if isinstance(v, (int, float)) and v > 0.3
        }
        if not significant:
            return "(нейтральное)"
        sorted_items = sorted(significant.items(), key=lambda x: x[1], reverse=True)
        return ", ".join(f"{k}={v:.2f}" for k, v in sorted_items)

    # ──────────────────────────────────────────────────────────────
    # Public read helper (used by IntrospectionAPI)
    # ──────────────────────────────────────────────────────────────
    def load_log(self) -> list:
        """Return list of narrative log records (up to 30). Never raises."""
        try:
            if not self._log_path.exists():
                return []
            records = json.loads(self._log_path.read_text(encoding="utf-8"))
            return records if isinstance(records, list) else []
        except Exception as e:
            log.error(f"[NarrativeEngine] load_log failed: {e}")
            return []
