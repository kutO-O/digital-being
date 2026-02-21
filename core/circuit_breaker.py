"""Circuit Breaker pattern for preventing cascading failures."""

import time
import asyncio
from enum import Enum
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger('digital_being.circuit_breaker')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Too many failures, stop calling
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.
    
    Prevents cascading failures by automatically stopping calls to failing services.
    
    States:
    - CLOSED: Normal operation, all calls go through
    - OPEN: Too many failures detected, calls are rejected immediately
    - HALF_OPEN: Testing if service recovered, allow one call through
    
    Example:
        breaker = CircuitBreaker(name="ollama", failure_threshold=3, timeout=60)
        
        try:
            result = await breaker.call(ollama.chat, prompt="test")
        except CircuitBreakerOpenError:
            # Service is down, use fallback
            result = use_cached_response()
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        timeout: int = 60,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name of the protected service
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before testing recovery (OPEN -> HALF_OPEN)
            success_threshold: Successes needed in HALF_OPEN to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change = time.time()
        
        logger.info(
            f"[CircuitBreaker:{name}] Initialized "
            f"(threshold={failure_threshold}, timeout={timeout}s)"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async or sync function to call
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is OPEN
            Exception: Original exception from function
        """
        # Check if circuit is OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable for {self._time_until_retry():.0f}s"
                )
        
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - record it
            self._on_success()
            return result
            
        except Exception as e:
            # Failure - record it
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failures = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            logger.info(
                f"[CircuitBreaker:{self.name}] Success in HALF_OPEN state "
                f"({self.successes}/{self.success_threshold})"
            )
            
            if self.successes >= self.success_threshold:
                self._transition_to_closed()
        
    def _on_failure(self, exception: Exception):
        """Handle failed call."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        logger.warning(
            f"[CircuitBreaker:{self.name}] Failure recorded: {exception} "
            f"({self.failures}/{self.failure_threshold})"
        )
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed in HALF_OPEN - go back to OPEN
            self._transition_to_open()
        elif self.failures >= self.failure_threshold:
            # Too many failures in CLOSED - open circuit
            self._transition_to_open()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.timeout
    
    def _time_until_retry(self) -> float:
        """Calculate seconds until retry is allowed."""
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.timeout - elapsed)
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        if self.state != CircuitState.OPEN:
            logger.error(
                f"[CircuitBreaker:{self.name}] Circuit OPENED. "
                f"Service will be unavailable for {self.timeout}s"
            )
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        logger.info(
            f"[CircuitBreaker:{self.name}] Circuit HALF_OPEN. "
            f"Testing service recovery..."
        )
        self.state = CircuitState.HALF_OPEN
        self.successes = 0
        self.last_state_change = time.time()
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        logger.info(
            f"[CircuitBreaker:{self.name}] Circuit CLOSED. "
            f"Service recovered!"
        )
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_state_change = time.time()
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "successes": self.successes,
            "last_failure_time": self.last_failure_time,
            "time_in_current_state": time.time() - self.last_state_change,
            "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else 0,
        }
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"[CircuitBreaker:{self.name}] Manual reset")
        self._transition_to_closed()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and call is rejected."""
    pass