"""
Digital Being — HeavyTick
Stage 18: SelfModificationEngine integration.

Each tick executes in strict order (with per-tick timeout):
  Step 1 — Internal Monologue  (always) + embed → VectorMemory
  Step 2 — Goal Selection      via StrategyEngine + semantic context
                                + GoalPersistence resume context if interrupted
  Step 3 — Action
  Step 4 — After-action (includes emotion update + reflection trigger
            + narrative trigger + GoalPersistence mark_completed on success)
  Step 5 — Curiosity: generate questions / seek answers (Stage 17)
  Step 6 — Self-Modification: every 50 ticks, suggest and apply improvements (Stage 18)

New in Stage 18:
  - self_modification injected (optional, gracefully skipped if None)
  - After curiosity step:
      • should_suggest()  → suggest_improvements() → propose() up to 2 suggestions
  - Config changes are logged and published via EventBus

Resource budget:
  - Max 3 LLM calls per tick (enforced by OllamaClient)
  - embed() does NOT count against budget
  - Reflection adds 1 extra LLM call on reflection ticks (outside normal budget)
  - Narrative adds 1 extra LLM call on narrative ticks (outside normal budget)
  - Curiosity adds up to 2 extra LLM calls (generate + seek) on curiosity ticks
  - Self-Modification adds up to 3 extra LLM calls (suggest + 2x verify) every 50 ticks
  - Max 30 s per tick (asyncio.wait_for)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.attention_system import AttentionSystem
    from core.curiosity_engine import CuriosityEngine
    from core.emotion_engine import EmotionEngine
    from core.goal_persistence import GoalPersistence
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.milestones import Milestones
    from core.narrative_engine import NarrativeEngine
    from core.ollama_client import OllamaClient
    from core.reflection_engine import ReflectionEngine
    from core.self_modification import SelfModificationEngine
    from core.self_model import SelfModel
    from core.strategy_engine import StrategyEngine
    from core.value_engine import ValueEngine
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.heavy_tick")

# How many ticks between vector DB cleanup runs (~7 days if tick=10 min)
WEEKLY_CLEANUP_TICKS = 1008

_DEFAULT_GOAL: dict = {
    "goal":        "наблюдать за средой",
    "reasoning":   "LLM недоступен или не вернул валидный JSON",
    "action_type": "observe",
    "risk_level":  "low",
}


class HeavyTick:
    """
    Async heavy-tick engine.
    All dependencies injected — no globals.

    Lifecycle:
        ht = HeavyTick(...)
        task = asyncio.create_task(ht.start())
        ht.stop()
    """

    def __init__(
        self,
        cfg:          dict,
        ollama:       "OllamaClient",
        world:        "WorldModel",
        values:       "ValueEngine",
        self_model:   "SelfModel",
        mem:          "EpisodicMemory",
        milestones:   "Milestones",
        log_dir:      Path,
        sandbox_dir:  Path,
        strategy:     "StrategyEngine | None" = None,
        vector_memory: "VectorMemory | None" = None,
        emotion_engine: "EmotionEngine | None" = None,
        reflection_engine: "ReflectionEngine | None" = None,  # Stage 13
        narrative_engine:  "NarrativeEngine | None"  = None,  # Stage 14
        goal_persistence:  "GoalPersistence | None"  = None,  # Stage 15
        attention_system:  "AttentionSystem | None"  = None,  # Stage 16
        curiosity_engine:  "CuriosityEngine | None"  = None,  # Stage 17
        self_modification: "SelfModificationEngine | None" = None,  # Stage 18
    ) -> None:
        self._cfg          = cfg
        self._ollama       = ollama
        self._world        = world
        self._values       = values
        self._self_model   = self_model
        self._mem          = mem
        self._milestones   = milestones
        self._log_dir      = log_dir
        self._sandbox_dir  = sandbox_dir
        self._strategy     = strategy
        self._vector_mem   = vector_memory
        self._emotions     = emotion_engine
        self._reflection   = reflection_engine  # Stage 13
        self._narrative    = narrative_engine   # Stage 14
        self._goal_pers    = goal_persistence   # Stage 15
        self._attention    = attention_system   # Stage 16
        self._curiosity    = curiosity_engine   # Stage 17
        self._self_mod     = self_modification  # Stage 18

        self._interval    = cfg["ticks"]["heavy_tick_sec"]
        self._timeout     = int(
            cfg.get("resources", {}).get("budget", {}).get("tick_timeout_sec", 30)
        )
        self._tick_count  = 0
        self._running     = False

        # Stage 15: flag to know whether the first recovery tick has been processed
        self._resume_incremented = False

        # Attention config (Stage 16)
        _attn_cfg             = cfg.get("attention", {})
        self._attn_top_k      = int(_attn_cfg.get("top_k", 5))
        self._attn_min_score  = float(_attn_cfg.get("min_score", 0.4))
        self._attn_max_chars  = int(_attn_cfg.get("max_context_chars", 1500))

        # Curiosity config (Stage 17)
        _cur_cfg              = cfg.get("curiosity", {})
        self._curiosity_enabled = bool(_cur_cfg.get("enabled", True))

        self._monologue_log = self._make_file_logger(
            "digital_being.monologue",
            log_dir / "monologue.log",
        )
        self._decision_log = self._make_file_logger(
            "digital_being.decisions",
            log_dir / "decisions.log",
        )

    # ────────────────────────────────────────────────────────────────
    # Main loop
    # ────────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self._running = True
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"HeavyTick started. Interval: {self._interval}s, timeout: {self._timeout}s")

        while self._running:
            tick_start = time.monotonic()
            self._tick_count += 1

            if not self._ollama.is_available():
                log.warning(f"[HeavyTick #{self._tick_count}] Ollama unavailable — skipping tick.")
                await asyncio.sleep(self._interval)
                continue

            try:
                await asyncio.wait_for(self._run_tick(), timeout=self._timeout)
            except asyncio.TimeoutError:
                log.error(f"[HeavyTick #{self._tick_count}] Timeout ({self._timeout}s) exceeded.")
                self._mem.add_episode(
                    "heavy_tick.timeout",
                    f"Heavy tick #{self._tick_count} exceeded {self._timeout}s timeout",
                    outcome="error",
                )
                self._values.update_after_action(success=False)
                await self._values._publish_changed()
                # Emotion update on timeout
                self._update_emotions(
                    event_type="heavy_tick.timeout",
                    outcome="failure",
                )

            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))

    def stop(self) -> None:
        self._running = False
        log.info("HeavyTick stopped.")

    # ────────────────────────────────────────────────────────────────
    # Tick body
    # ────────────────────────────────────────────────────────────────
    async def _run_tick(self) -> None:
        n = self._tick_count
        log.info(f"[HeavyTick #{n}] Starting.")
        self._ollama.reset_tick_counter()

        # Step 1: Monologue
        monologue, ep_id = await self._step_monologue(n)

        # Stage 9: embed monologue and store in VectorMemory
        await self._embed_and_store(ep_id, "monologue", monologue)

        # Defensive mode
        mode = self._values.get_mode()
        if mode == "defensive":
            log.info(f"[HeavyTick #{n}] Mode=defensive — skipping goal selection.")
            self._mem.add_episode(
                "heavy_tick.defensive",
                f"Tick #{n}: defensive mode, only monologue executed.",
                outcome="skipped",
            )
            self._decision_log.info(
                f"TICK #{n} | goal=observe(defensive) | action=none | outcome=skipped"
            )
            return

        # Stage 9: semantic context for goal selection
        semantic_ctx = await self._semantic_context(monologue)

        # Step 2: Goal Selection
        goal_data = await self._step_goal_selection(n, monologue, semantic_ctx)

        # Stage 15: persist active goal immediately after selection
        if self._goal_pers is not None:
            self._goal_pers.set_active(goal_data, tick=n)

        action_type = goal_data.get("action_type", "observe")
        risk_level  = goal_data.get("risk_level",  "low")
        goal_text   = goal_data.get("goal",         _DEFAULT_GOAL["goal"])

        # Step 3: Action
        success = True
        outcome = "observe"

        if action_type == "observe":
            outcome = "observed"
            log.info(f"[HeavyTick #{n}] Action: observe (passive tick).")
        elif action_type == "analyze":
            success, outcome = await self._action_analyze(n)
        elif action_type == "write":
            success, outcome = await self._action_write(n, monologue, goal_text)
        elif action_type == "reflect":
            success, outcome = await self._action_reflect(n)
        else:
            log.warning(f"[HeavyTick #{n}] Unknown action_type='{action_type}'. Treating as observe.")
            outcome = "observed"

        # Step 4: After-action
        await self._step_after_action(
            n=n,
            action_type=action_type,
            goal_text=goal_text,
            risk_level=risk_level,
            mode=mode,
            success=success,
            outcome=outcome,
        )

        # Step 5: Curiosity Engine (Stage 17)
        await self._step_curiosity(n)

        # Step 6: Self-Modification Engine (Stage 18)
        await self._step_self_modification(n)

    # ────────────────────────────────────────────────────────────────
    # Stage 18: Self-Modification step
    # ────────────────────────────────────────────────────────────────
    async def _step_self_modification(self, n: int) -> None:
        """Генерация и применение предложений по изменению config.yaml."""
        if self._self_mod is None:
            return

        if not self._self_mod.should_suggest(n):
            return

        log.info(f"[HeavyTick #{n}] SelfModificationEngine: generating suggestions.")

        try:
            loop = asyncio.get_event_loop()

            # Get reflection log and emotion state
            reflection_log = (
                self._reflection.load_log() if self._reflection else []
            )
            emotion_state = (
                self._emotions.get_state() if self._emotions else {}
            )

            # Generate suggestions
            suggestions = await loop.run_in_executor(
                None,
                lambda: self._self_mod.suggest_improvements(
                    reflection_log, emotion_state
                ),
            )

            if not suggestions:
                log.info(f"[HeavyTick #{n}] SelfModificationEngine: no suggestions generated.")
                return

            log.info(
                f"[HeavyTick #{n}] SelfModificationEngine: "
                f"{len(suggestions)} suggestion(s) generated."
            )

            # Apply up to 2 suggestions per cycle
            for s in suggestions[:2]:
                key = s.get("key", "")
                value = s.get("value")
                reason = s.get("reason", "")

                result = await loop.run_in_executor(
                    None,
                    lambda: self._self_mod.propose(key, value, reason),
                )

                status = result.get("status", "unknown")
                if status == "approved":
                    log.info(
                        f"[HeavyTick #{n}] Config change APPROVED: "
                        f"{key} = {value} (was {result.get('old')})"
                    )
                    self._mem.add_episode(
                        "self_modification.approved",
                        f"Config change: {key} = {value}. Reason: {reason[:200]}",
                        outcome="success",
                    )
                else:
                    log.info(
                        f"[HeavyTick #{n}] Config change REJECTED: "
                        f"{key} = {value}. Reason: {result.get('reason', '?')}"
                    )

        except Exception as e:
            log.error(f"[HeavyTick #{n}] SelfModificationEngine error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Stage 17: Curiosity step
    # ────────────────────────────────────────────────────────────────
    async def _step_curiosity(self, n: int) -> None:
        """Генерация вопросов и поиск ответов через CuriosityEngine."""
        if self._curiosity is None or not self._curiosity_enabled:
            return

        loop = asyncio.get_event_loop()

        # Генерация вопросов
        if self._curiosity.should_ask(n):
            log.info(f"[HeavyTick #{n}] CuriosityEngine: generating questions.")
            try:
                recent_eps = self._mem.get_recent_episodes(10)
                new_questions = await loop.run_in_executor(
                    None,
                    lambda: self._curiosity.generate_questions(
                        recent_eps, self._world, self._ollama
                    ),
                )
                for q in new_questions:
                    self._curiosity.add_question(q, context="auto", priority=0.6)
                if new_questions:
                    log.info(
                        f"[HeavyTick #{n}] CuriosityEngine: "
                        f"{len(new_questions)} question(s) generated."
                    )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] CuriosityEngine generate error: {e}")

        # Поиск ответов
        if self._curiosity.should_answer(n):
            q = self._curiosity.get_next_question()
            if q:
                log.info(
                    f"[HeavyTick #{n}] CuriosityEngine: seeking answer for "
                    f"'{q['question'][:60]}'"
                )
                try:
                    answer = await loop.run_in_executor(
                        None,
                        lambda: self._curiosity.seek_answer(
                            q, self._mem, self._vector_mem, self._ollama
                        ),
                    )
                    self._curiosity.answer_question(q["id"], answer)
                except Exception as e:
                    log.error(f"[HeavyTick #{n}] CuriosityEngine seek_answer error: {e}")
                    self._curiosity.answer_question(q["id"], "Ответ не найден")

    # ────────────────────────────────────────────────────────────────
    # Stage 16: attention helpers
    # ────────────────────────────────────────────────────────────────
    def _attention_filter_episodes(self, episodes: list[dict]) -> list[dict]:
        """Filter episodes through AttentionSystem if available."""
        if self._attention is None or not episodes:
            return episodes
        try:
            return self._attention.filter_episodes(
                episodes,
                top_k=self._attn_top_k,
                min_score=self._attn_min_score,
            )
        except Exception as e:
            log.debug(f"_attention_filter_episodes(): {e}")
            return episodes

    def _attention_build_context(self, episodes: list[dict]) -> str:
        """Build context string from filtered episodes."""
        if self._attention is None:
            return "; ".join(
                f"{e.get('event_type','?')}: {e.get('description','')[:60]}"
                for e in episodes
            ) if episodes else "нет"
        try:
            return self._attention.build_context(
                episodes, max_chars=self._attn_max_chars
            )
        except Exception as e:
            log.debug(f"_attention_build_context(): {e}")
            return "(контекст недоступен)"

    def _attention_focus_summary(self) -> str:
        """Get attention focus summary for system prompt."""
        if self._attention is None:
            return ""
        try:
            return self._attention.get_focus_summary()
        except Exception as e:
            log.debug(f"_attention_focus_summary(): {e}")
            return ""

    # ────────────────────────────────────────────────────────────────
    # Step 4: After-action (extracted for clarity)
    # ────────────────────────────────────────────────────────────────
    async def _step_after_action(
        self,
        n:           int,
        action_type: str,
        goal_text:   str,
        risk_level:  str,
        mode:        str,
        success:     bool,
        outcome:     str,
    ) -> None:
        self._values.update_after_action(success=success)
        await self._values._publish_changed()

        if self._strategy is not None:
            self._strategy.set_now(goal_text, action_type)

        # Stage 12: update emotions based on outcome
        emotion_outcome = "success" if success else "failure"
        self._update_emotions(
            event_type=f"heavy_tick.{action_type}",
            outcome=emotion_outcome,
        )

        # Stage 15: mark goal completed on success
        if self._goal_pers is not None and success:
            self._goal_pers.mark_completed(tick=n)

        self._mem.add_episode(
            f"heavy_tick.{action_type}",
            f"Tick #{n}: goal='{goal_text[:200]}' outcome={outcome}",
            outcome="success" if success else "error",
            data={"tick": n, "action_type": action_type, "risk_level": risk_level, "mode": mode},
        )

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._decision_log.info(
            f"[{ts}] TICK #{n} | "
            f"goal={goal_text[:80]} | action={action_type} | "
            f"risk={risk_level} | outcome={outcome}"
        )
        log.info(f"[HeavyTick #{n}] Completed. action={action_type} outcome={outcome}")

        # Stage 13: Reflection Engine trigger
        if self._reflection is not None and self._reflection.should_run(n):
            log.info(f"[HeavyTick #{n}] Triggering ReflectionEngine.")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: self._reflection.run(n)
                )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] ReflectionEngine.run() error: {e}")

        # Stage 14: Narrative Engine trigger
        if self._narrative is not None and self._narrative.should_run(n):
            log.info(f"[HeavyTick #{n}] Triggering NarrativeEngine.")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: self._narrative.run(n)
                )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] NarrativeEngine.run() error: {e}")

        # Weekly tasks
        if self._strategy is not None:
            await self._maybe_update_weekly(n)
        if self._vector_mem is not None and self._tick_count % WEEKLY_CLEANUP_TICKS == 0:
            deleted = self._vector_mem.delete_old(days=30)
            log.info(f"[HeavyTick #{n}] VectorMemory cleanup: {deleted} old records removed.")

    # ────────────────────────────────────────────────────────────────
    # Stage 12 helper: emotion update
    # ────────────────────────────────────────────────────────────────
    def _update_emotions(self, event_type: str, outcome: str) -> None:
        """Safe wrapper — never raises, logs errors."""
        if self._emotions is None:
            return
        try:
            self._emotions.update(
                event_type=event_type,
                outcome=outcome,
                value_scores=self._values.get_scores()
                if hasattr(self._values, "get_scores") else {},
            )
        except Exception as e:
            log.error(f"EmotionEngine.update() failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Stage 9 helpers
    # ────────────────────────────────────────────────────────────────
    async def _embed_and_store(self, ep_id: int | None, event_type: str, text: str) -> None:
        """
        Embed `text` via Ollama and store in VectorMemory.
        Fire-and-forget: errors are logged, never raised.
        """
        if self._vector_mem is None:
            return
        try:
            loop      = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self._ollama.embed(text[:2000])
            )
            if embedding:
                self._vector_mem.add(
                    episode_id=ep_id or 0,
                    event_type=event_type,
                    text=text[:500],
                    embedding=embedding,
                )
        except Exception as e:
            log.debug(f"_embed_and_store(): {e}")

    async def _semantic_context(self, query_text: str) -> str:
        """
        Embed `query_text`, search VectorMemory for similar past episodes.
        Returns a formatted string ready for LLM injection, or "" if unavailable.
        """
        if self._vector_mem is None:
            return ""
        if self._vector_mem.count() == 0:
            return ""
        try:
            loop      = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self._ollama.embed(query_text[:2000])
            )
            if not embedding:
                return ""

            results = self._vector_mem.search(embedding, top_k=3)
            if not results:
                return ""

            log.debug(
                f"Semantic search: {len(results)} results, "
                f"top score={results[0]['score']:.3f}"
            )

            lines = ["Похожие прошлые опыты:"]
            for r in results:
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"]))
                lines.append(f"  [{r['event_type']} | {ts} | sim={r['score']:.2f}] {r['text'][:120]}")
            return "\n".join(lines)
        except Exception as e:
            log.debug(f"_semantic_context(): {e}")
            return ""

    # ────────────────────────────────────────────────────────────────
    # Weekly direction refresh
    # ────────────────────────────────────────────────────────────────
    async def _maybe_update_weekly(self, n: int) -> None:
        if not self._strategy.should_update_weekly():
            return
        log.info(f"[HeavyTick #{n}] Weekly direction update triggered.")
        context = self._strategy.to_prompt_context()
        prompt = (
            f"{context}\n\n"
            f"Прошли сутки. Сформулируй новое недельное направление (1 предложение) "
            f"которое отражает текущее состояние системы и долгосрочный вектор. "
            f"Отвечай ТОЛЬКО текстом направления."
        )
        system = "Ты — Digital Being. Формулируй кратко и по делу."
        try:
            loop      = asyncio.get_event_loop()
            direction = await loop.run_in_executor(
                None, lambda: self._ollama.chat(prompt, system)
            )
            direction = direction.strip() if direction else ""
            if direction:
                self._strategy.update_weekly(direction)
                self._mem.add_episode(
                    "strategy.weekly_update",
                    f"Недельное направление обновлено: '{direction[:200]}'",
                    outcome="success",
                )
                log.info(f"[HeavyTick #{n}] Weekly direction updated.")
            else:
                log.warning(f"[HeavyTick #{n}] Weekly update: LLM returned empty.")
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Weekly update failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Step implementations
    # ────────────────────────────────────────────────────────────────
    async def _step_monologue(self, n: int) -> tuple[str, int | None]:
        """
        Step 1: Generate monologue.
        Stage 16: recent episodes passed through AttentionSystem before
                  being formatted; attention focus injected into system prompt.
        Stage 17: open curiosity questions appended to prompt.
        Returns (text, episode_id).
        """
        recent_changes = self._world.get_recent_changes(3)
        changes_str    = ", ".join(
            f"{c.change_type}:{Path(c.path).name}" for c in recent_changes
        ) or "нет"

        # Stage 16: filter episodes through AttentionSystem
        raw_eps     = self._mem.get_recent_episodes(10)  # fetch more, let attention trim
        filtered    = self._attention_filter_episodes(raw_eps)
        eps_str     = self._attention_build_context(filtered)

        strategy_ctx = (
            self._strategy.to_prompt_context()
            if self._strategy is not None else ""
        )

        # Stage 12: build emotion context for monologue
        emotion_ctx  = self._emotions.to_prompt_context() if self._emotions else ""
        tone_modifier = self._emotions.get_tone_modifier() if self._emotions else ""

        prompt = (
            f"Твоё состояние:\n"
            f"{self._self_model.to_prompt_context()}\n"
            f"{self._values.to_prompt_context()}\n"
            f"{strategy_ctx}\n"
            f"Мир: {self._world.summary()}\n"
            f"Последние изменения: {changes_str}\n"
            f"Значимые эпизоды:\n{eps_str}\n\n"
            f"Напиши короткий внутренний монолог (3-5 предложений):\n"
            f"Что ты сейчас замечаешь? Что тебя беспокоит или интересует? О чём ты думаешь?"
        )

        # Stage 17: append open curiosity questions to prompt
        if self._curiosity is not None and self._curiosity_enabled:
            open_q = self._curiosity.get_open_questions(3)
            if open_q:
                questions_str = "; ".join(q["question"] for q in open_q)
                prompt += f"\nОткрытые вопросы: {questions_str}"

        # Stage 16: attention focus appended to system prompt
        focus_summary = self._attention_focus_summary()
        system_parts = [
            "Ты — Digital Being. Автономная система. Отвечай от первого лица. Будь краток.",
        ]
        if emotion_ctx:
            system_parts.append(emotion_ctx)
        if tone_modifier:
            system_parts.append(tone_modifier)
        if focus_summary:
            system_parts.append(focus_summary)
        system = "\n".join(system_parts)

        loop      = asyncio.get_event_loop()
        monologue = await loop.run_in_executor(
            None, lambda: self._ollama.chat(prompt, system)
        )
        if not monologue:
            monologue = "(monologue unavailable — LLM did not respond)"

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._monologue_log.info(f"[{ts}] TICK #{n}\n{monologue}\n---")

        ep_id = self._mem.add_episode(
            "monologue",
            monologue[:1000],
            outcome="success",
            data={"tick": n},
        )
        log.info(f"[HeavyTick #{n}] Monologue written ({len(monologue)} chars).")
        return monologue, ep_id

    async def _step_goal_selection(
        self, n: int, monologue: str, semantic_ctx: str = ""
    ) -> dict:
        """
        Step 2: Select goal.
        Stage 9:  semantic_ctx injected into prompt.
        Stage 12: emotion context injected into StrategyEngine prompt.
        Stage 15: resume context injected when system was interrupted;
                  increment_resume() called once on first recovery tick.
        Stage 16: attention-filtered episode context injected;
                  attention focus added to system prompt.
        """
        # Stage 12: emotion context for goal selection
        emotion_ctx = self._emotions.to_prompt_context() if self._emotions else ""

        # Stage 15: build resume context block
        resume_ctx = ""
        if self._goal_pers is not None and self._goal_pers.was_interrupted():
            resume_ctx = self._goal_pers.get_resume_context()
            log.info(f"[HeavyTick #{n}] Recovery tick. Resume context injected.")
            if not self._resume_incremented:
                self._goal_pers.increment_resume()
                self._resume_incremented = True

        # Stage 16: attention-filtered episode context
        raw_eps      = self._mem.get_recent_episodes(10)
        filtered_eps = self._attention_filter_episodes(raw_eps)
        attn_ctx     = self._attention_build_context(filtered_eps)
        focus_summary = self._attention_focus_summary()

        # ── Stage 8/9 path: StrategyEngine ─────────────────
        if self._strategy is not None:
            goal_data = await self._strategy.select_goal(
                value_engine=self._values,
                world_model=self._world,
                episodic=self._mem,
                ollama=self._ollama,
                semantic_ctx=semantic_ctx,
                emotion_ctx=emotion_ctx,   # Stage 12
                resume_ctx=resume_ctx,     # Stage 15
            )
            log.info(
                f"[HeavyTick #{n}] Goal (StrategyEngine): "
                f"'{goal_data['goal'][:80]}' "
                f"action={goal_data['action_type']} risk={goal_data['risk_level']}"
            )
            return goal_data

        # ── Legacy path ─────────────────────────────
        mode   = self._values.get_mode()
        c_expl = self._values.get_conflict_winner("exploration_vs_stability")
        c_act  = self._values.get_conflict_winner(
            "action_vs_caution",
            risk_score=0.25 if mode in ("curious", "normal") else 0.5,
        )
        sem_block    = f"\n{semantic_ctx}\n"  if semantic_ctx  else ""
        em_block     = f"\n{emotion_ctx}\n"   if emotion_ctx   else ""
        resume_block = f"\n{resume_ctx}\n"    if resume_ctx    else ""
        attn_block   = f"\nЗначимые эпизоды:\n{attn_ctx}\n" if attn_ctx else ""

        prompt = (
            f"{monologue}\n{sem_block}{em_block}{resume_block}{attn_block}\n"
            f"Текущий режим: {mode}\n"
            f"Конфликты: exploration_vs_stability={c_expl}, action_vs_caution={c_act}\n\n"
            f"Выбери ONE цель. JSON:\n"
            f'{{"goal": "...", "reasoning": "...", '
            f'"action_type": "observe|analyze|write|reflect", '
            f'"risk_level": "low|medium|high"}}'
        )
        system_parts = ["Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."]
        if focus_summary:
            system_parts.append(focus_summary)
        system = "\n".join(system_parts)

        loop     = asyncio.get_event_loop()
        raw      = await loop.run_in_executor(None, lambda: self._ollama.chat(prompt, system))
        goal_data = self._parse_goal_json(raw, n)
        log.info(
            f"[HeavyTick #{n}] Goal (legacy): '{goal_data['goal'][:80]}' "
            f"action={goal_data['action_type']} risk={goal_data['risk_level']}"
        )
        return goal_data

    async def _action_analyze(self, n: int) -> tuple[bool, str]:
        try:
            anomalies = self._world.detect_anomalies()
            if anomalies:
                return True, f"analyzed:{len(anomalies)}_anomalies"
            return True, "analyzed:no_anomalies"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] analyze failed: {e}")
            return False, "analyze_error"

    async def _action_write(self, n: int, monologue: str, goal: str) -> tuple[bool, str]:
        try:
            ts       = time.strftime("%Y%m%d_%H%M%S")
            out_path = self._sandbox_dir / f"thought_{ts}_tick{n}.txt"
            content  = (
                f"=== Digital Being — Tick #{n} ===\n"
                f"Цель: {goal}\n"
                f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"\nМонолог:\n{monologue}\n"
            )
            out_path.write_text(content, encoding="utf-8")
            log.info(f"[HeavyTick #{n}] Written: {out_path.name}")
            return True, f"written:{out_path.name}"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] write failed: {e}")
            return False, "write_error"

    async def _action_reflect(self, n: int) -> tuple[bool, str]:
        try:
            errors = self._mem.get_episodes_by_type("error", limit=5)
            if not errors:
                errors = [
                    e for e in (self._mem.get_recent_episodes(20) or [])
                    if e.get("outcome") == "error"
                ][:5]
        except Exception:
            errors = []

        if not errors:
            log.info(f"[HeavyTick #{n}] Reflect: no errors found.")
            return True, "reflect:no_errors"

        errors_str = "\n".join(
            f"- [{e.get('event_type','?')}] {e.get('description','')[:120]}"
            for e in errors
        )
        prompt = (
            f"Последние ошибки системы:\n{errors_str}\n\n"
            f"Сформулируй ОДНО короткое правило (1 предложение). "
            f"Отвечай ТОЛЬКО текстом принципа."
        )
        system = "Ты — Digital Being. Формулируй правила из опыта."

        loop      = asyncio.get_event_loop()
        principle = await loop.run_in_executor(
            None, lambda: self._ollama.chat(prompt, system)
        )
        principle = principle.strip()

        if not principle:
            return False, "reflect:empty_principle"

        added = await self._self_model.add_principle(principle[:500])
        if added:
            self._milestones.achieve(
                "first_error_reflection",
                f"Рефлексия ошибок, принцип: '{principle[:80]}'",
            )
            log.info(f"[HeavyTick #{n}] Reflect: new principle added.")
            return True, "reflect:principle_added"
        else:
            log.info(f"[HeavyTick #{n}] Reflect: principle already exists.")
            return True, "reflect:principle_duplicate"

    # ────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_goal_json(raw: str, n: int) -> dict:
        if not raw:
            return dict(_DEFAULT_GOAL)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start: end + 1])
            except json.JSONDecodeError:
                pass
        log.warning(f"[HeavyTick #{n}] Could not parse goal JSON. Using default.")
        return dict(_DEFAULT_GOAL)

    @staticmethod
    def _make_file_logger(name: str, path: Path) -> logging.Logger:
        path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
        return logger
