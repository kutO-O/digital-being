"""
Digital Being — Canary Deployment
Stage 30.8: Gradually deploys changes to minimize risk.
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("digital_being.canary_deployment")

class DeploymentStage(Enum):
    """Canary deployment stages"""
    VALIDATION = "validation"      # 0% - Testing phase
    CANARY = "canary"             # 10% - Small rollout
    PILOT = "pilot"               # 30% - Expanded rollout
    PRODUCTION = "production"     # 100% - Full deployment
    FAILED = "failed"             # Deployment failed
    ROLLED_BACK = "rolled_back"   # Rolled back

class CanaryDeployment:
    """
    Manages gradual deployment of code changes.
    
    Features:
    - Multi-stage rollout (0% → 10% → 30% → 100%)
    - Success criteria validation
    - Automatic progression or rollback
    - Health monitoring per stage
    - A/B comparison tracking
    """
    
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path / "canary_deployments.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._deployments: dict[str, dict] = {}
        self._load_deployments()
        
        # Stage configurations
        self._stage_config = {
            DeploymentStage.VALIDATION: {
                "traffic_percentage": 0,
                "min_duration": 60,        # 1 minute
                "required_successes": 5
            },
            DeploymentStage.CANARY: {
                "traffic_percentage": 10,
                "min_duration": 300,       # 5 minutes
                "required_successes": 20
            },
            DeploymentStage.PILOT: {
                "traffic_percentage": 30,
                "min_duration": 600,       # 10 minutes
                "required_successes": 50
            },
            DeploymentStage.PRODUCTION: {
                "traffic_percentage": 100,
                "min_duration": 0,
                "required_successes": 0
            }
        }
        
        log.info("CanaryDeployment initialized")
    
    def _load_deployments(self) -> None:
        """Load deployments from disk."""
        if self._storage_path.exists():
            try:
                with self._storage_path.open("r", encoding="utf-8") as f:
                    self._deployments = json.load(f)
                log.info(f"Loaded {len(self._deployments)} deployments")
            except Exception as e:
                log.error(f"Failed to load deployments: {e}")
    
    def _save_deployments(self) -> None:
        """Save deployments to disk."""
        try:
            with self._storage_path.open("w", encoding="utf-8") as f:
                json.dump(self._deployments, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to save deployments: {e}")
    
    def start_deployment(
        self,
        change_id: str,
        module_name: str,
        description: str,
        success_criteria: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Start a canary deployment.
        
        Args:
            change_id: Change ID
            module_name: Module being deployed
            description: Deployment description
            success_criteria: Success thresholds
        
        Returns:
            Deployment info
        """
        if change_id in self._deployments:
            return {
                "success": False,
                "error": "Deployment already exists"
            }
        
        # Default success criteria
        if success_criteria is None:
            success_criteria = {
                "min_success_rate": 0.95,   # 95%
                "max_error_rate": 0.05,      # 5%
                "max_avg_latency": 1.0       # 1 second
            }
        
        deployment = {
            "change_id": change_id,
            "module_name": module_name,
            "description": description,
            "stage": DeploymentStage.VALIDATION.value,
            "started_at": time.time(),
            "stage_started_at": time.time(),
            "success_criteria": success_criteria,
            "metrics": {
                "validation": {},
                "canary": {},
                "pilot": {},
                "production": {}
            },
            "stage_history": [],
            "status": "active"
        }
        
        self._deployments[change_id] = deployment
        self._save_deployments()
        
        log.info(
            f"Started canary deployment for {change_id} ({module_name})"
        )
        
        return {
            "success": True,
            "change_id": change_id,
            "stage": DeploymentStage.VALIDATION.value,
            "traffic_percentage": 0
        }
    
    def record_metrics(
        self,
        change_id: str,
        metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Record metrics for current deployment stage.
        
        Args:
            change_id: Change ID
            metrics: Metrics data (success_rate, error_rate, latency, etc.)
        
        Returns:
            Result with progression decision
        """
        if change_id not in self._deployments:
            return {
                "success": False,
                "error": "Deployment not found"
            }
        
        deployment = self._deployments[change_id]
        stage = DeploymentStage(deployment["stage"])
        
        # Store metrics for current stage
        stage_metrics = deployment["metrics"].get(stage.value, {})
        
        # Update metrics
        if "samples" not in stage_metrics:
            stage_metrics["samples"] = []
        
        stage_metrics["samples"].append({
            "timestamp": time.time(),
            **metrics
        })
        
        # Calculate aggregated metrics
        aggregated = self._aggregate_metrics(stage_metrics["samples"])
        stage_metrics["aggregated"] = aggregated
        
        deployment["metrics"][stage.value] = stage_metrics
        
        # Check if should progress or rollback
        decision = self._evaluate_stage(deployment, stage, aggregated)
        
        self._save_deployments()
        
        return decision
    
    def get_traffic_percentage(self, change_id: str) -> float:
        """
        Get current traffic percentage for a deployment.
        
        Args:
            change_id: Change ID
        
        Returns:
            Traffic percentage (0-100)
        """
        if change_id not in self._deployments:
            return 0.0
        
        deployment = self._deployments[change_id]
        stage = DeploymentStage(deployment["stage"])
        
        return self._stage_config[stage]["traffic_percentage"]
    
    def should_use_new_version(self, change_id: str) -> bool:
        """
        Determine if new version should be used (for traffic routing).
        
        Args:
            change_id: Change ID
        
        Returns:
            True if new version should be used
        """
        import random
        
        traffic_pct = self.get_traffic_percentage(change_id)
        
        # Random selection based on traffic percentage
        return random.random() < (traffic_pct / 100.0)
    
    def progress_stage(
        self,
        change_id: str,
        force: bool = False
    ) -> dict[str, Any]:
        """
        Progress deployment to next stage.
        
        Args:
            change_id: Change ID
            force: Force progression (skip checks)
        
        Returns:
            Result with new stage info
        """
        if change_id not in self._deployments:
            return {
                "success": False,
                "error": "Deployment not found"
            }
        
        deployment = self._deployments[change_id]
        current_stage = DeploymentStage(deployment["stage"])
        
        # Get next stage
        next_stage = self._get_next_stage(current_stage)
        
        if next_stage is None:
            return {
                "success": False,
                "error": "Already in final stage"
            }
        
        # Record stage transition
        deployment["stage_history"].append({
            "stage": current_stage.value,
            "started_at": deployment["stage_started_at"],
            "ended_at": time.time(),
            "duration": time.time() - deployment["stage_started_at"]
        })
        
        # Update to next stage
        deployment["stage"] = next_stage.value
        deployment["stage_started_at"] = time.time()
        
        self._save_deployments()
        
        log.info(
            f"Progressed deployment {change_id}: "
            f"{current_stage.value} → {next_stage.value}"
        )
        
        return {
            "success": True,
            "change_id": change_id,
            "previous_stage": current_stage.value,
            "new_stage": next_stage.value,
            "traffic_percentage": self._stage_config[next_stage]["traffic_percentage"]
        }
    
    def rollback(
        self,
        change_id: str,
        reason: str
    ) -> dict[str, Any]:
        """
        Rollback a deployment.
        
        Args:
            change_id: Change ID
            reason: Rollback reason
        
        Returns:
            Rollback result
        """
        if change_id not in self._deployments:
            return {
                "success": False,
                "error": "Deployment not found"
            }
        
        deployment = self._deployments[change_id]
        deployment["stage"] = DeploymentStage.ROLLED_BACK.value
        deployment["status"] = "rolled_back"
        deployment["rollback_reason"] = reason
        deployment["rolled_back_at"] = time.time()
        
        self._save_deployments()
        
        log.warning(f"🔄 Rolled back deployment {change_id}: {reason}")
        
        return {
            "success": True,
            "change_id": change_id,
            "reason": reason
        }
    
    def complete(
        self,
        change_id: str
    ) -> None:
        """Mark deployment as completed."""
        if change_id in self._deployments:
            deployment = self._deployments[change_id]
            deployment["status"] = "completed"
            deployment["completed_at"] = time.time()
            
            total_duration = time.time() - deployment["started_at"]
            deployment["total_duration"] = total_duration
            
            self._save_deployments()
            
            log.info(
                f"✅ Completed deployment {change_id} "
                f"(duration: {total_duration/60:.1f} minutes)"
            )
    
    def _evaluate_stage(
        self,
        deployment: dict,
        stage: DeploymentStage,
        metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate if stage should progress or rollback."""
        stage_config = self._stage_config[stage]
        success_criteria = deployment["success_criteria"]
        
        # Check minimum duration
        stage_duration = time.time() - deployment["stage_started_at"]
        if stage_duration < stage_config["min_duration"]:
            return {
                "action": "continue",
                "reason": "Minimum stage duration not reached",
                "stage": stage.value
            }
        
        # Check minimum samples
        sample_count = metrics.get("count", 0)
        if sample_count < stage_config["required_successes"]:
            return {
                "action": "continue",
                "reason": "Not enough samples collected",
                "stage": stage.value,
                "samples": sample_count,
                "required": stage_config["required_successes"]
            }
        
        # Check success criteria
        success_rate = metrics.get("success_rate", 0.0)
        error_rate = metrics.get("error_rate", 1.0)
        avg_latency = metrics.get("avg_latency", float('inf'))
        
        # Evaluate criteria
        if success_rate < success_criteria["min_success_rate"]:
            return {
                "action": "rollback",
                "reason": f"Low success rate: {success_rate:.2%}",
                "stage": stage.value
            }
        
        if error_rate > success_criteria["max_error_rate"]:
            return {
                "action": "rollback",
                "reason": f"High error rate: {error_rate:.2%}",
                "stage": stage.value
            }
        
        if avg_latency > success_criteria["max_avg_latency"]:
            return {
                "action": "rollback",
                "reason": f"High latency: {avg_latency:.3f}s",
                "stage": stage.value
            }
        
        # All criteria met - can progress
        return {
            "action": "progress",
            "reason": "All success criteria met",
            "stage": stage.value,
            "metrics": metrics
        }
    
    def _aggregate_metrics(self, samples: list[dict]) -> dict[str, Any]:
        """Aggregate metrics from samples."""
        if not samples:
            return {}
        
        count = len(samples)
        
        # Calculate averages
        success_rate = sum(s.get("success", 0) for s in samples) / count
        error_rate = sum(s.get("error", 0) for s in samples) / count
        
        latencies = [s.get("latency", 0) for s in samples if "latency" in s]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            "count": count,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "avg_latency": avg_latency,
            "last_updated": time.time()
        }
    
    def _get_next_stage(self, current: DeploymentStage) -> DeploymentStage | None:
        """Get next deployment stage."""
        stage_order = [
            DeploymentStage.VALIDATION,
            DeploymentStage.CANARY,
            DeploymentStage.PILOT,
            DeploymentStage.PRODUCTION
        ]
        
        try:
            idx = stage_order.index(current)
            if idx < len(stage_order) - 1:
                return stage_order[idx + 1]
        except ValueError:
            pass
        
        return None
    
    def get_deployment_status(self, change_id: str) -> dict[str, Any] | None:
        """Get status of a deployment."""
        if change_id not in self._deployments:
            return None
        
        deployment = self._deployments[change_id]
        stage = DeploymentStage(deployment["stage"])
        
        return {
            "change_id": change_id,
            "module_name": deployment["module_name"],
            "stage": stage.value,
            "traffic_percentage": self._stage_config[stage]["traffic_percentage"],
            "status": deployment["status"],
            "started_at": deployment["started_at"],
            "duration": time.time() - deployment["started_at"],
            "metrics": deployment["metrics"].get(stage.value, {})
        }
    
    def get_stats(self) -> dict[str, Any]:
        """Get deployment statistics."""
        active = sum(1 for d in self._deployments.values() if d["status"] == "active")
        completed = sum(1 for d in self._deployments.values() if d["status"] == "completed")
        rolled_back = sum(1 for d in self._deployments.values() if d["status"] == "rolled_back")
        
        return {
            "total_deployments": len(self._deployments),
            "active": active,
            "completed": completed,
            "rolled_back": rolled_back,
            "success_rate": completed / max(len(self._deployments), 1)
        }
