"""Fault-Tolerant HeavyTick with Circuit Breaker, Health Monitoring, and Graceful Degradation.

This is the main orchestrator that integrates:
- CircuitBreaker for LLM call protection
- HealthMonitor for system health tracking
- PriorityExecutor for priority-based execution
- Graceful degradation with fallback strategies
- Parallel execution of optional steps

Usage:
    Replace HeavyTick with FaultTolerantHeavyTick in main.py:
    
    from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick
    
    heavy_tick = FaultTolerantHeavyTick(
        cfg=config,
        ollama=ollama_client,
        world=world_model,
        # ... all other components
    )
    
    await heavy_tick.start()
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.circuit_breaker import CircuitBreaker
from core.health_monitor import HealthMonitor, SystemMode
from core.priority_system import PriorityExecutor, Priority
from core.fallback_generators import FallbackGenerators
from core.resilient_ollama import ResilientOllamaClient

# Import implementation mixins
from core.fault_tolerant_heavy_tick_impl import FaultTolerantHeavyTickImpl
from core.fault_tolerant_heavy_tick_steps import FaultTolerantHeavyTickSteps

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

log = logging.getLogger("digital_being.fault_tolerant_heavy_tick")

# Adaptive timeouts per step (in seconds)
STEP_TIMEOUTS = {
    "monologue": 30,
    "semantic_context": 10,
    "goal_selection": 90,  # Most complex - multiple LLM calls
    "action": 45,
    "after_action": 20,
    "curiosity": 30,
    "self_modification": 25,
    "belief_system": 30,
    "contradiction_resolver": 30,
    "time_perception": 15,
    "social_interaction": 25,
    "meta_cognition": 25,
}

# Step priorities
STEP_PRIORITIES = {
    "monologue": Priority.CRITICAL,
    "semantic_context": Priority.IMPORTANT,
    "goal_selection": Priority.CRITICAL,
    "action": Priority.CRITICAL,
    "after_action": Priority.CRITICAL,
    "curiosity": Priority.OPTIONAL,
    "self_modification": Priority.OPTIONAL,
    "belief_system": Priority.IMPORTANT,
    "contradiction_resolver": Priority.IMPORTANT,
    "time_perception": Priority.OPTIONAL,
    "social_interaction": Priority.IMPORTANT,
    "meta_cognition": Priority.OPTIONAL,
}

_DEFAULT_GOAL: dict = {
    "goal": "наблюдать за средой",
    "reasoning": "LLM недоступен или не вернул валидный JSON",
    "action_type": "observe",
    "risk_level": "low",
}


class FaultTolerantHeavyTick(FaultTolerantHeavyTickImpl, FaultTolerantHeavyTickSteps):
    """
    Fault-tolerant Heavy Tick execution with:
    - Circuit Breaker protection for LLM calls
    - Health Monitoring and auto-recovery
    - Priority-based execution
    - Graceful degradation on failures
    - Automatic fallback with result caching
    - Parallel execution of optional steps
    
    Architecture:
    - FaultTolerantHeavyTickImpl: Core step implementations (monologue, goal, actions)
    - FaultTolerantHeavyTickSteps: Optional step implementations (curiosity, beliefs, etc.)
    - This class: Main orchestration and lifecycle management
    """
    
    def __init__(
        self,
        cfg: dict,
        ollama: "OllamaClient",
        world: "WorldModel",
        values: "ValueEngine",
        self_model: "SelfModel",
        mem: "EpisodicMemory",
        milestones: "Milestones",
        log_dir: Path,
        sandbox_dir: Path,
        strategy: Optional["StrategyEngine"] = None,
        vector_memory: Optional["VectorMemory"] = None,
        emotion_engine: Optional["EmotionEngine"] = None,
        reflection_engine: Optional["ReflectionEngine"] = None,
        narrative_engine: Optional["NarrativeEngine"] = None,
        goal_persistence: Optional["GoalPersistence"] = None,
        attention_system: Optional["AttentionSystem"] = None,
        curiosity_engine: Optional["CuriosityEngine"] = None,
        self_modification: Optional["SelfModificationEngine"] = None,
        belief_system: Optional["BeliefSystem"] = None,
        contradiction_resolver: Optional["ContradictionResolver"] = None,
        shell_executor: Optional["ShellExecutor"] = None,
        time_perception: Optional["TimePerception"] = None,
        social_layer: Optional["SocialLayer"] = None,
        meta_cognition: Optional["MetaCognition"] = None,
        # NEW: 8-Layer Cognitive Architecture components
        goal_oriented = None,
        tool_registry = None,
        learning_engine = None,
        user_model = None,
        proactive = None,
        meta_optimizer = None,
    ) -> None:
        # Store all components
        self._cfg = cfg
        self._world = world
        self._values = values
        self._self_model = self_model
        self._mem = mem
        self._milestones = milestones
        self._log_dir = log_dir
        self._sandbox_dir = sandbox_dir
        self._strategy = strategy
        self._vector_mem = vector_memory
        self._emotions = emotion_engine
        self._reflection = reflection_engine
        self._narrative = narrative_engine
        self._goal_pers = goal_persistence
        self._attention = attention_system
        self._curiosity = curiosity_engine
        self._self_mod = self_modification
        self._beliefs = belief_system
        self._contradictions = contradiction_resolver
        self._shell_executor = shell_executor
        self._time_perc = time_perception
        self._social = social_layer
        self._meta_cog = meta_cognition
        
        # NEW: 8-Layer Architecture components
        self._goal_oriented = goal_oriented
        self._tool_registry = tool_registry
        self._learning_engine = learning_engine
        self._user_model = user_model
        self._proactive = proactive
        self._meta_optimizer = meta_optimizer
        
        # Initialize Health Monitor
        self._health_monitor = HealthMonitor(check_interval=30)
        
        # Initialize Resilient Ollama Client
        self._ollama = ResilientOllamaClient(ollama, self._health_monitor)
        
        # Initialize Priority Executor
        self._executor = PriorityExecutor()
        
        # Configuration
        self._interval = cfg["ticks"]["heavy_tick_sec"]
        self._timeout = int(cfg.get("resources", {}).get("budget", {}).get("tick_timeout_sec", 120))
        self._tick_count = 0
        self._running = False
        self._resume_incremented = False
        
        _attn_cfg = cfg.get("attention", {})
        self._attn_top_k = int(_attn_cfg.get("top_k", 5))
        self._attn_min_score = float(_attn_cfg.get("min_score", 0.4))
        self._attn_max_chars = int(_attn_cfg.get("max_context_chars", 1500))
        
        _cur_cfg = cfg.get("curiosity", {})
        self._curiosity_enabled = bool(_cur_cfg.get("enabled", True))
        
        # Loggers
        from core.heavy_tick import HeavyTick
        self._monologue_log = HeavyTick._make_file_logger(
            "digital_being.monologue", log_dir / "monologue.log"
        )
        self._decision_log = HeavyTick._make_file_logger(
            "digital_being.decisions", log_dir / "decisions.log"
        )
        
        log.info("[FaultTolerantHeavyTick] Initialized with resilience features")
    
    async def start(self) -> None:
        """Start Heavy Tick loop with health monitoring."""
        self._running = True
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Start health monitoring
        await self._health_monitor.start()
        
        log.info(
            f"[FaultTolerantHeavyTick] Started. "
            f"Interval: {self._interval}s, max timeout: {self._timeout}s"
        )
        log.info(f"[FaultTolerantHeavyTick] Adaptive timeouts: {STEP_TIMEOUTS}")
        
        while self._running:
            tick_start = time.monotonic()
            self._tick_count += 1
            
            # Check system health
            system_status = self._health_monitor.get_system_status()
            mode = system_status["mode"]
            
            if mode == SystemMode.EMERGENCY.value:
                log.error(
                    f"[HeavyTick #{self._tick_count}] System in EMERGENCY mode, "
                    "skipping tick"
                )
                await asyncio.sleep(self._interval)
                continue
            
            # Check if Ollama is available
            if not self._ollama.is_available():
                log.warning(
                    f"[HeavyTick #{self._tick_count}] Ollama unavailable "
                    "(circuit breaker OPEN), skipping tick"
                )
                await asyncio.sleep(self._interval)
                continue
            
            # Run tick
            try:
                await asyncio.wait_for(
                    self._run_tick(),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                log.error(
                    f"[HeavyTick #{self._tick_count}] "
                    f"Total timeout ({self._timeout}s) exceeded"
                )
                self._mem.add_episode(
                    "heavy_tick.timeout",
                    f"Heavy tick #{self._tick_count} exceeded {self._timeout}s timeout",
                    outcome="error",
                )
                self._values.update_after_action(success=False)
                await self._values._publish_changed()
                self._update_emotions("heavy_tick.timeout", "failure")
            except Exception as e:
                log.error(f"[HeavyTick #{self._tick_count}] Unexpected error: {e}")
            
            # Reset budgets for next tick
            self._executor.reset_budgets()
            
            # Sleep until next tick
            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))
    
    def stop(self) -> None:
        """Stop Heavy Tick loop and health monitoring."""
        self._running = False
        # Health monitor will be stopped by event loop
        log.info("[FaultTolerantHeavyTick] Stopped")
    
    async def _run_tick(self) -> None:
        """Execute single Heavy Tick with fault tolerance."""
        n = self._tick_count
        log.info(f"[HeavyTick #{n}] Starting (fault-tolerant mode)")
        
        # Update time context
        if self._time_perc is not None:
            self._time_perc.update_context()
        
        # === PHASE 1: Critical Sequential Steps ===
        
        # Step 1: Monologue
        monologue_result = await self._executor.execute_step(
            step_name="monologue",
            func=self._step_monologue,
            priority=STEP_PRIORITIES["monologue"],
            timeout=STEP_TIMEOUTS["monologue"],
            fallback=lambda: FallbackGenerators.monologue_fallback({"tick_number": n}),
            n=n,
        )
        
        if not monologue_result.success:
            log.error(f"[HeavyTick #{n}] Monologue failed, aborting tick")
            return
        
        monologue = monologue_result.result["text"]
        ep_id = monologue_result.result.get("ep_id")
        
        # Embed monologue
        await self._embed_and_store(ep_id, "monologue", monologue)
        
        # Check if defensive mode
        mode = self._values.get_mode()
        if mode == "defensive":
            log.info(f"[HeavyTick #{n}] Mode=defensive, skipping goal selection")
            self._mem.add_episode(
                "heavy_tick.defensive",
                f"Tick #{n}: defensive mode, only monologue executed",
                outcome="skipped",
            )
            self._decision_log.info(
                f"TICK #{n} | goal=observe(defensive) | action=none | outcome=skipped"
            )
            return
        
        # Step 2: Semantic Context
        semantic_result = await self._executor.execute_step(
            step_name="semantic_context",
            func=self._semantic_context,
            priority=STEP_PRIORITIES["semantic_context"],
            timeout=STEP_TIMEOUTS["semantic_context"],
            fallback=lambda: "",
            query_text=monologue,
        )
        
        semantic_ctx = semantic_result.result if semantic_result.success else ""
        
        # Step 3: Goal Selection
        goal_result = await self._executor.execute_step(
            step_name="goal_selection",
            func=self._step_goal_selection,
            priority=STEP_PRIORITIES["goal_selection"],
            timeout=STEP_TIMEOUTS["goal_selection"],
            fallback=lambda: FallbackGenerators.goal_selection_fallback({"tick_number": n}),
            n=n,
            monologue=monologue,
            semantic_ctx=semantic_ctx,
        )
        
        if not goal_result.success:
            log.error(f"[HeavyTick #{n}] Goal selection failed, using fallback")
        
        goal_data = goal_result.result
        
        if self._goal_pers is not None:
            self._goal_pers.set_active(goal_data, tick=n)
        
        action_type = goal_data.get("action_type", "observe")
        risk_level = goal_data.get("risk_level", "low")
        goal_text = goal_data.get("goal", _DEFAULT_GOAL["goal"])
        
        # Step 4: Action
        action_result = await self._executor.execute_step(
            step_name="action",
            func=self._dispatch_action,
            priority=STEP_PRIORITIES["action"],
            timeout=STEP_TIMEOUTS["action"],
            fallback=lambda: FallbackGenerators.action_result_fallback(action_type),
            n=n,
            action_type=action_type,
            goal_text=goal_text,
            goal_data=goal_data,
            monologue=monologue,
        )
        
        success = action_result.result.get("success", True) if action_result.success else False
        outcome = action_result.result.get("outcome", "observed") if action_result.success else "action_failed"
        
        # Step 5: After Action
        await self._executor.execute_step(
            step_name="after_action",
            func=self._step_after_action,
            priority=STEP_PRIORITIES["after_action"],
            timeout=STEP_TIMEOUTS["after_action"],
            fallback=lambda: {"status": "skipped"},
            n=n,
            action_type=action_type,
            goal_text=goal_text,
            risk_level=risk_level,
            mode=mode,
            success=success,
            outcome=outcome,
        )
        
        # === PHASE 2: Optional Parallel Steps ===
        log.info(f"[HeavyTick #{n}] Starting parallel optional steps")
        
        optional_tasks = [
            self._executor.execute_step(
                step_name="curiosity",
                func=self._step_curiosity,
                priority=STEP_PRIORITIES["curiosity"],
                timeout=STEP_TIMEOUTS["curiosity"],
                fallback=lambda: FallbackGenerators.curiosity_fallback(),
                n=n,
            ),
            self._executor.execute_step(
                step_name="self_modification",
                func=self._step_self_modification,
                priority=STEP_PRIORITIES["self_modification"],
                timeout=STEP_TIMEOUTS["self_modification"],
                fallback=lambda: {"status": "skipped"},
                n=n,
            ),
            self._executor.execute_step(
                step_name="belief_system",
                func=self._step_belief_system,
                priority=STEP_PRIORITIES["belief_system"],
                timeout=STEP_TIMEOUTS["belief_system"],
                fallback=lambda: FallbackGenerators.beliefs_fallback(),
                n=n,
            ),
            self._executor.execute_step(
                step_name="contradiction_resolver",
                func=self._step_contradiction_resolver,
                priority=STEP_PRIORITIES["contradiction_resolver"],
                timeout=STEP_TIMEOUTS["contradiction_resolver"],
                fallback=lambda: {"status": "skipped"},
                n=n,
            ),
            self._executor.execute_step(
                step_name="time_perception",
                func=self._step_time_perception,
                priority=STEP_PRIORITIES["time_perception"],
                timeout=STEP_TIMEOUTS["time_perception"],
                fallback=lambda: {"status": "skipped"},
                n=n,
            ),
            self._executor.execute_step(
                step_name="social_interaction",
                func=self._step_social_interaction,
                priority=STEP_PRIORITIES["social_interaction"],
                timeout=STEP_TIMEOUTS["social_interaction"],
                fallback=lambda: FallbackGenerators.social_fallback(),
                n=n,
            ),
            self._executor.execute_step(
                step_name="meta_cognition",
                func=self._step_meta_cognition,
                priority=STEP_PRIORITIES["meta_cognition"],
                timeout=STEP_TIMEOUTS["meta_cognition"],
                fallback=lambda: FallbackGenerators.meta_cognition_fallback(),
                n=n,
            ),
        ]
        
        # Execute all optional tasks in parallel
        optional_results = await asyncio.gather(
            *optional_tasks,
            return_exceptions=True
        )
        
        # Log results
        for i, result in enumerate(optional_results):
            if isinstance(result, Exception):
                log.warning(f"[HeavyTick #{n}] Optional step #{i} failed: {result}")
            elif not result.success:
                log.info(
                    f"[HeavyTick #{n}] Optional step '{result.step_name}' "
                    f"{'used fallback' if result.used_fallback else 'failed'}"
                )
        
        # Print stats
        stats = self._executor.get_stats()
        log.info(
            f"[HeavyTick #{n}] Completed. "
            f"Critical: {stats['critical_executed']}, "
            f"Important: {stats['important_executed']}, "
            f"Optional: {stats['optional_executed']}, "
            f"Fallbacks: {stats['fallbacks_used']}, "
            f"Skipped: {stats['total_skipped']}"
        )
        
        # Print Ollama stats
        ollama_stats = self._ollama.get_stats()
        log.info(
            f"[HeavyTick #{n}] Ollama: "
            f"{ollama_stats['successful_calls']}/{ollama_stats['total_calls']} calls, "
            f"{ollama_stats['success_rate']}% success, "
            f"{ollama_stats['avg_latency_ms']:.0f}ms avg latency"
        )