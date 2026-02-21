"""Circuit Breaker pattern for fault isolation."""

import asyncio
import time
from typing import Callable, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger("digital_being.circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Too many failures, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker for protecting against cascading failures.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Too many failures, calls blocked (return fallback)
    - HALF_OPEN: Testing recovery, limited calls allowed
    
    Behavior:
    - After `failure_threshold` failures → OPEN
    - After `timeout_duration` seconds → HALF_OPEN
    - If call succeeds in HALF_OPEN → CLOSED
    - If call fails in HALF_OPEN → OPEN again
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        timeout_duration: int = 60,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change = time.time()
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            fallback: Fallback function if circuit is OPEN
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or fallback result
            
        Raises:
            Exception: If circuit is OPEN and no fallback provided
        """
        self.total_calls += 1
        
        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"[CircuitBreaker:{self.name}] Transitioning OPEN → HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                logger.warning(f"[CircuitBreaker:{self.name}] Circuit OPEN, using fallback")
                if fallback:
                    return await self._call_fallback(fallback, *args, **kwargs)
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")
        
        # Try to execute function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            logger.error(f"[CircuitBreaker:{self.name}] Call failed: {e}")
            
            if fallback:
                return await self._call_fallback(fallback, *args, **kwargs)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.timeout_duration
    
    def _on_success(self):
        """Handle successful call."""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info(f"[CircuitBreaker:{self.name}] Recovery confirmed, HALF_OPEN → CLOSED")
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure counter on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"[CircuitBreaker:{self.name}] Recovery failed, HALF_OPEN → OPEN")
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"[CircuitBreaker:{self.name}] Failure threshold reached "
                    f"({self.failure_count}/{self.failure_threshold}), CLOSED → OPEN"
                )
                self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        self.success_count = 0
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self.failure_count = 0
        self.success_count = 0
    
    async def _call_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute fallback function."""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"[CircuitBreaker:{self.name}] Fallback failed: {e}")
            raise
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        uptime = time.time() - self.last_state_change
        success_rate = (
            (self.total_successes / self.total_calls * 100)
            if self.total_calls > 0
            else 0
        )
        
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": round(success_rate, 2),
            "failure_count": self.failure_count,
            "state_uptime_sec": round(uptime, 2),
        }
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"[CircuitBreaker:{self.name}] Manual reset")
        self._transition_to_closed()
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0