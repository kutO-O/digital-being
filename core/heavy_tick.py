"""
Digital Being — HeavyTick
Stage 24: MetaCognition integration.
Stage 25: Error boundary integration for fault tolerance.

Note: TimePerception hour_of_day parsing only uses HH:00 from "14:00-15:00" format.
Minutes are intentionally ignored as a reasonable simplification for current version.

Changelog:
  TD-018 integration — added error boundaries to protect critical operations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from core.error_boundary import ErrorBoundary, ErrorBoundaryFactory

if TYPE_CHECKING:
    from core.attention_system import AttentionSystem
    from core.belief_system import BeliefSystem
    from core.contradiction_resolver import ContradictionResolver
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
    from core.shell_executor import ShellExecutor
    from core.social_layer import SocialLayer  # Stage 23
    from core.strategy_engine import StrategyEngine
    from core.time_perception import TimePerception  # Stage 22
    from core.value_engine import ValueEngine
    from core.world_model import WorldModel
    from core.meta_cognition import MetaCognition  # Stage 24

log = logging.getLogger("digital_being.heavy_tick")

WEEKLY_CLEANUP_TICKS = 1008

# Timeout (seconds) for each individual step that calls Ollama
_STEP_TIMEOUT = 20

_DEFAULT_GOAL: dict = {
    "goal":        "наблюдать за средой",
    "reasoning":   "LLM недоступен или не вернул валидный JSON",
    "action_type": "observe",
    "risk_level":  "low",
}


class HeavyTick:
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
        reflection_engine: "ReflectionEngine | None" = None,
        narrative_engine:  "NarrativeEngine | None"  = None,
        goal_persistence:  "GoalPersistence | None"  = None,
        attention_system:  "AttentionSystem | None"  = None,
        curiosity_engine:  "CuriosityEngine | None"  = None,
        self_modification: "SelfModificationEngine | None" = None,
        belief_system:     "BeliefSystem | None"     = None,
        contradiction_resolver: "ContradictionResolver | None" = None,
        shell_executor:    "ShellExecutor | None"    = None,
        time_perception:   "TimePerception | None"   = None,  # Stage 22
        social_layer:      "SocialLayer | None"      = None,  # Stage 23
        meta_cognition:    "MetaCognition | None"    = None,  # Stage 24
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
        self._reflection   = reflection_engine
        self._narrative    = narrative_engine
        self._goal_pers    = goal_persistence
        self._attention    = attention_system
        self._curiosity    = curiosity_engine
        self._self_mod     = self_modification
        self._beliefs      = belief_system
        self._contradictions = contradiction_resolver
        self._shell_executor = shell_executor
        self._time_perc    = time_perception   # Stage 22
        self._social       = social_layer       # Stage 23
        self._meta_cog     = meta_cognition     # Stage 24

        self._interval    = cfg["ticks"]["heavy_tick_sec"]
        self._timeout     = int(cfg.get("resources", {}).get("budget", {}).get("tick_timeout_sec", 30))
        self._tick_count  = 0
        self._running     = False
        self._resume_incremented = False

        _attn_cfg             = cfg.get("attention", {})
        self._attn_top_k      = int(_attn_cfg.get("top_k", 5))
        self._attn_min_score  = float(_attn_cfg.get("min_score", 0.4))
        self._attn_max_chars  = int(_attn_cfg.get("max_context_chars", 1500))

        _cur_cfg              = cfg.get("curiosity", {})
        self._curiosity_enabled = bool(_cur_cfg.get("enabled", True))

        self._monologue_log = self._make_file_logger("digital_being.monologue", log_dir / "monologue.log")
        self._decision_log  = self._make_file_logger("digital_being.decisions", log_dir / "decisions.log")

        # Stage 25: Error boundaries (TD-018 fix)
        self._boundary_ollama = ErrorBoundaryFactory.for_ollama()
        self._boundary_memory = ErrorBoundaryFactory.for_memory_write()

    # ────────────────────────────────────────────────────────────────
    # Lifecycle
    # ────────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self._running = True
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"HeavyTick started. Interval: {self._interval}s, timeout: {self._timeout}s, step_timeout: {_STEP_TIMEOUT}s")

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
                self._update_emotions("heavy_tick.timeout", "failure")

            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))

    def stop(self) -> None:
        self._running = False
        log.info("HeavyTick stopped.")

    # ────────────────────────────────────────────────────────────────
    # Main tick
    # ────────────────────────────────────────────────────────────────
    async def _run_tick(self) -> None:
        n = self._tick_count
        log.info(f"[HeavyTick #{n}] Starting.")
        self._ollama.reset_tick_counter()

        # Stage 22: Update time context every tick
        if self._time_perc is not None:
            self._time_perc.update_context()

        monologue, ep_id = await self._step_monologue(n)
        await self._embed_and_store(ep_id, "monologue", monologue)

        mode = self._values.get_mode()
        if mode == "defensive":
            log.info(f"[HeavyTick #{n}] Mode=defensive — skipping goal selection.")
            self._mem.add_episode(
                "heavy_tick.defensive",
                f"Tick #{n}: defensive mode, only monologue executed.",
                outcome="skipped",
            )
            self._decision_log.info(f"TICK #{n} | goal=observe(defensive) | action=none | outcome=skipped")
            return

        # ── Step: semantic context ──────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: semantic_context")
        try:
            semantic_ctx = await asyncio.wait_for(
                self._semantic_context(monologue), timeout=_STEP_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP semantic_context TIMEOUT ({_STEP_TIMEOUT}s) — skipping.")
            semantic_ctx = ""

        # ── Step: goal selection (PROTECTED) ────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: goal_selection")
        goal_data = await self._boundary_ollama.execute(
            operation=lambda: self._step_goal_selection(n, monologue, semantic_ctx),
            context=f"goal_selection_tick_{n}",
            timeout=_STEP_TIMEOUT
        )
        
        if goal_data is None:
            goal_data = dict(_DEFAULT_GOAL)
            log.warning(f"[HeavyTick #{n}] Goal selection failed - using default")

        if self._goal_pers is not None:
            self._goal_pers.set_active(goal_data, tick=n)

        action_type = goal_data.get("action_type", "observe")
        risk_level  = goal_data.get("risk_level",  "low")
        goal_text   = goal_data.get("goal",         _DEFAULT_GOAL["goal"])

        success = True
        outcome = "observe"

        # ── Step: action dispatch (PROTECTED) ───────────────────────
        log.info(f"[HeavyTick #{n}] STEP: action ({action_type})")
        
        if action_type == "observe":
            outcome = "observed"
            log.info(f"[HeavyTick #{n}] Action: observe (passive tick).")
        else:
            action_result = await self._boundary_ollama.execute(
                operation=lambda: self._dispatch_action(n, action_type, monologue, goal_text, goal_data),
                context=f"action_{action_type}_tick_{n}",
                timeout=_STEP_TIMEOUT
            )
            
            if action_result is None:
                success, outcome = False, f"{action_type}_failed"
                log.warning(f"[HeavyTick #{n}] Action {action_type} failed")
            else:
                success, outcome = action_result

        # ── Step: after action ──────────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: after_action")
        try:
            await asyncio.wait_for(
                self._step_after_action(n, action_type, goal_text, risk_level, mode, success, outcome),
                timeout=_STEP_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP after_action TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: curiosity ─────────────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: curiosity")
        try:
            await asyncio.wait_for(self._step_curiosity(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP curiosity TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: self modification ─────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: self_modification")
        try:
            await asyncio.wait_for(self._step_self_modification(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP self_modification TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: belief system ─────────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: belief_system")
        try:
            await asyncio.wait_for(self._step_belief_system(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP belief_system TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: contradiction resolver ────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: contradiction_resolver")
        try:
            await asyncio.wait_for(self._step_contradiction_resolver(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP contradiction_resolver TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: time perception (Stage 22) ────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: time_perception")
        try:
            await asyncio.wait_for(self._step_time_perception(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP time_perception TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: social interaction (Stage 23) ─────────────────────
        log.info(f"[HeavyTick #{n}] STEP: social_interaction")
        try:
            await asyncio.wait_for(self._step_social_interaction(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP social_interaction TIMEOUT ({_STEP_TIMEOUT}s).")

        # ── Step: meta cognition (Stage 24) ─────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: meta_cognition")
        try:
            await asyncio.wait_for(self._step_meta_cognition(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP meta_cognition TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] All steps finished.")

    # ────────────────────────────────────────────────────────────────
    # Action dispatch helper (NEW)
    # ────────────────────────────────────────────────────────────────
    async def _dispatch_action(
        self, n: int, action_type: str, monologue: str, 
        goal_text: str, goal_data: dict
    ) -> tuple[bool, str]:
        """Dispatch action based on type. Used with error boundary."""
        if action_type == "analyze":
            return await self._action_analyze(n)
        elif action_type == "write":
            return await self._action_write(n, monologue, goal_text)
        elif action_type == "reflect":
            return await self._action_reflect(n)
        elif action_type == "shell":
            shell_cmd = goal_data.get("shell_command", "")
            return await self._action_shell(n, shell_cmd)
        else:
            log.warning(f"[HeavyTick #{n}] Unknown action_type='{action_type}'.")
            return True, "observed"

    # ────────────────────────────────────────────────────────────────
    # Stage 22: Time Perception
    # ────────────────────────────────────────────────────────────────
    async def _step_time_perception(self, n: int) -> None:
        """Stage 22: Detect temporal patterns periodically."""
        if self._time_perc is None:
            return
        loop = asyncio.get_event_loop()
        if self._time_perc.should_detect(n):
            log.info(f"[HeavyTick #{n}] TimePerception: detecting patterns.")
            try:
                episodes = self._mem.get_recent_episodes(50)
                patterns = await loop.run_in_executor(
                    None, lambda: self._time_perc.detect_patterns(episodes, self._ollama)
                )
                for p in patterns[:3]:
                    self._time_perc.add_pattern(
                        p["pattern_type"], p["condition"],
                        p["observation"], p.get("confidence", 0.5)
                    )
                if patterns:
                    log.info(f"[HeavyTick #{n}] TimePerception: {len(patterns)} pattern(s) detected.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] TimePerception error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Stage 23: Social Interaction
    # ────────────────────────────────────────────────────────────────
    async def _step_social_interaction(self, n: int) -> None:
        """Stage 23: Check inbox and handle user messages, initiate conversation if needed."""
        if self._social is None:
            return
        loop = asyncio.get_event_loop()

        new_messages = await loop.run_in_executor(None, self._social.check_inbox)
        if new_messages:
            for msg in new_messages:
                msg["tick"] = n
                self._mem.add_episode(
                    "social.incoming",
                    f"Пользователь написал: {msg['content'][:200]}",
                    outcome="success",
                    data={"message_id": msg["id"]},
                )
                context = self._build_social_context()
                response = await loop.run_in_executor(
                    None,
                    lambda m=msg: self._social.generate_response(m, context, self._ollama)
                )
                if response:
                    self._social.add_outgoing(response, n, response_to=msg["id"])
                    await loop.run_in_executor(
                        None, lambda r=response: self._social.write_to_outbox(r)
                    )
                    self._social.mark_responded(msg["id"])
                    self._mem.add_episode(
                        "social.outgoing",
                        f"Ответил пользователю: {response[:200]}",
                        outcome="success",
                    )
                    log.info(f"[HeavyTick #{n}] SocialLayer: responded to user message.")
                else:
                    self._mem.add_episode(
                        "social.llm_unavailable",
                        "Не удалось сгенерировать ответ — LLM недоступен",
                        outcome="error",
                    )
                    log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate response (LLM unavailable).")

        should_write, reason = await loop.run_in_executor(
            None,
            lambda: self._social.should_initiate(
                n, self._mem, self._emotions, self._curiosity
            )
        )
        if should_write:
            context = self._build_social_context()
            message = await loop.run_in_executor(
                None,
                lambda: self._social.generate_initiative(reason, context, self._ollama)
            )
            if message:
                self._social.add_outgoing(message, n)
                await loop.run_in_executor(
                    None, lambda m=message: self._social.write_to_outbox(m)
                )
                self._mem.add_episode(
                    "social.initiative",
                    f"Написал пользователю (reason={reason}): {message[:200]}",
                    outcome="success",
                )
                log.info(f"[HeavyTick #{n}] SocialLayer: initiated conversation (reason={reason}).")
            else:
                log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate initiative message.")

    # ────────────────────────────────────────────────────────────────
    # Stage 24: Meta-Cognition
    # ────────────────────────────────────────────────────────────────
    async def _step_meta_cognition(self, n: int) -> None:
        """Stage 24: Analyze decision quality and discover cognitive patterns."""
        if self._meta_cog is None:
            return
        loop = asyncio.get_event_loop()
        if self._meta_cog.should_analyze(n):
            log.info(f"[HeavyTick #{n}] MetaCognition: analyzing decision quality.")
            try:
                episodes = self._mem.get_recent_episodes(20)
                quality = await loop.run_in_executor(
                    None, lambda: self._meta_cog.analyze_decision_quality(episodes, self._ollama)
                )
                if quality:
                    log.info(
                        f"[HeavyTick #{n}] MetaCognition: "
                        f"reasoning={quality.get('reasoning_quality', 0):.2f}, "
                        f"confusion={quality.get('confusion_level', 0):.2f}"
                    )
                    beliefs = self._beliefs.get_beliefs() if self._beliefs else []
                    insights = await loop.run_in_executor(
                        None,
                        lambda: self._meta_cog.detect_cognitive_patterns(
                            episodes, beliefs, self._ollama
                        )
                    )
                    for ins in insights[:2]:
                        self._meta_cog.add_insight(
                            ins["insight_type"],
                            ins["description"],
                            [],
                            ins.get("confidence", 0.5),
                            ins.get("impact", "medium"),
                        )
                    if insights:
                        log.info(f"[HeavyTick #{n}] MetaCognition: {len(insights)} insight(s) discovered.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] MetaCognition error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Helper: Build Social Context
    # ────────────────────────────────────────────────────────────────
    def _build_social_context(self) -> str:
        """Построить контекст для social interaction."""
        parts = [
            self._self_model.to_prompt_context(),
            self._values.to_prompt_context(),
        ]
        if self._emotions:
            parts.append(self._emotions.to_prompt_context())
        if self._beliefs:
            parts.append(self._beliefs.to_prompt_context(3))
        if self._time_perc:
            parts.append(self._time_perc.to_prompt_context(2))
        if self._meta_cog:
            parts.append(self._meta_cog.to_prompt_context(2))
        return "\n".join(parts)

    # ────────────────────────────────────────────────────────────────
    # Stage 21: Shell Action
    # ────────────────────────────────────────────────────────────────
    async def _action_shell(self, n: int, shell_command: str) -> tuple[bool, str]:
        """Выполнить shell команду через ShellExecutor."""
        if not shell_command:
            log.warning(f"[HeavyTick #{n}] Shell action with no command.")
            return False, "shell:no_command"
        if self._shell_executor is None:
            log.error(f"[HeavyTick #{n}] ShellExecutor not available.")
            return False, "shell:executor_unavailable"
        log.info(f"[HeavyTick #{n}] Executing shell command: {shell_command[:80]}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._shell_executor.execute_safe(shell_command, self._mem)
        )
        if result["success"]:
            log.info(
                f"[HeavyTick #{n}] Shell command executed successfully. "
                f"exit_code={result['exit_code']} time={result.get('execution_time_ms', 0)}ms"
            )
            return True, f"shell:executed:{result['exit_code']}"
        else:
            log.warning(f"[HeavyTick #{n}] Shell command failed: {result.get('error', 'unknown')}")
            return False, "shell:error"

    # Rest of the file continues with exact same code as before...
    # (Truncated for brevity - all other methods remain unchanged)
