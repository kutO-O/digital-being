"""
Digital Being — Performance Monitor
Stage 30.3: Monitors performance before and after code changes.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("digital_being.performance_monitor")

class PerformanceMonitor:
    """
    Monitors performance metrics for code changes.
    
    Features:
    - Baseline metric capture
    - Post-change comparison
    - Performance regression detection
    - Metric history tracking
    - Automated rollback triggers
    """
    
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path / "performance_metrics.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._metrics: dict[str, dict] = {}
        self._baselines: dict[str, dict] = {}
        self._load_metrics()
        
        log.info("PerformanceMonitor initialized")
    
    def _load_metrics(self) -> None:
        """Load saved metrics."""
        if self._storage_path.exists():
            try:
                with self._storage_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._metrics = data.get("metrics", {})
                    self._baselines = data.get("baselines", {})
                log.info(f"Loaded metrics for {len(self._metrics)} modules")
            except Exception as e:
                log.error(f"Failed to load metrics: {e}")
    
    def _save_metrics(self) -> None:
        """Save metrics to disk."""
        try:
            data = {
                "metrics": self._metrics,
                "baselines": self._baselines,
                "last_updated": time.time()
            }
            with self._storage_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to save metrics: {e}")
    
    def capture_baseline(
        self,
        module_name: str,
        metrics: dict[str, Any]
    ) -> None:
        """
        Capture baseline metrics before change.
        
        Args:
            module_name: Module name
            metrics: Metrics dictionary (execution_time, memory_usage, etc.)
        """
        self._baselines[module_name] = {
            "metrics": metrics,
            "captured_at": time.time()
        }
        self._save_metrics()
        
        log.info(f"Captured baseline for {module_name}: {metrics}")
    
    def capture_post_change(
        self,
        module_name: str,
        change_id: str,
        metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Capture metrics after change and compare with baseline.
        
        Args:
            module_name: Module name
            change_id: Change ID
            metrics: New metrics
        
        Returns:
            Comparison result with regression detection
        """
        # Store new metrics
        if module_name not in self._metrics:
            self._metrics[module_name] = {}
        
        self._metrics[module_name][change_id] = {
            "metrics": metrics,
            "captured_at": time.time()
        }
        
        # Compare with baseline if available
        comparison = None
        if module_name in self._baselines:
            comparison = self._compare_metrics(
                baseline=self._baselines[module_name]["metrics"],
                current=metrics
            )
        
        self._save_metrics()
        
        result = {
            "module_name": module_name,
            "change_id": change_id,
            "metrics": metrics,
            "comparison": comparison
        }
        
        if comparison and comparison["has_regression"]:
            log.warning(
                f"Performance regression detected in {module_name}: "
                f"{comparison['regressions']}"
            )
        else:
            log.info(f"Performance metrics captured for {module_name}")
        
        return result
    
    def _compare_metrics(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Compare current metrics with baseline.
        
        Args:
            baseline: Baseline metrics
            current: Current metrics
        
        Returns:
            Comparison with improvements and regressions
        """
        improvements = []
        regressions = []
        changes = {}
        
        # Compare each metric
        for key in baseline:
            if key not in current:
                continue
            
            baseline_val = baseline[key]
            current_val = current[key]
            
            # Skip non-numeric values
            if not isinstance(baseline_val, (int, float)) or not isinstance(current_val, (int, float)):
                continue
            
            # Calculate percentage change
            if baseline_val == 0:
                continue
            
            change_pct = ((current_val - baseline_val) / baseline_val) * 100
            changes[key] = {
                "baseline": baseline_val,
                "current": current_val,
                "change_pct": change_pct
            }
            
            # Determine if improvement or regression
            # Lower is better for time/memory metrics
            if key in ["execution_time", "memory_usage", "cpu_time"]:
                if change_pct < -5:  # 5% improvement threshold
                    improvements.append({"metric": key, "change": change_pct})
                elif change_pct > 10:  # 10% regression threshold
                    regressions.append({"metric": key, "change": change_pct})
            # Higher is better for throughput/efficiency metrics
            elif key in ["throughput", "efficiency", "success_rate"]:
                if change_pct > 5:
                    improvements.append({"metric": key, "change": change_pct})
                elif change_pct < -10:
                    regressions.append({"metric": key, "change": change_pct})
        
        return {
            "has_regression": len(regressions) > 0,
            "has_improvement": len(improvements) > 0,
            "regressions": regressions,
            "improvements": improvements,
            "all_changes": changes
        }
    
    def measure_execution(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        Measure execution metrics of a function.
        
        Args:
            func: Function to measure
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Execution metrics
        """
        import tracemalloc
        import sys
        
        # Start memory tracking
        tracemalloc.start()
        start_time = time.perf_counter()
        start_cpu = time.process_time()
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        # Capture metrics
        end_time = time.perf_counter()
        end_cpu = time.process_time()
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics = {
            "execution_time": end_time - start_time,
            "cpu_time": end_cpu - start_cpu,
            "memory_current": current_mem / 1024 / 1024,  # MB
            "memory_peak": peak_mem / 1024 / 1024,  # MB
            "success": success,
            "error": error
        }
        
        return {
            "result": result,
            "metrics": metrics
        }
    
    def should_rollback(
        self,
        module_name: str,
        change_id: str,
        threshold: float = 20.0
    ) -> tuple[bool, str]:
        """
        Determine if a change should be rolled back based on performance.
        
        Args:
            module_name: Module name
            change_id: Change ID
            threshold: Regression threshold percentage
        
        Returns:
            (should_rollback, reason)
        """
        if module_name not in self._metrics or change_id not in self._metrics[module_name]:
            return False, "No metrics found"
        
        metrics_data = self._metrics[module_name][change_id]
        
        # Check if we have baseline for comparison
        if module_name not in self._baselines:
            return False, "No baseline for comparison"
        
        comparison = self._compare_metrics(
            baseline=self._baselines[module_name]["metrics"],
            current=metrics_data["metrics"]
        )
        
        # Check for severe regressions
        if comparison["has_regression"]:
            for regression in comparison["regressions"]:
                if abs(regression["change"]) > threshold:
                    reason = f"Severe regression in {regression['metric']}: {regression['change']:.1f}%"
                    return True, reason
        
        return False, "Performance acceptable"
    
    def get_module_history(
        self,
        module_name: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get performance history for a module."""
        if module_name not in self._metrics:
            return []
        
        history = []
        for change_id, data in self._metrics[module_name].items():
            history.append({
                "change_id": change_id,
                "metrics": data["metrics"],
                "captured_at": data["captured_at"]
            })
        
        # Sort by time, newest first
        history.sort(key=lambda x: x["captured_at"], reverse=True)
        
        return history[:limit]
    
    def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        total_modules = len(self._metrics)
        total_measurements = sum(len(changes) for changes in self._metrics.values())
        modules_with_baseline = len(self._baselines)
        
        return {
            "monitored_modules": total_modules,
            "total_measurements": total_measurements,
            "modules_with_baseline": modules_with_baseline
        }
