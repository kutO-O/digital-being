"""Health monitoring system for continuous service health checks."""

import asyncio
import time
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger('digital_being.health_monitor')


@dataclass
class HealthStatus:
    """Health status for a service."""
    service_name: str
    healthy: bool
    latency_ms: Optional[float]
    last_check: float
    consecutive_failures: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "service": self.service_name,
            "healthy": self.healthy,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "error": self.error_message,
        }


class HealthMonitor:
    """
    Continuous health monitoring for critical services.
    
    Monitors services in background and emits health change events.
    Detects:
    - Service unavailability
    - Degraded performance (high latency)
    - Intermittent failures
    
    Example:
        monitor = HealthMonitor(check_interval=30)
        
        # Register Ollama health check
        async def check_ollama():
            response = await ollama.chat("test")
            return response is not None
        
        monitor.register("ollama", check_ollama, latency_threshold=10.0)
        
        # Start monitoring
        await monitor.start()
        
        # Get current health
        if monitor.is_healthy("ollama"):
            result = await ollama.chat(prompt)
        else:
            result = use_cached_response()
    """
    
    def __init__(
        self,
        check_interval: int = 30,
        failure_threshold: int = 3,
    ):
        """
        Initialize health monitor.
        
        Args:
            check_interval: Seconds between health checks
            failure_threshold: Consecutive failures before marking unhealthy
        """
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        
        self.services: Dict[str, Callable] = {}
        self.thresholds: Dict[str, float] = {}
        self.statuses: Dict[str, HealthStatus] = {}
        self.listeners: List[Callable] = []
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info(
            f"[HealthMonitor] Initialized (interval={check_interval}s, "
            f"threshold={failure_threshold})"
        )
    
    def register(
        self,
        service_name: str,
        health_check: Callable,
        latency_threshold: float = 10.0,
    ):
        """
        Register a service for health monitoring.
        
        Args:
            service_name: Unique service identifier
            health_check: Async function that returns True if healthy
            latency_threshold: Max acceptable latency in seconds
        """
        self.services[service_name] = health_check
        self.thresholds[service_name] = latency_threshold
        self.statuses[service_name] = HealthStatus(
            service_name=service_name,
            healthy=True,
            latency_ms=None,
            last_check=time.time(),
            consecutive_failures=0,
        )
        logger.info(
            f"[HealthMonitor] Registered service '{service_name}' "
            f"(latency_threshold={latency_threshold}s)"
        )
    
    def add_listener(self, callback: Callable[[str, HealthStatus], None]):
        """
        Add health change event listener.
        
        Args:
            callback: Function called when health status changes
                      Signature: callback(service_name, new_status)
        """
        self.listeners.append(callback)
    
    async def start(self):
        """Start health monitoring loop."""
        if self._running:
            logger.warning("[HealthMonitor] Already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("[HealthMonitor] Started")
    
    async def stop(self):
        """Stop health monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[HealthMonitor] Stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Check all registered services
                for service_name in self.services:
                    await self._check_service(service_name)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HealthMonitor] Error in monitor loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _check_service(self, service_name: str):
        """Check health of a single service."""
        health_check = self.services[service_name]
        threshold = self.thresholds[service_name]
        old_status = self.statuses[service_name]
        
        start_time = time.time()
        
        try:
            # Execute health check
            result = await asyncio.wait_for(
                health_check(),
                timeout=threshold * 2  # Give extra time for check itself
            )
            
            latency = time.time() - start_time
            latency_ms = latency * 1000
            
            # Determine if healthy
            is_healthy = result and latency <= threshold
            
            # Create new status
            new_status = HealthStatus(
                service_name=service_name,
                healthy=is_healthy,
                latency_ms=latency_ms,
                last_check=time.time(),
                consecutive_failures=0 if is_healthy else old_status.consecutive_failures + 1,
                error_message=None if is_healthy else f"Latency {latency:.2f}s exceeds threshold {threshold}s",
            )
            
            # Check if exceeded failure threshold
            if new_status.consecutive_failures >= self.failure_threshold:
                new_status.healthy = False
            
            # Log status
            if is_healthy:
                logger.debug(
                    f"[HealthMonitor] {service_name}: healthy "
                    f"(latency={latency_ms:.0f}ms)"
                )
            else:
                logger.warning(
                    f"[HealthMonitor] {service_name}: degraded "
                    f"(latency={latency_ms:.0f}ms, threshold={threshold*1000:.0f}ms)"
                )
            
        except asyncio.TimeoutError:
            new_status = HealthStatus(
                service_name=service_name,
                healthy=False,
                latency_ms=None,
                last_check=time.time(),
                consecutive_failures=old_status.consecutive_failures + 1,
                error_message=f"Health check timeout (>{threshold*2}s)",
            )
            logger.warning(
                f"[HealthMonitor] {service_name}: timeout "
                f"({new_status.consecutive_failures}/{self.failure_threshold})"
            )
            
        except Exception as e:
            new_status = HealthStatus(
                service_name=service_name,
                healthy=False,
                latency_ms=None,
                last_check=time.time(),
                consecutive_failures=old_status.consecutive_failures + 1,
                error_message=str(e),
            )
            logger.error(
                f"[HealthMonitor] {service_name}: error - {e} "
                f"({new_status.consecutive_failures}/{self.failure_threshold})"
            )
        
        # Update status
        self.statuses[service_name] = new_status
        
        # Notify listeners if health changed
        if old_status.healthy != new_status.healthy:
            self._notify_listeners(service_name, new_status)
    
    def _notify_listeners(self, service_name: str, status: HealthStatus):
        """Notify listeners of health status change."""
        logger.info(
            f"[HealthMonitor] {service_name} health changed: "
            f"{'HEALTHY' if status.healthy else 'UNHEALTHY'}"
        )
        
        for listener in self.listeners:
            try:
                listener(service_name, status)
            except Exception as e:
                logger.error(f"[HealthMonitor] Listener error: {e}")
    
    def is_healthy(self, service_name: str) -> bool:
        """Check if service is currently healthy."""
        status = self.statuses.get(service_name)
        return status.healthy if status else False
    
    def get_status(self, service_name: str) -> Optional[HealthStatus]:
        """Get current health status for service."""
        return self.statuses.get(service_name)
    
    def get_all_statuses(self) -> Dict[str, HealthStatus]:
        """Get health statuses for all services."""
        return self.statuses.copy()
    
    def get_latency(self, service_name: str) -> Optional[float]:
        """Get last measured latency for service in milliseconds."""
        status = self.statuses.get(service_name)
        return status.latency_ms if status else None