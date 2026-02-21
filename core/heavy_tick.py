"""
Digital Being — HeavyTick
Stage 24: MetaCognition integration.

Note: TimePerception hour_of_day parsing only uses HH:00 from "14:00-15:00" format.
Minutes are intentionally ignored as a reasonable simplification for current version.
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

        # ── Step: goal selection ────────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: goal_selection")
        try:
            goal_data = await asyncio.wait_for(
                self._step_goal_selection(n, monologue, semantic_ctx), timeout=_STEP_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP goal_selection TIMEOUT ({_STEP_TIMEOUT}s) — using default.")
            goal_data = dict(_DEFAULT_GOAL)

        if self._goal_pers is not None:
            self._goal_pers.set_active(goal_data, tick=n)

        action_type = goal_data.get("action_type", "observe")
        risk_level  = goal_data.get("risk_level",  "low")
        goal_text   = goal_data.get("goal",         _DEFAULT_GOAL["goal"])

        success = True
        outcome = "observe"

        # ── Step: action dispatch ───────────────────────────────────
        log.info(f"[HeavyTick #{n}] STEP: action ({action_type})")
        try:
            if action_type == "observe":
                outcome = "observed"
                log.info(f"[HeavyTick #{n}] Action: observe (passive tick).")
            elif action_type == "analyze":
                success, outcome = await asyncio.wait_for(
                    self._action_analyze(n), timeout=_STEP_TIMEOUT
                )
            elif action_type == "write":
                success, outcome = await asyncio.wait_for(
                    self._action_write(n, monologue, goal_text), timeout=_STEP_TIMEOUT
                )
            elif action_type == "reflect":
                success, outcome = await asyncio.wait_for(
                    self._action_reflect(n), timeout=_STEP_TIMEOUT
                )
            elif action_type == "shell":
                shell_cmd = goal_data.get("shell_command", "")
                success, outcome = await asyncio.wait_for(
                    self._action_shell(n, shell_cmd), timeout=_STEP_TIMEOUT
                )
            else:
                log.warning(f"[HeavyTick #{n}] Unknown action_type='{action_type}'.")
                outcome = "observed"
        except asyncio.TimeoutError:
            log.warning(f"[HeavyTick #{n}] STEP action({action_type}) TIMEOUT ({_STEP_TIMEOUT}s).")
            success, outcome = False, "action_timeout"

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
    # Stage 20: Contradiction Resolver
    # ────────────────────────────────────────────────────────────────
    async def _step_contradiction_resolver(self, n: int) -> None:
        if self._contradictions is None or self._beliefs is None:
            return
        loop = asyncio.get_event_loop()
        if self._contradictions.should_detect(n):
            log.info(f"[HeavyTick #{n}] ContradictionResolver: detecting contradictions.")
            try:
                beliefs = self._beliefs.get_beliefs(status="active")
                principles = self._self_model.get_principles()
                contradictions = await loop.run_in_executor(
                    None, lambda: self._contradictions.detect_contradictions(beliefs, principles, self._ollama)
                )
                for c in contradictions[:2]:
                    added = self._contradictions.add_contradiction(c["type"], c["item_a"], c["item_b"])
                    if added:
                        self._mem.add_episode(
                            "contradiction.detected",
                            f"[{c['type']}] {c['item_a']['text'][:60]} vs {c['item_b']['text'][:60]}",
                            outcome="pending",
                        )
                if contradictions:
                    log.info(f"[HeavyTick #{n}] ContradictionResolver: {len(contradictions)} detected, {len(contradictions[:2])} added.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] ContradictionResolver detect error: {e}")
        if self._contradictions.should_resolve(n):
            pending = self._contradictions.get_pending()
            if pending:
                c = pending[0]
                log.info(f"[HeavyTick #{n}] ContradictionResolver: resolving '{c['item_a']['text'][:40]} vs {c['item_b']['text'][:40]}'")
                try:
                    resolved = await loop.run_in_executor(
                        None, lambda: self._contradictions.resolve_contradiction(c["id"], self._ollama)
                    )
                    if resolved:
                        await self._apply_verdict(c["id"], n)
                        log.info(f"[HeavyTick #{n}] ContradictionResolver: resolution completed and applied.")
                except Exception as e:
                    log.error(f"[HeavyTick #{n}] ContradictionResolver resolve error: {e}")

    async def _apply_verdict(self, contradiction_id: str, tick: int) -> None:
        resolved = self._contradictions.get_resolved(limit=50)
        contradiction = None
        for c in resolved:
            if c["id"] == contradiction_id:
                contradiction = c
                break
        if not contradiction or not contradiction.get("resolution"):
            log.warning(f"_apply_verdict: contradiction {contradiction_id} not found or unresolved")
            return
        resolution = contradiction["resolution"]
        verdict = resolution["verdict"]
        item_a, item_b = contradiction["item_a"], contradiction["item_b"]
        log.info(f"Applying verdict '{verdict}' to contradiction: {item_a['text'][:30]} vs {item_b['text'][:30]}")
        loop = asyncio.get_event_loop()
        if verdict == "choose_a":
            await self._modify_item_confidence(item_b, -0.3, loop)
            self._mem.add_episode("contradiction.resolved", f"Verdict: choose_a. Weakened: {item_b['text'][:100]}",
                                  outcome="success", data={"verdict": verdict, "weakened_id": item_b["id"]})
        elif verdict == "choose_b":
            await self._modify_item_confidence(item_a, -0.3, loop)
            self._mem.add_episode("contradiction.resolved", f"Verdict: choose_b. Weakened: {item_a['text'][:100]}",
                                  outcome="success", data={"verdict": verdict, "weakened_id": item_a["id"]})
        elif verdict == "synthesis":
            synthesis_text = resolution.get("synthesis_text", "")
            if synthesis_text:
                await self._create_synthesis(item_a, item_b, synthesis_text, loop)
                await self._modify_item_confidence(item_a, -0.2, loop)
                await self._modify_item_confidence(item_b, -0.2, loop)
                self._mem.add_episode("contradiction.resolved", f"Verdict: synthesis. Created: {synthesis_text[:100]}",
                                      outcome="success", data={"verdict": verdict, "synthesis": synthesis_text})
        elif verdict == "both_valid":
            self._mem.add_episode("contradiction.resolved", "Verdict: both_valid. No changes applied.",
                                  outcome="success", data={"verdict": verdict})

    async def _modify_item_confidence(self, item: dict, delta: float, loop) -> None:
        item_type = item.get("type", "belief")
        item_id = item["id"]
        if item_type == "belief" and self._beliefs:
            updated = await loop.run_in_executor(
                None, lambda: self._beliefs.update_confidence(item_id, delta)
            )
            if updated:
                log.info(f"Updated belief confidence via update_confidence(): {item['text'][:40]}")
        elif item_type == "principle":
            log.debug(f"Principle confidence modification not implemented: {item_id}")

    async def _create_synthesis(self, item_a: dict, item_b: dict, synthesis_text: str, loop) -> None:
        if item_a.get("type") == "belief" or item_b.get("type") == "belief":
            if self._beliefs:
                if item_a.get("type") == "belief" and item_b.get("type") == "belief":
                    beliefs = self._beliefs.get_beliefs(status="active")
                    cat_a = next((b["category"] for b in beliefs if b["id"] == item_a["id"]), "cause_effect")
                    cat_b = next((b["category"] for b in beliefs if b["id"] == item_b["id"]), "cause_effect")
                    category = cat_a if cat_a == cat_b else "cause_effect"
                else:
                    category = "cause_effect"
                added = self._beliefs.add_belief(synthesis_text, category, 0.6)
                if added:
                    log.info(f"Created synthesis belief: {synthesis_text[:60]}")
        else:
            added = await self._self_model.add_principle(synthesis_text)
            if added:
                log.info(f"Created synthesis principle: {synthesis_text[:60]}")

    # ────────────────────────────────────────────────────────────────
    # Belief System
    # ────────────────────────────────────────────────────────────────
    async def _step_belief_system(self, n: int) -> None:
        if self._beliefs is None:
            return
        loop = asyncio.get_event_loop()
        recent_episodes = self._mem.get_recent_episodes(15)
        if self._beliefs.should_form(n):
            log.info(f"[HeavyTick #{n}] BeliefSystem: forming new beliefs.")
            try:
                new_beliefs = await loop.run_in_executor(
                    None, lambda: self._beliefs.form_beliefs(recent_episodes, self._world, self._ollama)
                )
                for b in new_beliefs:
                    added = self._beliefs.add_belief(b["statement"], b["category"], b.get("initial_confidence", 0.5))
                    if added:
                        self._mem.add_episode(
                            "belief.formed",
                            f"[{b['category']}] {b['statement'][:200]}",
                            outcome="success",
                            data={"confidence": b.get("initial_confidence", 0.5)},
                        )
                if new_beliefs:
                    log.info(f"[HeavyTick #{n}] BeliefSystem: {len(new_beliefs)} belief(s) added.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] BeliefSystem form error: {e}")
        if self._beliefs.should_validate(n):
            try:
                beliefs_to_check = self._beliefs.get_beliefs(min_confidence=0.3, status="active")
                if beliefs_to_check:
                    import random
                    b = random.choice(beliefs_to_check)
                    log.info(f"[HeavyTick #{n}] BeliefSystem: validating '{b['statement'][:60]}'")
                    validated = await loop.run_in_executor(
                        None, lambda: self._beliefs.validate_belief(b["id"], recent_episodes, self._ollama)
                    )
                    if validated:
                        log.info(f"[HeavyTick #{n}] BeliefSystem: validation completed.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] BeliefSystem validate error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Self Modification
    # ────────────────────────────────────────────────────────────────
    async def _step_self_modification(self, n: int) -> None:
        if self._self_mod is None:
            return
        if not self._self_mod.should_suggest(n):
            return
        log.info(f"[HeavyTick #{n}] SelfModificationEngine: generating suggestions.")
        try:
            loop = asyncio.get_event_loop()
            reflection_log = self._reflection.load_log() if self._reflection else []
            emotion_state = self._emotions.get_state() if self._emotions else {}
            suggestions = await loop.run_in_executor(
                None, lambda: self._self_mod.suggest_improvements(reflection_log, emotion_state)
            )
            if not suggestions:
                log.info(f"[HeavyTick #{n}] SelfModificationEngine: no suggestions generated.")
                return
            log.info(f"[HeavyTick #{n}] SelfModificationEngine: {len(suggestions)} suggestion(s) generated.")
            for s in suggestions[:2]:
                key, value, reason = s.get("key", ""), s.get("value"), s.get("reason", "")
                result = await loop.run_in_executor(None, lambda: self._self_mod.propose(key, value, reason))
                status = result.get("status", "unknown")
                if status == "approved":
                    log.info(f"[HeavyTick #{n}] Config change APPROVED: {key} = {value} (was {result.get('old')})")
                    self._mem.add_episode(
                        "self_modification.approved",
                        f"Config change: {key} = {value}. Reason: {reason[:200]}",
                        outcome="success",
                    )
                else:
                    log.info(f"[HeavyTick #{n}] Config change REJECTED: {key} = {value}. Reason: {result.get('reason', '?')}")
        except Exception as e:
            log.error(f"[HeavyTick #{n}] SelfModificationEngine error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Curiosity Engine
    # ────────────────────────────────────────────────────────────────
    async def _step_curiosity(self, n: int) -> None:
        if self._curiosity is None or not self._curiosity_enabled:
            return
        loop = asyncio.get_event_loop()
        if self._curiosity.should_ask(n):
            log.info(f"[HeavyTick #{n}] CuriosityEngine: generating questions.")
            try:
                recent_eps = self._mem.get_recent_episodes(10)
                new_questions = await loop.run_in_executor(
                    None, lambda: self._curiosity.generate_questions(recent_eps, self._world, self._ollama)
                )
                for q in new_questions:
                    self._curiosity.add_question(q, context="auto", priority=0.6)
                if new_questions:
                    log.info(f"[HeavyTick #{n}] CuriosityEngine: {len(new_questions)} question(s) generated.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] CuriosityEngine generate error: {e}")
        if self._curiosity.should_answer(n):
            q = self._curiosity.get_next_question()
            if q:
                log.info(f"[HeavyTick #{n}] CuriosityEngine: seeking answer for '{q['question'][:60]}'")
                try:
                    answer = await loop.run_in_executor(
                        None, lambda: self._curiosity.seek_answer(q, self._mem, self._vector_mem, self._ollama)
                    )
                    self._curiosity.answer_question(q["id"], answer)
                except Exception as e:
                    log.error(f"[HeavyTick #{n}] CuriosityEngine seek_answer error: {e}")
                    self._curiosity.answer_question(q["id"], "Ответ не найден")

    # ────────────────────────────────────────────────────────────────
    # Attention helpers
    # ────────────────────────────────────────────────────────────────
    def _attention_filter_episodes(self, episodes: list[dict]) -> list[dict]:
        if self._attention is None or not episodes:
            return episodes
        try:
            return self._attention.filter_episodes(episodes, top_k=self._attn_top_k, min_score=self._attn_min_score)
        except Exception as e:
            log.debug(f"_attention_filter_episodes(): {e}")
            return episodes

    def _attention_build_context(self, episodes: list[dict]) -> str:
        if self._attention is None:
            return "; ".join(
                f"{e.get('event_type', '?')}: {e.get('description', '')[:60]}" for e in episodes
            ) if episodes else "нет"
        try:
            return self._attention.build_context(episodes, max_chars=self._attn_max_chars)
        except Exception as e:
            log.debug(f"_attention_build_context(): {e}")
            return "(контекст недоступен)"

    def _attention_focus_summary(self) -> str:
        if self._attention is None:
            return ""
        try:
            return self._attention.get_focus_summary()
        except Exception as e:
            log.debug(f"_attention_focus_summary(): {e}")
            return ""

    # ────────────────────────────────────────────────────────────────
    # Post-action steps
    # ────────────────────────────────────────────────────────────────
    async def _step_after_action(
        self, n: int, action_type: str, goal_text: str,
        risk_level: str, mode: str, success: bool, outcome: str
    ) -> None:
        self._values.update_after_action(success=success)
        await self._values._publish_changed()
        if self._strategy is not None:
            self._strategy.set_now(goal_text, action_type)
        emotion_outcome = "success" if success else "failure"
        self._update_emotions(f"heavy_tick.{action_type}", emotion_outcome)
        if self._goal_pers is not None and success:
            self._goal_pers.mark_completed(tick=n)
        self._mem.add_episode(
            f"heavy_tick.{action_type}",
            f"Tick #{n}: goal='{goal_text[:200]}' outcome={outcome}",
            outcome="success" if success else "error",
            data={"tick": n, "action_type": action_type, "risk_level": risk_level, "mode": mode},
        )
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._decision_log.info(f"[{ts}] TICK #{n} | goal={goal_text[:80]} | action={action_type} | risk={risk_level} | outcome={outcome}")
        log.info(f"[HeavyTick #{n}] Completed. action={action_type} outcome={outcome}")
        if self._reflection is not None and self._reflection.should_run(n):
            log.info(f"[HeavyTick #{n}] Triggering ReflectionEngine.")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._reflection.run(n))
            except Exception as e:
                log.error(f"[HeavyTick #{n}] ReflectionEngine.run() error: {e}")
        if self._narrative is not None and self._narrative.should_run(n):
            log.info(f"[HeavyTick #{n}] Triggering NarrativeEngine.")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._narrative.run(n))
            except Exception as e:
                log.error(f"[HeavyTick #{n}] NarrativeEngine.run() error: {e}")
        if self._strategy is not None:
            await self._maybe_update_weekly(n)
        if self._vector_mem is not None and self._tick_count % WEEKLY_CLEANUP_TICKS == 0:
            deleted = self._vector_mem.delete_old(days=30)
            log.info(f"[HeavyTick #{n}] VectorMemory cleanup: {deleted} old records removed.")

    def _update_emotions(self, event_type: str, outcome: str) -> None:
        if self._emotions is None:
            return
        try:
            self._emotions.update(
                event_type=event_type,
                outcome=outcome,
                value_scores=self._values.get_scores() if hasattr(self._values, "get_scores") else {},
            )
        except Exception as e:
            log.error(f"EmotionEngine.update() failed: {e}")

    # ────────────────────────────────────────────────────────────────
    # Memory / Vector helpers
    # ────────────────────────────────────────────────────────────────
    async def _embed_and_store(self, ep_id: int | None, event_type: str, text: str) -> None:
        if self._vector_mem is None:
            return
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(None, lambda: self._ollama.embed(text[:2000]))
            if embedding:
                self._vector_mem.add(
                    episode_id=ep_id or 0, event_type=event_type,
                    text=text[:500], embedding=embedding
                )
        except Exception as e:
            log.debug(f"_embed_and_store(): {e}")

    async def _semantic_context(self, query_text: str) -> str:
        if self._vector_mem is None or self._vector_mem.count() == 0:
            return ""
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(None, lambda: self._ollama.embed(query_text[:2000]))
            if not embedding:
                return ""
            results = self._vector_mem.search(embedding, top_k=3)
            if not results:
                return ""
            log.debug(f"Semantic search: {len(results)} results, top score={results[0]['score']:.3f}")
            lines = ["Похожие прошлые опыты:"]
            for r in results:
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"]))
                lines.append(f"  [{r['event_type']} | {ts} | sim={r['score']:.2f}] {r['text'][:120]}")
            return "\n".join(lines)
        except Exception as e:
            log.debug(f"_semantic_context(): {e}")
            return ""

    # ────────────────────────────────────────────────────────────────
    # Strategy weekly update
    # ────────────────────────────────────────────────────────────────
    async def _maybe_update_weekly(self, n: int) -> None:
        if not self._strategy.should_update_weekly():
            return
        log.info(f"[HeavyTick #{n}] Weekly direction update triggered.")
        context = self._strategy.to_prompt_context()
        prompt = (
            f"{context}\n\nПрошли сутки. Сформулируй новое недельное направление (1 предложение). "
            "Отвечай ТОЛЬКО текстом направления."
        )
        system = "Ты — Digital Being. Формулируй кратко и по делу."
        try:
            loop = asyncio.get_event_loop()
            direction = await loop.run_in_executor(None, lambda: self._ollama.chat(prompt, system))
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
    # Monologue
    # ────────────────────────────────────────────────────────────────
    async def _step_monologue(self, n: int) -> tuple[str, int | None]:
        recent_changes = self._world.get_recent_changes(3)
        changes_str = ", ".join(f"{c.change_type}:{Path(c.path).name}" for c in recent_changes) or "нет"
        raw_eps = self._mem.get_recent_episodes(10)
        filtered = self._attention_filter_episodes(raw_eps)
        eps_str = self._attention_build_context(filtered)
        strategy_ctx = self._strategy.to_prompt_context() if self._strategy is not None else ""
        emotion_ctx = self._emotions.to_prompt_context() if self._emotions else ""
        tone_modifier = self._emotions.get_tone_modifier() if self._emotions else ""
        beliefs_ctx = self._beliefs.to_prompt_context(3) if self._beliefs else ""
        time_ctx = self._time_perc.to_prompt_context(3) if self._time_perc else ""
        meta_ctx  = self._meta_cog.to_prompt_context(2) if self._meta_cog else ""

        prompt = (
            f"Твоё состояние:\n{self._self_model.to_prompt_context()}\n{self._values.to_prompt_context()}\n"
            f"{strategy_ctx}\nМир: {self._world.summary()}\nПоследние изменения: {changes_str}\n"
            f"Значимые эпизоды:\n{eps_str}\n"
        )
        if time_ctx:
            prompt += f"\n{time_ctx}\n"
        if meta_ctx:
            prompt += f"\n{meta_ctx}\n"
        prompt += "\nНапиши короткий внутренний монолог (3-5 предложений):\n"
        prompt += "Что ты сейчас замечаешь? Что тебя беспокоит или интересует? О чём ты думаешь?"
        if beliefs_ctx:
            prompt += f"\n{beliefs_ctx}"
        if self._curiosity is not None and self._curiosity_enabled:
            open_q = self._curiosity.get_open_questions(3)
            if open_q:
                questions_str = "; ".join(q["question"] for q in open_q)
                prompt += f"\nОткрытые вопросы: {questions_str}"

        focus_summary = self._attention_focus_summary()
        system_parts = ["Ты — Digital Being. Автономная система. Отвечай от первого лица. Будь краток."]
        if emotion_ctx:
            system_parts.append(emotion_ctx)
        if tone_modifier:
            system_parts.append(tone_modifier)
        if focus_summary:
            system_parts.append(focus_summary)
        system = "\n".join(system_parts)

        loop = asyncio.get_event_loop()
        monologue = await loop.run_in_executor(None, lambda: self._ollama.chat(prompt, system))
        if not monologue:
            monologue = "(monologue unavailable — LLM did not respond)"

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._monologue_log.info(f"[{ts}] TICK #{n}\n{monologue}\n---")
        ep_id = self._mem.add_episode("monologue", monologue[:1000], outcome="success", data={"tick": n})
        log.info(f"[HeavyTick #{n}] Monologue written ({len(monologue)} chars).")
        return monologue, ep_id

    # ────────────────────────────────────────────────────────────────
    # Goal selection
    # ────────────────────────────────────────────────────────────────
    async def _step_goal_selection(self, n: int, monologue: str, semantic_ctx: str = "") -> dict:
        emotion_ctx = self._emotions.to_prompt_context() if self._emotions else ""
        resume_ctx = ""
        if self._goal_pers is not None and self._goal_pers.was_interrupted():
            resume_ctx = self._goal_pers.get_resume_context()
            log.info(f"[HeavyTick #{n}] Recovery tick. Resume context injected.")
            if not self._resume_incremented:
                self._goal_pers.increment_resume()
                self._resume_incremented = True
        raw_eps = self._mem.get_recent_episodes(10)
        filtered_eps = self._attention_filter_episodes(raw_eps)
        attn_ctx = self._attention_build_context(filtered_eps)
        focus_summary = self._attention_focus_summary()
        if self._strategy is not None:
            goal_data = await self._strategy.select_goal(
                value_engine=self._values, world_model=self._world, episodic=self._mem,
                ollama=self._ollama, semantic_ctx=semantic_ctx,
                emotion_ctx=emotion_ctx, resume_ctx=resume_ctx,
            )
            log.info(f"[HeavyTick #{n}] Goal (StrategyEngine): '{goal_data['goal'][:80]}' action={goal_data['action_type']} risk={goal_data['risk_level']}")
            return goal_data
        mode = self._values.get_mode()
        c_expl = self._values.get_conflict_winner("exploration_vs_stability")
        c_act  = self._values.get_conflict_winner(
            "action_vs_caution",
            risk_score=0.25 if mode in ("curious", "normal") else 0.5,
        )
        sem_block    = f"\n{semantic_ctx}\n" if semantic_ctx else ""
        em_block     = f"\n{emotion_ctx}\n" if emotion_ctx else ""
        resume_block = f"\n{resume_ctx}\n" if resume_ctx else ""
        attn_block   = f"\nЗначимые эпизоды:\n{attn_ctx}\n" if attn_ctx else ""
        shell_hint = ""
        if self._shell_executor is not None:
            allowed_commands = ", ".join(self._shell_executor.get_allowed_commands())
            shell_hint = (
                f"\nЕсли нужно активно исследовать среду — используй action_type=\"shell\" и укажи команду в \"shell_command\".\n"
                f"Доступные команды: {allowed_commands}\n"
                f'{{"goal": "проверить есть ли файл config.yaml", "action_type": "shell", "shell_command": "ls config.yaml"}}'
            )
        prompt = (
            f"{monologue}\n{sem_block}{em_block}{resume_block}{attn_block}"
            f"\nТекущий режим: {mode}\n"
            f"Конфликты: exploration_vs_stability={c_expl}, action_vs_caution={c_act}\n"
            f"{shell_hint}\nВыбери ONE цель. JSON:\n"
            f'{{"goal": "...", "reasoning": "...", "action_type": "observe|analyze|write|reflect|shell", "risk_level": "low|medium|high", "shell_command": "..."}}'
        )
        system_parts = ["Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."]
        if focus_summary:
            system_parts.append(focus_summary)
        system = "\n".join(system_parts)
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: self._ollama.chat(prompt, system))
        goal_data = self._parse_goal_json(raw, n)
        log.info(f"[HeavyTick #{n}] Goal (legacy): '{goal_data['goal'][:80]}' action={goal_data['action_type']} risk={goal_data['risk_level']}")
        return goal_data

    # ────────────────────────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────────────────────────
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
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = self._sandbox_dir / f"thought_{ts}_tick{n}.txt"
            content = (
                f"=== Digital Being — Tick #{n} ===\n"
                f"Цель: {goal}\n"
                f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Монолог:\n{monologue}\n"
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
                errors = [e for e in (self._mem.get_recent_episodes(20) or []) if e.get("outcome") == "error"][:5]
        except Exception:
            errors = []
        if not errors:
            log.info(f"[HeavyTick #{n}] Reflect: no errors found.")
            return True, "reflect:no_errors"
        errors_str = "\n".join(
            f"- [{e.get('event_type', '?')}] {e.get('description', '')[:120]}" for e in errors
        )
        prompt = (
            f"Последние ошибки системы:\n{errors_str}\n\n"
            "Сформулируй ОДНО короткое правило (1 предложение). Отвечай ТОЛЬКО текстом принципа."
        )
        system = "Ты — Digital Being. Формулируй правила из опыта."
        loop = asyncio.get_event_loop()
        principle = await loop.run_in_executor(None, lambda: self._ollama.chat(prompt, system))
        principle = principle.strip()
        if not principle:
            return False, "reflect:empty_principle"
        added = await self._self_model.add_principle(principle[:500])
        if added:
            self._milestones.achieve("first_error_reflection", f"Рефлексия ошибок, принцип: '{principle[:80]}'")
            log.info(f"[HeavyTick #{n}] Reflect: new principle added.")
            return True, "reflect:principle_added"
        else:
            log.info(f"[HeavyTick #{n}] Reflect: principle already exists.")
            return True, "reflect:principle_duplicate"

    # ────────────────────────────────────────────────────────────────
    # Static helpers
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_goal_json(raw: str, n: int) -> dict:
        if not raw:
            return dict(_DEFAULT_GOAL)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start, end = raw.find("{"), raw.rfind("}")
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
