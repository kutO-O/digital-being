"""
Digital Being — Auto-Rollback Handler
Stage 30.4: Automatically rolls back problematic changes.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("digital_being.auto_rollback")

class AutoRollbackHandler:
    """
    Automatically rolls back changes that cause issues.
    
    Features:
    - Error detection
    - Performance regression detection
    - Automatic rollback triggers
    - Health monitoring
    - Rollback history
    """
    
    def __init__(self) -> None:
        self._rollback_count = 0
        self._triggers: dict[str, dict] = {}
        self._history: list[dict] = []
        
        # Rollback thresholds
        self._error_threshold = 3  # Rollback after N errors
        self._performance_threshold = 25.0  # Rollback if >25% regression
        self._timeout_threshold = 30.0  # Rollback if execution times out (seconds)
        
        log.info("AutoRollbackHandler initialized")
    
    def monitor_change(
        self,
        change_id: str,
        module_name: str,
        health_check: Callable[[], dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Start monitoring a change for automatic rollback.
        
        Args:
            change_id: Change ID to monitor
            module_name: Module name
            health_check: Optional health check function
        
        Returns:
            Monitoring configuration
        """
        self._triggers[change_id] = {
            "module_name": module_name,
            "started_at": time.time(),
            "error_count": 0,
            "health_check": health_check,
            "status": "monitoring"
        }
        
        log.info(f"Started monitoring change {change_id} for {module_name}")
        
        return {
            "change_id": change_id,
            "monitoring": True,
            "thresholds": {
                "errors": self._error_threshold,
                "performance": self._performance_threshold,
                "timeout": self._timeout_threshold
            }
        }
    
    def report_error(
        self,
        change_id: str,
        error: Exception | str,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Report an error for a monitored change.
        
        Args:
            change_id: Change ID
            error: Error that occurred
            context: Additional error context
        
        Returns:
            Result with rollback decision
        """
        if change_id not in self._triggers:
            return {
                "should_rollback": False,
                "reason": "Change not monitored"
            }
        
        trigger = self._triggers[change_id]
        trigger["error_count"] += 1
        
        error_str = str(error) if isinstance(error, Exception) else error
        
        log.warning(
            f"Error reported for change {change_id}: {error_str} "
            f"(count: {trigger['error_count']}/{self._error_threshold})"
        )
        
        # Check if threshold exceeded
        if trigger["error_count"] >= self._error_threshold:
            return self._trigger_rollback(
                change_id=change_id,
                reason=f"Error threshold exceeded: {trigger['error_count']} errors",
                details={
                    "last_error": error_str,
                    "context": context
                }
            )
        
        return {
            "should_rollback": False,
            "reason": "Error threshold not exceeded",
            "error_count": trigger["error_count"]
        }
    
    def check_performance(
        self,
        change_id: str,
        performance_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Check performance metrics and decide on rollback.
        
        Args:
            change_id: Change ID
            performance_data: Performance metrics with comparison
        
        Returns:
            Result with rollback decision
        """
        if change_id not in self._triggers:
            return {
                "should_rollback": False,
                "reason": "Change not monitored"
            }
        
        # Check for severe regressions
        comparison = performance_data.get("comparison")
        if not comparison or not comparison.get("has_regression"):
            return {
                "should_rollback": False,
                "reason": "No performance regression"
            }
        
        # Find worst regression
        worst_regression = 0.0
        worst_metric = None
        
        for reg in comparison.get("regressions", []):
            change_pct = abs(reg["change"])
            if change_pct > worst_regression:
                worst_regression = change_pct
                worst_metric = reg["metric"]
        
        # Trigger rollback if severe
        if worst_regression >= self._performance_threshold:
            return self._trigger_rollback(
                change_id=change_id,
                reason=f"Performance regression: {worst_metric} degraded by {worst_regression:.1f}%",
                details={
                    "regression_data": comparison["regressions"]
                }
            )
        
        return {
            "should_rollback": False,
            "reason": "Performance regression within threshold",
            "worst_regression": worst_regression
        }
    
    def check_timeout(
        self,
        change_id: str,
        execution_time: float
    ) -> dict[str, Any]:
        """
        Check if execution timed out.
        
        Args:
            change_id: Change ID
            execution_time: Execution time in seconds
        
        Returns:
            Result with rollback decision
        """
        if change_id not in self._triggers:
            return {
                "should_rollback": False,
                "reason": "Change not monitored"
            }
        
        if execution_time >= self._timeout_threshold:
            return self._trigger_rollback(
                change_id=change_id,
                reason=f"Execution timeout: {execution_time:.2f}s >= {self._timeout_threshold}s",
                details={
                    "execution_time": execution_time,
                    "threshold": self._timeout_threshold
                }
            )
        
        return {
            "should_rollback": False,
            "reason": "Execution within timeout"
        }
    
    def run_health_check(self, change_id: str) -> dict[str, Any]:
        """
        Run health check for a change.
        
        Args:
            change_id: Change ID
        
        Returns:
            Health check result with rollback decision
        """
        if change_id not in self._triggers:
            return {
                "should_rollback": False,
                "reason": "Change not monitored"
            }
        
        trigger = self._triggers[change_id]
        health_check = trigger.get("health_check")
        
        if not health_check:
            return {
                "should_rollback": False,
                "reason": "No health check configured"
            }
        
        try:
            result = health_check()
            
            if not result.get("healthy", True):
                return self._trigger_rollback(
                    change_id=change_id,
                    reason=f"Health check failed: {result.get('reason', 'Unknown')}",
                    details=result
                )
            
            return {
                "should_rollback": False,
                "reason": "Health check passed",
                "health_status": result
            }
        
        except Exception as e:
            log.error(f"Health check error for {change_id}: {e}")
            return self._trigger_rollback(
                change_id=change_id,
                reason=f"Health check error: {str(e)}",
                details={"error": str(e)}
            )
    
    def _trigger_rollback(
        self,
        change_id: str,
        reason: str,
        details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Trigger automatic rollback.
        
        Args:
            change_id: Change ID to rollback
            reason: Rollback reason
            details: Additional details
        
        Returns:
            Rollback trigger result
        """
        trigger = self._triggers[change_id]
        trigger["status"] = "rollback_triggered"
        
        self._rollback_count += 1
        
        # Record in history
        rollback_record = {
            "change_id": change_id,
            "module_name": trigger["module_name"],
            "reason": reason,
            "details": details or {},
            "triggered_at": time.time(),
            "monitoring_duration": time.time() - trigger["started_at"]
        }
        
        self._history.append(rollback_record)
        
        log.warning(
            f"🔄 AUTO-ROLLBACK TRIGGERED for {change_id}: {reason}"
        )
        
        return {
            "should_rollback": True,
            "reason": reason,
            "change_id": change_id,
            "module_name": trigger["module_name"],
            "details": details
        }
    
    def stop_monitoring(self, change_id: str) -> None:
        """Stop monitoring a change (it's stable)."""
        if change_id in self._triggers:
            trigger = self._triggers[change_id]
            trigger["status"] = "completed"
            duration = time.time() - trigger["started_at"]
            
            log.info(
                f"Stopped monitoring {change_id} after {duration:.1f}s "
                f"({trigger['error_count']} errors)"
            )
    
    def set_thresholds(
        self,
        error_threshold: int | None = None,
        performance_threshold: float | None = None,
        timeout_threshold: float | None = None
    ) -> None:
        """Update rollback thresholds."""
        if error_threshold is not None:
            self._error_threshold = error_threshold
        if performance_threshold is not None:
            self._performance_threshold = performance_threshold
        if timeout_threshold is not None:
            self._timeout_threshold = timeout_threshold
        
        log.info(
            f"Updated thresholds: errors={self._error_threshold}, "
            f"performance={self._performance_threshold}%, "
            f"timeout={self._timeout_threshold}s"
        )
    
    def get_rollback_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent rollback history."""
        return sorted(
            self._history,
            key=lambda r: r["triggered_at"],
            reverse=True
        )[:limit]
    
    def get_stats(self) -> dict[str, Any]:
        """Get rollback handler statistics."""
        active_monitoring = sum(
            1 for t in self._triggers.values()
            if t["status"] == "monitoring"
        )
        
        return {
            "total_rollbacks": self._rollback_count,
            "active_monitoring": active_monitoring,
            "thresholds": {
                "errors": self._error_threshold,
                "performance": self._performance_threshold,
                "timeout": self._timeout_threshold
            }
        }
