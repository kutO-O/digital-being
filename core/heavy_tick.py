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
    from core.social_layer import SocialLayer
    from core.strategy_engine import StrategyEngine
    from core.time_perception import TimePerception
    from core.value_engine import ValueEngine
    from core.world_model import WorldModel
    from core.meta_cognition import MetaCognition

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
        time_perception:   "TimePerception | None"   = None,
        social_layer:      "SocialLayer | None"      = None,
        meta_cognition:    "MetaCognition | None"    = None,
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
        self._time_perc    = time_perception
        self._social       = social_layer
        self._meta_cog     = meta_cognition

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

        log.info(f"[HeavyTick #{n}] STEP: semantic_context")
        try:
            semantic_ctx = await asyncio.wait_for(
                self._semantic_context(monologue), timeout=_STEP_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP semantic_context TIMEOUT ({_STEP_TIMEOUT}s) — skipping.")
            semantic_ctx = ""

        # PROTECTED: Goal selection with error boundary
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

        # PROTECTED: Action dispatch with error boundary
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

        log.info(f"[HeavyTick #{n}] STEP: after_action")
        try:
            await asyncio.wait_for(
                self._step_after_action(n, action_type, goal_text, risk_level, mode, success, outcome),
                timeout=_STEP_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP after_action TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: curiosity")
        try:
            await asyncio.wait_for(self._step_curiosity(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP curiosity TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: self_modification")
        try:
            await asyncio.wait_for(self._step_self_modification(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP self_modification TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: belief_system")
        try:
            await asyncio.wait_for(self._step_belief_system(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP belief_system TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: contradiction_resolver")
        try:
            await asyncio.wait_for(self._step_contradiction_resolver(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP contradiction_resolver TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: time_perception")
        try:
            await asyncio.wait_for(self._step_time_perception(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP time_perception TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: social_interaction")
        try:
            await asyncio.wait_for(self._step_social_interaction(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP social_interaction TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] STEP: meta_cognition")
        try:
            await asyncio.wait_for(self._step_meta_cognition(n), timeout=_STEP_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP meta_cognition TIMEOUT ({_STEP_TIMEOUT}s).")

        log.info(f"[HeavyTick #{n}] All steps finished.")

    # ────────────────────────────────────────────────────────────────
    # Action dispatch helper (NEW for error boundaries)
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

    # ────────────────────────────────────────────────────────────────
    # Step: Monologue
    # ────────────────────────────────────────────────────────────────
    async def _step_monologue(self, n: int) -> tuple[str, int]:
        """Generate internal monologue and log it."""
        prompt = self._build_monologue_prompt()
        try:
            response = await asyncio.wait_for(
                self._ollama.generate(prompt, max_tokens=300),
                timeout=_STEP_TIMEOUT
            )
            mono = response.strip()
        except Exception as e:
            log.warning(f"[HeavyTick #{n}] Monologue generation failed: {e}")
            mono = "(монолог недоступен — LLM ошибка)"

        self._monologue_log.info(f"TICK #{n} | {mono}")
        ep_id = self._mem.add_episode("monologue", mono, outcome="generated")
        return mono, ep_id

    def _build_monologue_prompt(self) -> str:
        """Build prompt for internal monologue."""
        parts = [
            "# Внутренний монолог",
            "",
            self._self_model.to_prompt_context(),
            self._values.to_prompt_context(),
        ]
        if self._emotions:
            parts.append(self._emotions.to_prompt_context())
        if self._time_perc:
            parts.append(self._time_perc.to_prompt_context(2))
        
        recent = self._mem.get_recent_episodes(3)
        if recent:
            parts.append("\n## Последние события:")
            for ep in recent:
                parts.append(f"- {ep['event_type']}: {ep['description'][:100]}")
        
        parts.append("\nВырази в 2-3 предложениях свои мысли о текущем состоянии и что делать дальше.")
        return "\n".join(parts)

    # ────────────────────────────────────────────────────────────────
    # Step: Semantic Context (Attention)
    # ────────────────────────────────────────────────────────────────
    async def _semantic_context(self, monologue: str) -> str:
        """Retrieve relevant memories based on monologue."""
        if self._vector_mem is None or self._attention is None:
            return ""
        
        loop = asyncio.get_event_loop()
        try:
            emb = await loop.run_in_executor(
                None,
                lambda: self._ollama.embed(monologue)
            )
            if emb is None:
                return ""
            
            results = await loop.run_in_executor(
                None,
                lambda: self._vector_mem.search(emb, k=self._attn_top_k)
            )
            
            filtered = [r for r in results if r["score"] >= self._attn_min_score]
            if not filtered:
                return ""
            
            ctx_parts = []
            total_chars = 0
            for r in filtered:
                snippet = r["text"][:200]
                if total_chars + len(snippet) > self._attn_max_chars:
                    break
                ctx_parts.append(f"- {snippet} (score: {r['score']:.2f})")
                total_chars += len(snippet)
            
            if ctx_parts:
                return "Релевантный контекст:\n" + "\n".join(ctx_parts)
            return ""
        except Exception as e:
            log.error(f"Semantic context retrieval failed: {e}")
            return ""

    # ────────────────────────────────────────────────────────────────
    # Step: Goal Selection
    # ────────────────────────────────────────────────────────────────
    async def _step_goal_selection(
        self, n: int, monologue: str, semantic_ctx: str
    ) -> dict:
        """Select goal using LLM."""
        prompt = self._build_goal_prompt(monologue, semantic_ctx)
        
        try:
            response = await asyncio.wait_for(
                self._ollama.generate(prompt, max_tokens=200),
                timeout=_STEP_TIMEOUT
            )
            goal_data = self._parse_goal_json(response)
            if goal_data:
                return goal_data
        except Exception as e:
            log.warning(f"[HeavyTick #{n}] Goal selection failed: {e}")
        
        return dict(_DEFAULT_GOAL)

    def _build_goal_prompt(self, monologue: str, semantic_ctx: str) -> str:
        """Build prompt for goal selection."""
        parts = [
            "# Выбор цели",
            "",
            self._self_model.to_prompt_context(),
            self._values.to_prompt_context(),
        ]
        
        if self._emotions:
            parts.append(self._emotions.to_prompt_context())
        
        if semantic_ctx:
            parts.append(f"\n{semantic_ctx}")
        
        parts.append(f"\n## Текущие мысли:\n{monologue}")
        
        if self._curiosity and self._curiosity_enabled:
            q = self._curiosity.get_top_question()
            if q:
                parts.append(f"\n## Открытый вопрос:\n{q['question']}")
        
        parts.append("\nВыбери цель на следующий тик. Ответь JSON:")
        parts.append('{"goal": "текст цели", "reasoning": "почему", "action_type": "observe|analyze|write|reflect|shell", "risk_level": "low|medium|high"}')
        
        return "\n".join(parts)

    def _parse_goal_json(self, text: str) -> dict | None:
        """Parse goal from LLM response."""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                if "goal" in data and "action_type" in data:
                    return data
        except Exception:
            pass
        return None

    # ────────────────────────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────────────────────────
    async def _action_analyze(self, n: int) -> tuple[bool, str]:
        """Analyze recent episodes."""
        episodes = self._mem.get_recent_episodes(10)
        if not episodes:
            return True, "analyze:no_data"
        
        patterns = {}
        for ep in episodes:
            et = ep["event_type"]
            patterns[et] = patterns.get(et, 0) + 1
        
        summary = ", ".join([f"{k}={v}" for k, v in patterns.items()])
        log.info(f"[HeavyTick #{n}] Analysis: {summary}")
        
        self._mem.add_episode(
            "action.analyze",
            f"Проанализировал последние 10 эпизодов: {summary}",
            outcome="success"
        )
        return True, "analyze:complete"

    async def _action_write(self, n: int, monologue: str, goal: str) -> tuple[bool, str]:
        """Write thoughts to file."""
        filename = f"thought_{n}.txt"
        filepath = self._sandbox_dir / filename
        
        try:
            content = f"Tick #{n}\n\nМонолог: {monologue}\n\nЦель: {goal}\n"
            filepath.write_text(content, encoding="utf-8")
            
            log.info(f"[HeavyTick #{n}] Wrote to {filename}")
            self._mem.add_episode(
                "action.write",
                f"Записал мысли в {filename}",
                outcome="success"
            )
            return True, "write:success"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Write failed: {e}")
            return False, "write:error"

    async def _action_reflect(self, n: int) -> tuple[bool, str]:
        """Trigger reflection engine."""
        if self._reflection is None:
            log.warning(f"[HeavyTick #{n}] ReflectionEngine not available")
            return False, "reflect:unavailable"
        
        try:
            loop = asyncio.get_event_loop()
            episodes = self._mem.get_recent_episodes(20)
            
            reflection = await loop.run_in_executor(
                None,
                lambda: self._reflection.reflect(episodes, self._ollama)
            )
            
            if reflection:
                log.info(f"[HeavyTick #{n}] Reflection: {reflection[:100]}")
                self._mem.add_episode(
                    "action.reflect",
                    f"Рефлексия: {reflection[:200]}",
                    outcome="success"
                )
                return True, "reflect:success"
            else:
                return False, "reflect:no_output"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Reflection failed: {e}")
            return False, "reflect:error"

    # ────────────────────────────────────────────────────────────────
    # Step: After Action
    # ────────────────────────────────────────────────────────────────
    async def _step_after_action(
        self,
        n: int,
        action_type: str,
        goal_text: str,
        risk_level: str,
        mode: str,
        success: bool,
        outcome: str
    ) -> None:
        """Process results after action execution."""
        self._values.update_after_action(success)
        await self._values._publish_changed()
        
        self._update_emotions(action_type, outcome)
        
        self._decision_log.info(
            f"TICK #{n} | goal={goal_text[:50]} | "
            f"action={action_type} | risk={risk_level} | "
            f"mode={mode} | success={success} | outcome={outcome}"
        )
        
        self._mem.add_episode(
            "heavy_tick.complete",
            f"Tick #{n}: {action_type} - {outcome}",
            outcome="success" if success else "failure"
        )
        
        # Weekly strategy update
        if self._strategy and n % WEEKLY_CLEANUP_TICKS == 0:
            log.info(f"[HeavyTick #{n}] Weekly strategy update")
            try:
                loop = asyncio.get_event_loop()
                episodes = self._mem.get_recent_episodes(100)
                await loop.run_in_executor(
                    None,
                    lambda: self._strategy.update_from_history(episodes, self._ollama)
                )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] Strategy update failed: {e}")
        
        # Periodic cleanup
        if self._vector_mem and n % 24 == 0:
            try:
                loop = asyncio.get_event_loop()
                deleted = await loop.run_in_executor(
                    None,
                    lambda: self._vector_mem.cleanup_old_vectors(days=30)
                )
                if deleted > 0:
                    log.info(f"[HeavyTick #{n}] Cleaned up {deleted} old vectors")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] Vector cleanup failed: {e}")

    def _update_emotions(self, action: str, outcome: str) -> None:
        """Update emotional state based on action outcome."""
        if self._emotions is None:
            return
        
        if outcome in ("success", "complete", "observed"):
            self._emotions.adjust("satisfaction", 0.1)
            self._emotions.adjust("anxiety", -0.05)
        elif outcome in ("error", "failure", "timeout"):
            self._emotions.adjust("anxiety", 0.1)
            self._emotions.adjust("satisfaction", -0.05)
        
        self._emotions.decay(0.95)

    # ────────────────────────────────────────────────────────────────
    # Step: Curiosity
    # ────────────────────────────────────────────────────────────────
    async def _step_curiosity(self, n: int) -> None:
        """Update curiosity engine."""
        if self._curiosity is None or not self._curiosity_enabled:
            return
        
        try:
            loop = asyncio.get_event_loop()
            episodes = self._mem.get_recent_episodes(10)
            
            await loop.run_in_executor(
                None,
                lambda: self._curiosity.update(episodes, self._ollama)
            )
            
            top_q = self._curiosity.get_top_question()
            if top_q:
                log.info(f"[HeavyTick #{n}] Top question: {top_q['question'][:80]}")
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Curiosity update failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Step: Self Modification
    # ────────────────────────────────────────────────────────────────
    async def _step_self_modification(self, n: int) -> None:
        """Check for self-modification proposals."""
        if self._self_mod is None:
            return
        
        if n % 168 == 0:  # Weekly
            log.info(f"[HeavyTick #{n}] Checking self-modification proposals")
            try:
                loop = asyncio.get_event_loop()
                proposals = await loop.run_in_executor(
                    None,
                    lambda: self._self_mod.check_proposals(self._mem, self._ollama)
                )
                if proposals:
                    log.info(f"[HeavyTick #{n}] Found {len(proposals)} modification proposal(s)")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] Self-modification check failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Step: Belief System
    # ────────────────────────────────────────────────────────────────
    async def _step_belief_system(self, n: int) -> None:
        """Update beliefs based on recent experiences."""
        if self._beliefs is None:
            return
        
        if n % 24 == 0:  # Daily
            log.info(f"[HeavyTick #{n}] Updating belief system")
            try:
                loop = asyncio.get_event_loop()
                episodes = self._mem.get_recent_episodes(30)
                await loop.run_in_executor(
                    None,
                    lambda: self._beliefs.update_from_episodes(episodes, self._ollama)
                )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] Belief system update failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Step: Contradiction Resolver
    # ────────────────────────────────────────────────────────────────
    async def _step_contradiction_resolver(self, n: int) -> None:
        """Detect and resolve contradictions."""
        if self._contradictions is None or self._beliefs is None:
            return
        
        if n % 48 == 0:  # Every 2 days
            log.info(f"[HeavyTick #{n}] Checking for contradictions")
            try:
                loop = asyncio.get_event_loop()
                beliefs = self._beliefs.get_beliefs()
                conflicts = await loop.run_in_executor(
                    None,
                    lambda: self._contradictions.detect(beliefs, self._ollama)
                )
                if conflicts:
                    log.info(f"[HeavyTick #{n}] Found {len(conflicts)} contradiction(s)")
                    for c in conflicts[:2]:
                        resolution = await loop.run_in_executor(
                            None,
                            lambda conflict=c: self._contradictions.resolve(
                                conflict, beliefs, self._mem, self._ollama
                            )
                        )
                        if resolution:
                            log.info(f"[HeavyTick #{n}] Resolved: {resolution[:100]}")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] Contradiction resolution failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Helper: Embed and Store
    # ────────────────────────────────────────────────────────────────
    async def _embed_and_store(self, episode_id: int, label: str, text: str) -> None:
        """Embed text and store in vector memory."""
        if self._vector_mem is None:
            return
        
        try:
            loop = asyncio.get_event_loop()
            emb = await loop.run_in_executor(
                None,
                lambda: self._ollama.embed(text)
            )
            if emb:
                await loop.run_in_executor(
                    None,
                    lambda: self._vector_mem.add(f"{label}_{episode_id}", text, emb)
                )
        except Exception as e:
            log.error(f"Embedding failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Helper: File Logger
    # ────────────────────────────────────────────────────────────────
    def _make_file_logger(self, name: str, path: Path) -> logging.Logger:
        """Create a dedicated file logger."""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        
        logger.addHandler(handler)
        return logger
