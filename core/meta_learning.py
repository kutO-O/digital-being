"""Meta-Learning - Self-Optimization."""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

log = logging.getLogger("digital_being.meta_learning")


class MetaOptimizer:
    """
    Self-optimization system.
    
    Performs:
    - A/B testing of prompts
    - Strategy optimization
    - Self-reflection on failures
    - Hyperparameter tuning
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path
        
        # A/B tests: name -> variants
        self._ab_tests: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self._metrics: Dict[str, List[float]] = {}
        
        # Best configurations
        self._best_configs: Dict[str, Any] = {}
        
        if storage_path and storage_path.exists():
            self.load()
    
    def register_ab_test(
        self,
        name: str,
        variants: List[Dict[str, Any]],
    ) -> None:
        """
        Register A/B test.
        
        Args:
            name: Test name
            variants: List of variants to test
        """
        self._ab_tests[name] = {
            "variants": variants,
            "results": {i: [] for i in range(len(variants))},
            "current_best": 0,
        }
        log.info(f"Registered A/B test '{name}' with {len(variants)} variants")
    
    def get_variant(self, test_name: str) -> Optional[Dict[str, Any]]:
        """
        Get variant for A/B test.
        
        Uses epsilon-greedy: mostly use best, sometimes explore.
        
        Returns:
            Variant dict or None
        """
        test = self._ab_tests.get(test_name)
        if not test:
            return None
        
        variants = test["variants"]
        
        # Epsilon-greedy (10% exploration)
        if random.random() < 0.1:
            # Explore: random variant
            idx = random.randint(0, len(variants) - 1)
        else:
            # Exploit: use current best
            idx = test["current_best"]
        
        return {"index": idx, "config": variants[idx]}
    
    def record_result(
        self,
        test_name: str,
        variant_index: int,
        success: bool,
        metric_value: float = 1.0,
    ) -> None:
        """
        Record result of A/B test variant.
        
        Args:
            test_name: Test name
            variant_index: Which variant was used
            success: Whether it succeeded
            metric_value: Performance metric (higher = better)
        """
        test = self._ab_tests.get(test_name)
        if not test:
            return
        
        # Record result
        value = metric_value if success else 0.0
        test["results"][variant_index].append(value)
        
        # Update best variant
        best_idx = 0
        best_avg = 0.0
        
        for idx, results in test["results"].items():
            if not results:
                continue
            avg = sum(results) / len(results)
            if avg > best_avg:
                best_avg = avg
                best_idx = idx
        
        test["current_best"] = best_idx
        
        log.debug(
            f"A/B test '{test_name}': variant {variant_index} "
            f"{'succeeded' if success else 'failed'}, "
            f"current best: {best_idx}"
        )
    
    def get_best_config(self, test_name: str) -> Optional[Dict[str, Any]]:
        """Get best configuration from A/B test."""
        test = self._ab_tests.get(test_name)
        if not test:
            return None
        
        best_idx = test["current_best"]
        return test["variants"][best_idx]
    
    def record_metric(self, metric_name: str, value: float) -> None:
        """Record performance metric."""
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []
        
        self._metrics[metric_name].append(value)
        
        # Keep last 100 values
        if len(self._metrics[metric_name]) > 100:
            self._metrics[metric_name] = self._metrics[metric_name][-100:]
    
    def get_metric_stats(self, metric_name: str) -> Dict[str, float]:
        """Get statistics for a metric."""
        values = self._metrics.get(metric_name, [])
        if not values:
            return {}
        
        return {
            "count": len(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "recent_avg": sum(values[-10:]) / min(len(values), 10),
        }
    
    def self_reflect(self, failure_description: str) -> str:
        """
        Reflect on a failure and generate hypothesis for improvement.
        
        Args:
            failure_description: What went wrong
        
        Returns:
            Hypothesis for improvement
        """
        # Simple reflection (in practice, would use LLM)
        hypotheses = [
            "Try breaking down the task into smaller steps",
            "Adjust timeout parameters",
            "Use different decomposition strategy",
            "Add more context to planning",
        ]
        
        return random.choice(hypotheses)
    
    def save(self) -> None:
        """Save to storage."""
        if not self._storage_path:
            return
        
        data = {
            "ab_tests": self._ab_tests,
            "metrics": self._metrics,
            "best_configs": self._best_configs,
        }
        
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    def load(self) -> None:
        """Load from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return
        
        data = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._ab_tests = data.get("ab_tests", {})
        self._metrics = data.get("metrics", {})
        self._best_configs = data.get("best_configs", {})