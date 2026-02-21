"""Priority-based resource budget system."""

import time
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger('digital_being.priority_budget')


class Priority(Enum):
    """Task priority levels."""
    CRITICAL = "CRITICAL"    # Must always execute (monologue, goal, action)
    IMPORTANT = "IMPORTANT"  # Execute if budget available (emotions, beliefs)
    OPTIONAL = "OPTIONAL"    # Execute only with spare budget (curiosity, meta)


@dataclass
class BudgetConfig:
    """Budget configuration per priority level."""
    llm_calls: int          # Max LLM calls allowed
    timeout_seconds: int    # Max total time allowed
    
    def __repr__(self):
        return f"Budget(calls={self.llm_calls}, timeout={self.timeout_seconds}s)"


@dataclass
class BudgetUsage:
    """Track budget usage."""
    llm_calls: int = 0
    time_seconds: float = 0.0
    tasks_executed: int = 0
    tasks_skipped: int = 0
    
    def reset(self):
        """Reset usage counters."""
        self.llm_calls = 0
        self.time_seconds = 0.0
        self.tasks_executed = 0
        self.tasks_skipped = 0


class PriorityBudgetSystem:
    """
    Priority-based budget system for resource allocation.
    
    Ensures critical tasks always execute while optional tasks
    are skipped when resources are constrained.
    
    Example:
        budget = PriorityBudgetSystem(
            budgets={
                Priority.CRITICAL: BudgetConfig(llm_calls=15, timeout_seconds=120),
                Priority.IMPORTANT: BudgetConfig(llm_calls=10, timeout_seconds=60),
                Priority.OPTIONAL: BudgetConfig(llm_calls=5, timeout_seconds=30),
            }
        )
        
        # Critical task - always executes
        if budget.can_execute(Priority.CRITICAL, llm_calls=3):
            result = await generate_monologue()
            budget.record_usage(Priority.CRITICAL, llm_calls=3, duration=10.5)
        
        # Optional task - may skip if budget exhausted
        if budget.can_execute(Priority.OPTIONAL, llm_calls=2):
            result = await generate_curiosity()
        else:
            logger.info("Skipping curiosity - budget exhausted")
    """
    
    def __init__(
        self,
        budgets: Optional[Dict[Priority, BudgetConfig]] = None,
    ):
        """
        Initialize priority budget system.
        
        Args:
            budgets: Budget configuration per priority level
        """
        # Default budgets
        self.budgets = budgets or {
            Priority.CRITICAL: BudgetConfig(llm_calls=20, timeout_seconds=180),
            Priority.IMPORTANT: BudgetConfig(llm_calls=10, timeout_seconds=90),
            Priority.OPTIONAL: BudgetConfig(llm_calls=5, timeout_seconds=45),
        }
        
        # Track usage per priority
        self.usage = {
            Priority.CRITICAL: BudgetUsage(),
            Priority.IMPORTANT: BudgetUsage(),
            Priority.OPTIONAL: BudgetUsage(),
        }
        
        # Track cycle start time
        self.cycle_start_time = time.time()
        
        logger.info("[PriorityBudget] Initialized")
        for priority, budget in self.budgets.items():
            logger.info(f"  {priority.value}: {budget}")
    
    def can_execute(
        self,
        priority: Priority,
        llm_calls: int = 0,
        estimated_duration: float = 0.0,
    ) -> bool:
        """
        Check if task can execute within budget.
        
        Critical tasks ALWAYS return True.
        Important/Optional tasks check against available budget.
        
        Args:
            priority: Task priority level
            llm_calls: Estimated LLM calls needed
            estimated_duration: Estimated duration in seconds
            
        Returns:
            True if task should execute
        """
        # CRITICAL tasks always execute
        if priority == Priority.CRITICAL:
            return True
        
        budget = self.budgets[priority]
        used = self.usage[priority]
        
        # Check LLM call budget
        if used.llm_calls + llm_calls > budget.llm_calls:
            logger.debug(
                f"[PriorityBudget] {priority.value} LLM budget exhausted "
                f"({used.llm_calls + llm_calls}/{budget.llm_calls})"
            )
            return False
        
        # Check time budget
        if used.time_seconds + estimated_duration > budget.timeout_seconds:
            logger.debug(
                f"[PriorityBudget] {priority.value} time budget exhausted "
                f"({used.time_seconds + estimated_duration:.0f}/{budget.timeout_seconds}s)"
            )
            return False
        
        return True
    
    def record_usage(
        self,
        priority: Priority,
        llm_calls: int = 0,
        duration: float = 0.0,
    ):
        """
        Record resource usage for a task.
        
        Args:
            priority: Task priority level
            llm_calls: Number of LLM calls made
            duration: Task duration in seconds
        """
        used = self.usage[priority]
        used.llm_calls += llm_calls
        used.time_seconds += duration
        used.tasks_executed += 1
        
        budget = self.budgets[priority]
        
        logger.debug(
            f"[PriorityBudget] {priority.value} usage: "
            f"calls={used.llm_calls}/{budget.llm_calls}, "
            f"time={used.time_seconds:.0f}/{budget.timeout_seconds}s"
        )
    
    def record_skip(self, priority: Priority, reason: str = ""):
        """
        Record that a task was skipped.
        
        Args:
            priority: Task priority level
            reason: Reason for skip
        """
        self.usage[priority].tasks_skipped += 1
        logger.info(
            f"[PriorityBudget] Skipped {priority.value} task. Reason: {reason}"
        )
    
    def reset_cycle(self):
        """Reset budget for new cycle (e.g., new Heavy Tick)."""
        for usage in self.usage.values():
            usage.reset()
        self.cycle_start_time = time.time()
        logger.debug("[PriorityBudget] New cycle started")
    
    def get_remaining_budget(self, priority: Priority) -> BudgetConfig:
        """Get remaining budget for priority level."""
        budget = self.budgets[priority]
        used = self.usage[priority]
        
        return BudgetConfig(
            llm_calls=max(0, budget.llm_calls - used.llm_calls),
            timeout_seconds=max(0, budget.timeout_seconds - int(used.time_seconds)),
        )
    
    def get_usage_report(self) -> dict:
        """Get detailed usage report."""
        report = {
            "cycle_duration": time.time() - self.cycle_start_time,
            "priorities": {},
        }
        
        for priority in Priority:
            budget = self.budgets[priority]
            used = self.usage[priority]
            remaining = self.get_remaining_budget(priority)
            
            report["priorities"][priority.value] = {
                "budget": {
                    "llm_calls": budget.llm_calls,
                    "timeout_seconds": budget.timeout_seconds,
                },
                "used": {
                    "llm_calls": used.llm_calls,
                    "time_seconds": used.time_seconds,
                    "tasks_executed": used.tasks_executed,
                    "tasks_skipped": used.tasks_skipped,
                },
                "remaining": {
                    "llm_calls": remaining.llm_calls,
                    "timeout_seconds": remaining.timeout_seconds,
                },
                "utilization": {
                    "llm_calls_pct": (used.llm_calls / budget.llm_calls * 100) if budget.llm_calls > 0 else 0,
                    "time_pct": (used.time_seconds / budget.timeout_seconds * 100) if budget.timeout_seconds > 0 else 0,
                },
            }
        
        return report
    
    def log_summary(self):
        """Log budget usage summary."""
        logger.info("[PriorityBudget] Cycle Summary:")
        
        for priority in Priority:
            budget = self.budgets[priority]
            used = self.usage[priority]
            
            llm_pct = (used.llm_calls / budget.llm_calls * 100) if budget.llm_calls > 0 else 0
            time_pct = (used.time_seconds / budget.timeout_seconds * 100) if budget.timeout_seconds > 0 else 0
            
            logger.info(
                f"  {priority.value}: "
                f"calls={used.llm_calls}/{budget.llm_calls} ({llm_pct:.0f}%), "
                f"time={used.time_seconds:.0f}/{budget.timeout_seconds}s ({time_pct:.0f}%), "
                f"executed={used.tasks_executed}, skipped={used.tasks_skipped}"
            )