"""Health monitoring and auto-recovery system."""

import asyncio
import time
from typing import Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger("digital_being.health_monitor")


class SystemMode(Enum):
    """System operation modes."""
    NORMAL = "normal"          # All systems operational
    DEGRADED = "degraded"      # Some systems down, using fallbacks
    RECOVERY = "recovery"      # Attempting to recover
    EMERGENCY = "emergency"    # Critical failure, minimal operation


class ComponentHealth:
    """Track health status of a single component."""
    
    def __init__(self, name: str):
        self.name = name
        self.status = "unknown"
        self.last_check = None
        self.latency_ms = None
        self.error_count = 0
        self.consecutive_failures = 0
        self.last_error = None
    
    def mark_healthy(self, latency_ms: float):
        """Mark component as healthy."""
        self.status = "healthy"
        self.last_check = time.time()
        self.latency_ms = latency_ms
        self.consecutive_failures = 0
    
    def mark_unhealthy(self, error: str):
        """Mark component as unhealthy."""
        self.status = "unhealthy"
        self.last_check = time.time()
        self.error_count += 1
        self.consecutive_failures += 1
        self.last_error = error
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "error_count": self.error_count,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check,
            "last_error": self.last_error,
        }


class HealthMonitor:
    """
    Monitor system health and trigger auto-recovery.
    
    Responsibilities:
    - Check health of critical components (Ollama, memory, etc.)
    - Switch system modes based on component health
    - Trigger recovery actions
    - Provide health status for observability
    """
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.mode = SystemMode.NORMAL
        self.components: Dict[str, ComponentHealth] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Thresholds
        self.unhealthy_threshold = 3  # Consecutive failures before degraded
        self.latency_warning_ms = 5000  # 5 seconds
        self.latency_critical_ms = 15000  # 15 seconds
    
    def register_component(self, name: str):
        """Register a component for health monitoring."""
        self.components[name] = ComponentHealth(name)
        logger.info(f"[HealthMonitor] Registered component: {name}")
    
    async def start(self):
        """Start health monitoring loop."""
        if self._running:
            logger.warning("[HealthMonitor] Already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"[HealthMonitor] Started (interval={self.check_interval}s)")
    
    async def stop(self):
        """Stop health monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("[HealthMonitor] Stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self.check_all_components()
                self._update_system_mode()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HealthMonitor] Monitor loop error: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def check_all_components(self):
        """Check health of all registered components."""
        for name, health in self.components.items():
            try:
                await self.check_component(name)
            except Exception as e:
                logger.error(f"[HealthMonitor] Failed to check {name}: {e}")
    
    async def check_component(self, name: str) -> ComponentHealth:
        """
        Check health of specific component.
        Override this method to implement actual health checks.
        """
        health = self.components.get(name)
        if not health:
            raise ValueError(f"Component '{name}' not registered")
        
        # Default: assume healthy (override in subclass)
        health.mark_healthy(latency_ms=0)
        return health
    
    def _update_system_mode(self):
        """Update system mode based on component health."""
        unhealthy_count = sum(
            1 for h in self.components.values()
            if h.status == "unhealthy"
        )
        
        critical_count = sum(
            1 for h in self.components.values()
            if h.consecutive_failures >= self.unhealthy_threshold
        )
        
        old_mode = self.mode
        
        if critical_count > 0:
            self.mode = SystemMode.EMERGENCY
        elif unhealthy_count > 0:
            self.mode = SystemMode.DEGRADED
        else:
            # Check if recovering from degraded state
            if self.mode in (SystemMode.DEGRADED, SystemMode.RECOVERY):
                self.mode = SystemMode.RECOVERY
                # After 2 successful checks, return to normal
                all_healthy = all(
                    h.status == "healthy" and h.consecutive_failures == 0
                    for h in self.components.values()
                )
                if all_healthy:
                    self.mode = SystemMode.NORMAL
            else:
                self.mode = SystemMode.NORMAL
        
        if old_mode != self.mode:
            logger.warning(f"[HealthMonitor] System mode changed: {old_mode.value} → {self.mode.value}")
    
    def get_system_status(self) -> dict:
        """Get overall system health status."""
        return {
            "mode": self.mode.value,
            "components": {name: h.to_dict() for name, h in self.components.items()},
            "summary": self._get_summary(),
        }
    
    def _get_summary(self) -> dict:
        """Get health summary statistics."""
        total = len(self.components)
        healthy = sum(1 for h in self.components.values() if h.status == "healthy")
        unhealthy = total - healthy
        
        avg_latency = None
        if healthy > 0:
            latencies = [h.latency_ms for h in self.components.values() if h.latency_ms is not None]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
        
        return {
            "total_components": total,
            "healthy_count": healthy,
            "unhealthy_count": unhealthy,
            "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
        }