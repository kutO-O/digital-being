"""Priority-based execution system with graceful degradation."""

import asyncio
import time
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import logging

logger = logging.getLogger("digital_being.priority_system")


class Priority(Enum):
    """Task priority levels."""
    CRITICAL = "critical"    # Must execute, system fails without it
    IMPORTANT = "important"  # Should execute, can use fallback
    OPTIONAL = "optional"    # Nice to have, skip if no resources


class StepResult:
    """Result of a step execution."""
    
    def __init__(
        self,
        step_name: str,
        success: bool,
        result: Any = None,
        error: Optional[str] = None,
        used_fallback: bool = False,
        execution_time_ms: float = 0,
    ):
        self.step_name = step_name
        self.success = success
        self.result = result
        self.error = error
        self.used_fallback = used_fallback
        self.execution_time_ms = execution_time_ms
        self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "used_fallback": self.used_fallback,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
        }


class PriorityExecutor:
    """
    Execute tasks based on priority with graceful degradation.
    
    Features:
    - Priority-based execution order
    - Budget management per priority level
    - Automatic fallback on failure
    - Result caching for future fallbacks
    - Graceful degradation under load
    """
    
    def __init__(self):
        self.budgets = {
            Priority.CRITICAL: 15,   # Always execute, high budget
            Priority.IMPORTANT: 8,   # Execute if possible
            Priority.OPTIONAL: 3,    # Execute only if resources available
        }
        
        # Cache recent results for fallback
        self.result_cache: Dict[str, StepResult] = {}
        self.cache_max_age = 300  # 5 minutes
        
        # Statistics
        self.stats = {
            "critical_executed": 0,
            "important_executed": 0,
            "optional_executed": 0,
            "fallbacks_used": 0,
            "total_skipped": 0,
        }
    
    async def execute_step(
        self,
        step_name: str,
        func: Callable,
        priority: Priority,
        timeout: int,
        fallback: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> StepResult:
        """
        Execute a step with priority-based resource allocation.
        
        Args:
            step_name: Name of the step
            func: Async function to execute
            priority: Priority level
            timeout: Timeout in seconds
            fallback: Fallback function if execution fails
            *args, **kwargs: Arguments for func
            
        Returns:
            StepResult with execution outcome
        """
        start_time = time.time()
        
        # Check budget
        if not self._has_budget(priority):
            logger.warning(
                f"[PriorityExecutor] No budget for {priority.value} step '{step_name}', using fallback"
            )
            return await self._use_fallback(step_name, fallback, *args, **kwargs)
        
        # Try execution
        try:
            logger.info(f"[PriorityExecutor] Executing {priority.value} step '{step_name}' (timeout={timeout}s)")
            
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            
            execution_time = (time.time() - start_time) * 1000
            step_result = StepResult(
                step_name=step_name,
                success=True,
                result=result,
                execution_time_ms=execution_time,
            )
            
            # Cache successful result
            self.result_cache[step_name] = step_result
            self._update_stats(priority, success=True)
            
            logger.info(
                f"[PriorityExecutor] Step '{step_name}' completed successfully ({execution_time:.0f}ms)"
            )
            return step_result
            
        except asyncio.TimeoutError:
            logger.warning(f"[PriorityExecutor] Step '{step_name}' timed out after {timeout}s")
            return await self._use_fallback(step_name, fallback, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"[PriorityExecutor] Step '{step_name}' failed: {e}")
            return await self._use_fallback(step_name, fallback, *args, **kwargs)
    
    async def _use_fallback(
        self,
        step_name: str,
        fallback: Optional[Callable],
        *args,
        **kwargs
    ) -> StepResult:
        """
        Use fallback strategy when step fails.
        
        Fallback hierarchy:
        1. Custom fallback function
        2. Cached result from previous execution
        3. Default empty result
        """
        # Try custom fallback
        if fallback:
            try:
                logger.info(f"[PriorityExecutor] Using custom fallback for '{step_name}'")
                if asyncio.iscoroutinefunction(fallback):
                    result = await fallback(*args, **kwargs)
                else:
                    result = fallback(*args, **kwargs)
                
                self.stats["fallbacks_used"] += 1
                return StepResult(
                    step_name=step_name,
                    success=True,
                    result=result,
                    used_fallback=True,
                )
            except Exception as e:
                logger.error(f"[PriorityExecutor] Fallback for '{step_name}' failed: {e}")
        
        # Try cached result
        cached = self._get_cached_result(step_name)
        if cached:
            logger.info(f"[PriorityExecutor] Using cached result for '{step_name}'")
            self.stats["fallbacks_used"] += 1
            cached.used_fallback = True
            return cached
        
        # Default: return error result
        logger.warning(f"[PriorityExecutor] No fallback available for '{step_name}', returning empty result")
        self.stats["total_skipped"] += 1
        return StepResult(
            step_name=step_name,
            success=False,
            error="No fallback available",
        )
    
    def _get_cached_result(self, step_name: str) -> Optional[StepResult]:
        """Get cached result if still valid."""
        cached = self.result_cache.get(step_name)
        if not cached:
            return None
        
        age = time.time() - cached.timestamp
        if age > self.cache_max_age:
            logger.debug(f"[PriorityExecutor] Cached result for '{step_name}' expired ({age:.0f}s old)")
            del self.result_cache[step_name]
            return None
        
        return cached
    
    def _has_budget(self, priority: Priority) -> bool:
        """Check if priority level has budget remaining."""
        return self.budgets[priority] > 0
    
    def _update_stats(self, priority: Priority, success: bool):
        """Update execution statistics."""
        if success:
            if priority == Priority.CRITICAL:
                self.stats["critical_executed"] += 1
            elif priority == Priority.IMPORTANT:
                self.stats["important_executed"] += 1
            elif priority == Priority.OPTIONAL:
                self.stats["optional_executed"] += 1
    
    def reset_budgets(self):
        """Reset budgets for new execution cycle."""
        self.budgets = {
            Priority.CRITICAL: 15,
            Priority.IMPORTANT: 8,
            Priority.OPTIONAL: 3,
        }
    
    def get_stats(self) -> dict:
        """Get execution statistics."""
        total_executed = (
            self.stats["critical_executed"] +
            self.stats["important_executed"] +
            self.stats["optional_executed"]
        )
        
        return {
            **self.stats,
            "total_executed": total_executed,
            "cached_results": len(self.result_cache),
        }