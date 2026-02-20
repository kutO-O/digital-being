"""
Digital Being — HeavyTick
Stage 23: SocialLayer integration for async user communication.

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
    from core.time_perception import TimePerception
    from core.value_engine import ValueEngine
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.heavy_tick")

WEEKLY_CLEANUP_TICKS = 1008

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
        social_layer:      "SocialLayer | None"      = None,  # Stage 23
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
        self._social       = social_layer  # Stage 23

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
        self._decision_log = self._make_file_logger("digital_being.decisions", log_dir / "decisions.log")

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
                self._mem.add_episode("heavy_tick.timeout", f"Heavy tick #{self._tick_count} exceeded {self._timeout}s timeout", outcome="error")
                self._values.update_after_action(success=False)
                await self._values._publish_changed()
                self._update_emotions("heavy_tick.timeout", "failure")

            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))

    def stop(self) -> None:
        self._running = False
        log.info("HeavyTick stopped.")

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
            self._mem.add_episode("heavy_tick.defensive", f"Tick #{n}: defensive mode, only monologue executed.", outcome="skipped")
            self._decision_log.info(f"TICK #{n} | goal=observe(defensive) | action=none | outcome=skipped")
            return

        semantic_ctx = await self._semantic_context(monologue)
        goal_data = await self._step_goal_selection(n, monologue, semantic_ctx)

        if self._goal_pers is not None:
            self._goal_pers.set_active(goal_data, tick=n)

        action_type = goal_data.get("action_type", "observe")
        risk_level  = goal_data.get("risk_level",  "low")
        goal_text   = goal_data.get("goal",         _DEFAULT_GOAL["goal"])

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
        elif action_type == "shell":
            shell_cmd = goal_data.get("shell_command", "")
            success, outcome = await self._action_shell(n, shell_cmd)
        else:
            log.warning(f"[HeavyTick #{n}] Unknown action_type='{action_type}'.")
            outcome = "observed"

        await self._step_after_action(n, action_type, goal_text, risk_level, mode, success, outcome)
        await self._step_curiosity(n)
        await self._step_self_modification(n)
        await self._step_belief_system(n)
        await self._step_contradiction_resolver(n)
        await self._step_time_perception(n)
        await self._step_social_interaction(n)  # Stage 23

    # ────────────────────────────────────────────────────────────────
    # Stage 23: Social Interaction
    # ────────────────────────────────────────────────────────────────
    async def _step_social_interaction(self, n: int) -> None:
        if self._social is None:
            return
        
        loop = asyncio.get_event_loop()
        
        # Check for incoming messages
        new_messages = await loop.run_in_executor(None, self._social.check_inbox)
        
        if new_messages:
            for msg in new_messages:
                # Update tick in message
                msg["tick"] = n
                
                # Add to memory
                self._mem.add_episode(
                    "social.incoming",
                    f"Пользователь написал: {msg['content'][:200]}",
                    outcome="success",
                    data={"message_id": msg["id"]}
                )
                
                # Generate response
                context = self._build_social_context()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._social.generate_response(msg, context, self._ollama)
                )
                
                if response:
                    # Send response
                    outgoing = self._social.add_outgoing(response, n, response_to=msg["id"])
                    await loop.run_in_executor(None, lambda: self._social.write_to_outbox(response))
                    self._social.mark_responded(msg["id"])
                    
                    self._mem.add_episode(
                        "social.outgoing",
                        f"Ответил пользователю: {response[:200]}",
                        outcome="success"
                    )
                    
                    log.info(f"[HeavyTick #{n}] SocialLayer: responded to user message.")
                else:
                    # LLM unavailable
                    self._mem.add_episode(
                        "social.llm_unavailable",
                        "Не удалось сгенерировать ответ — LLM недоступен",
                        outcome="error"
                    )
                    log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate response (LLM unavailable).")
        
        # Check if should initiate conversation
        should_write, reason = await loop.run_in_executor(
            None,
            lambda: self._social.should_initiate(
                n, self._world, self._emotions, self._curiosity
            )
        )
        
        if should_write:
            context = self._build_social_context()
            message = await loop.run_in_executor(
                None,
                lambda: self._social.generate_initiative(reason, context, self._ollama)
            )
            
            if message:
                outgoing = self._social.add_outgoing(message, n)
                await loop.run_in_executor(None, lambda: self._social.write_to_outbox(message))
                
                self._mem.add_episode(
                    "social.initiative",
                    f"Написал пользователю (reason={reason}): {message[:200]}",
                    outcome="success"
                )
                
                log.info(f"[HeavyTick #{n}] SocialLayer: initiated conversation (reason={reason}).")
            else:
                log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate initiative message.")

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
        
        return "\n".join(parts)

    # ────────────────────────────────────────────────────────────────
    # Stage 22: Time Perception
    # ────────────────────────────────────────────────────────────────
    async def _step_time_perception(self, n: int) -> None:
        if self._time_perc is None:
            return
        
        loop = asyncio.get_event_loop()
        
        # Detect patterns periodically
        if self._time_perc.should_detect(n):
            log.info(f"[HeavyTick #{n}] TimePerception: detecting patterns.")
            try:
                episodes = self._mem.get_recent_episodes(50)
                patterns = await loop.run_in_executor(
                    None, lambda: self._time_perc.detect_patterns(episodes, self._ollama)
                )
                
                for p in patterns[:3]:  # max 3 per cycle
                    self._time_perc.add_pattern(
                        p["pattern_type"], p["condition"], p["observation"], p.get("confidence", 0.5)
                    )
                
                if patterns:
                    log.info(f"[HeavyTick #{n}] TimePerception: {len(patterns)} pattern(s) detected.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] TimePerception error: {e}")

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

    # Continue with rest of heavy_tick.py methods...
    # [Previous methods remain unchanged]
