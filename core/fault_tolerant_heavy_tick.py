"""Fault-tolerant Heavy Tick orchestrator."""

import asyncio
import time
from typing import Dict, Any, Optional, List
import logging

from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from core.health_monitor import HealthMonitor
from core.fallback_cache import FallbackCache, FallbackStrategy
from core.priority_budget import PriorityBudgetSystem, Priority

logger = logging.getLogger('digital_being.fault_tolerant_heavy_tick')


class FaultTolerantHeavyTick:
    """
    Fault-tolerant Heavy Tick orchestrator.
    
    Features:
    - Circuit breakers prevent cascading failures
    - Health monitoring detects degraded services
    - Graceful degradation with fallback cache
    - Priority budget ensures critical tasks always run
    - Parallel execution of optional steps
    - Comprehensive error handling
    
    Architecture:
        [Monologue] (CRITICAL, sequential)
            ↓
        [Goal Selection] (CRITICAL, sequential)
            ↓
        [Action] (CRITICAL, sequential)
            ↓
        [Curiosity | Beliefs | Social | Meta] (OPTIONAL, parallel)
    """
    
    def __init__(
        self,
        ollama_client,
        config: Dict[str, Any],
    ):
        """
        Initialize fault-tolerant orchestrator.
        
        Args:
            ollama_client: Ollama LLM client instance
            config: Configuration dict
        """
        self.ollama = ollama_client
        self.config = config
        
        # Initialize fault-tolerance components
        self.circuit_breaker = CircuitBreaker(
            name="ollama_llm",
            failure_threshold=3,
            timeout=60,
            success_threshold=2,
        )
        
        self.health_monitor = HealthMonitor(
            check_interval=30,
            failure_threshold=3,
        )
        
        self.fallback_cache = FallbackCache(default_ttl=300)
        self.fallback_strategy = FallbackStrategy(self.fallback_cache)
        
        self.budget_system = PriorityBudgetSystem()
        
        # Register health check for Ollama
        self.health_monitor.register(
            "ollama",
            self._check_ollama_health,
            latency_threshold=10.0,
        )
        
        # Register defaults for critical components
        self._register_defaults()
        
        # Health monitoring listener
        self.health_monitor.add_listener(self._on_health_change)
        
        logger.info("[FaultTolerantHeavyTick] Initialized")
    
    def _register_defaults(self):
        """Register default fallback values."""
        self.fallback_cache.set_default(
            "monologue",
            "Размышляю о текущей ситуации..."
        )
        self.fallback_cache.set_default(
            "goal",
            {"goal": "wait", "reason": "Fallback goal - system degraded"}
        )
        self.fallback_cache.set_default(
            "action",
            {"action": "observe", "target": None}
        )
    
    async def _check_ollama_health(self) -> bool:
        """Health check for Ollama service."""
        try:
            # Simple test chat
            response = await self.circuit_breaker.call(
                self.ollama.chat,
                model=self.config.get('model', 'llama3.2:3b'),
                messages=[{"role": "user", "content": "test"}],
            )
            return response is not None
        except:
            return False
    
    def _on_health_change(self, service_name: str, status):
        """Handle health status changes."""
        if not status.healthy:
            logger.warning(
                f"[FaultTolerantHeavyTick] Service '{service_name}' "
                f"unhealthy - entering degraded mode"
            )
        else:
            logger.info(
                f"[FaultTolerantHeavyTick] Service '{service_name}' "
                f"recovered - exiting degraded mode"
            )
    
    async def start(self):
        """Start health monitoring."""
        await self.health_monitor.start()
        logger.info("[FaultTolerantHeavyTick] Started")
    
    async def stop(self):
        """Stop health monitoring."""
        await self.health_monitor.stop()
        logger.info("[FaultTolerantHeavyTick] Stopped")
    
    async def execute_heavy_tick(self, tick_number: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute fault-tolerant Heavy Tick.
        
        Args:
            tick_number: Current tick number
            context: System context and state
            
        Returns:
            Dict with results from all steps
        """
        logger.info(f"[HeavyTick #{tick_number}] Starting fault-tolerant execution")
        
        # Reset budget for new cycle
        self.budget_system.reset_cycle()
        
        start_time = time.time()
        results = {
            "tick_number": tick_number,
            "critical_steps": {},
            "optional_steps": {},
            "errors": [],
        }
        
        try:
            # === PHASE 1: Critical Sequential Steps ===
            
            # Step 1: Monologue (CRITICAL)
            monologue_result = await self._execute_critical_step(
                name="monologue",
                func=self._generate_monologue,
                args=(tick_number, context),
                priority=Priority.CRITICAL,
                llm_calls=1,
                timeout=30,
            )
            results["critical_steps"]["monologue"] = monologue_result
            
            # Step 2: Goal Selection (CRITICAL)
            goal_result = await self._execute_critical_step(
                name="goal",
                func=self._select_goal,
                args=(tick_number, monologue_result, context),
                priority=Priority.CRITICAL,
                llm_calls=3,  # Multiple LLM calls
                timeout=90,   # Longest timeout
            )
            results["critical_steps"]["goal"] = goal_result
            
            # Step 3: Action (CRITICAL)
            action_result = await self._execute_critical_step(
                name="action",
                func=self._execute_action,
                args=(tick_number, goal_result, context),
                priority=Priority.CRITICAL,
                llm_calls=2,
                timeout=45,
            )
            results["critical_steps"]["action"] = action_result
            
            # === PHASE 2: Optional Parallel Steps ===
            
            logger.info(f"[HeavyTick #{tick_number}] Starting parallel optional steps")
            
            optional_tasks = []
            
            # Curiosity (OPTIONAL)
            if self.budget_system.can_execute(Priority.OPTIONAL, llm_calls=1):
                optional_tasks.append(
                    self._execute_optional_step(
                        name="curiosity",
                        func=self._generate_curiosity,
                        args=(tick_number, context),
                        priority=Priority.OPTIONAL,
                        llm_calls=1,
                        timeout=30,
                    )
                )
            else:
                self.budget_system.record_skip(Priority.OPTIONAL, "Budget exhausted")
            
            # Beliefs (IMPORTANT)
            if self.budget_system.can_execute(Priority.IMPORTANT, llm_calls=1):
                optional_tasks.append(
                    self._execute_optional_step(
                        name="beliefs",
                        func=self._update_beliefs,
                        args=(tick_number, context),
                        priority=Priority.IMPORTANT,
                        llm_calls=1,
                        timeout=30,
                    )
                )
            
            # Social (OPTIONAL)
            if self.budget_system.can_execute(Priority.OPTIONAL, llm_calls=1):
                optional_tasks.append(
                    self._execute_optional_step(
                        name="social",
                        func=self._social_interaction,
                        args=(tick_number, context),
                        priority=Priority.OPTIONAL,
                        llm_calls=1,
                        timeout=25,
                    )
                )
            
            # Meta-Cognition (OPTIONAL)
            if self.budget_system.can_execute(Priority.OPTIONAL, llm_calls=1):
                optional_tasks.append(
                    self._execute_optional_step(
                        name="meta_cognition",
                        func=self._meta_cognition,
                        args=(tick_number, context),
                        priority=Priority.OPTIONAL,
                        llm_calls=1,
                        timeout=25,
                    )
                )
            
            # Execute all optional tasks in parallel
            if optional_tasks:
                optional_results = await asyncio.gather(
                    *optional_tasks,
                    return_exceptions=True
                )
                
                # Process results
                for result in optional_results:
                    if isinstance(result, dict) and "name" in result:
                        results["optional_steps"][result["name"]] = result["result"]
                    elif isinstance(result, Exception):
                        results["errors"].append(str(result))
            
            # === PHASE 3: Cleanup and Summary ===
            
            duration = time.time() - start_time
            results["duration"] = duration
            results["status"] = "success"
            
            # Log budget summary
            self.budget_system.log_summary()
            
            # Cleanup expired cache entries
            self.fallback_cache.cleanup_expired()
            
            logger.info(
                f"[HeavyTick #{tick_number}] Completed in {duration:.1f}s "
                f"(critical: {len(results['critical_steps'])}, "
                f"optional: {len(results['optional_steps'])}, "
                f"errors: {len(results['errors'])})"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"[HeavyTick #{tick_number}] Fatal error: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            return results
    
    async def _execute_critical_step(
        self,
        name: str,
        func,
        args: tuple,
        priority: Priority,
        llm_calls: int,
        timeout: int,
    ) -> Any:
        """
        Execute critical step with full fault tolerance.
        
        Critical steps ALWAYS execute, even if budget exhausted.
        Uses fallback cache if execution fails.
        """
        logger.info(f"[HeavyTick] STEP: {name} (CRITICAL, timeout={timeout}s)")
        
        step_start = time.time()
        
        try:
            # Execute with fallback strategy
            result = await asyncio.wait_for(
                self.fallback_strategy.execute(
                    key=name,
                    func=func,
                    args=args,
                    ttl=300,
                    use_expired=True,
                ),
                timeout=timeout
            )
            
            duration = time.time() - step_start
            self.budget_system.record_usage(priority, llm_calls=llm_calls, duration=duration)
            
            logger.info(f"[HeavyTick] Step '{name}' completed in {duration:.1f}s")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"[HeavyTick] Step '{name}' TIMEOUT after {timeout}s")
            # Use fallback
            fallback = self.fallback_cache.get(name, allow_expired=True)
            if fallback:
                logger.warning(f"[HeavyTick] Using cached fallback for '{name}'")
                return fallback
            raise
    
    async def _execute_optional_step(
        self,
        name: str,
        func,
        args: tuple,
        priority: Priority,
        llm_calls: int,
        timeout: int,
    ) -> Dict[str, Any]:
        """
        Execute optional step with fault tolerance.
        
        Optional steps can fail safely without breaking the system.
        """
        logger.debug(f"[HeavyTick] Optional step: {name}")
        
        step_start = time.time()
        
        try:
            result = await asyncio.wait_for(
                func(*args),
                timeout=timeout
            )
            
            duration = time.time() - step_start
            self.budget_system.record_usage(priority, llm_calls=llm_calls, duration=duration)
            
            return {"name": name, "result": result}
            
        except Exception as e:
            logger.warning(f"[HeavyTick] Optional step '{name}' failed: {e}")
            self.budget_system.record_skip(priority, f"Failed: {e}")
            return {"name": name, "result": None, "error": str(e)}
    
    # === Placeholder step implementations ===
    # These will be replaced with actual implementations from your system
    
    async def _generate_monologue(self, tick_number: int, context: dict) -> str:
        """Generate internal monologue."""
        # TODO: Implement actual monologue generation
        return "Monologue placeholder"
    
    async def _select_goal(self, tick_number: int, monologue: str, context: dict) -> dict:
        """Select current goal."""
        # TODO: Implement actual goal selection
        return {"goal": "placeholder", "reason": "test"}
    
    async def _execute_action(self, tick_number: int, goal: dict, context: dict) -> dict:
        """Execute action based on goal."""
        # TODO: Implement actual action execution
        return {"action": "placeholder"}
    
    async def _generate_curiosity(self, tick_number: int, context: dict) -> list:
        """Generate curiosity questions."""
        # TODO: Implement actual curiosity generation
        return []
    
    async def _update_beliefs(self, tick_number: int, context: dict) -> dict:
        """Update belief system."""
        # TODO: Implement actual belief updates
        return {}
    
    async def _social_interaction(self, tick_number: int, context: dict) -> dict:
        """Process social interactions."""
        # TODO: Implement actual social processing
        return {}
    
    async def _meta_cognition(self, tick_number: int, context: dict) -> dict:
        """Perform meta-cognitive analysis."""
        # TODO: Implement actual meta-cognition
        return {}