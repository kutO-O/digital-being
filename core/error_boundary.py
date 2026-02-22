"""
Digital Being — Error Boundary
Added: TD-018 fix for fault tolerance.

Provides error boundaries with fallback strategies to prevent
single component failures from crashing the entire system.

Usage:
    boundary = ErrorBoundary(
        ErrorBoundaryConfig(
            strategy=FallbackStrategy.USE_CACHE,
            max_retries=3
        )
    )
    
    result = await boundary.execute(
        operation=lambda: risky_function(),
        context="component_name"
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar

log = logging.getLogger("digital_being.error_boundary")

T = TypeVar('T')


class FallbackStrategy(Enum):
    """Strategy to use when operation fails after all retries."""
    RETURN_DEFAULT = "return_default"  # Return a default value
    USE_CACHE = "use_cache"            # Use last successful value
    SKIP_STEP = "skip_step"            # Return None and continue
    RETRY = "retry"                    # Keep retrying (use with caution)


@dataclass
class ErrorBoundaryConfig:
    """Configuration for error boundary behavior."""
    strategy: FallbackStrategy
    max_retries: int = 3
    base_delay: float = 1.0  # Initial backoff delay in seconds
    default_value: Any = None
    cache_ttl: int = 300  # Cache time-to-live in seconds


class ErrorBoundary:
    """
    Wraps operations with error handling and fallback strategies.
    
    Prevents single component failures from crashing the entire system.
    """
    
    def __init__(self, config: ErrorBoundaryConfig) -> None:
        self.config = config
        self._consecutive_failures = 0
        self._last_success_time: float | None = None
        self._cached_value: Any = None
        self._total_calls = 0
        self._total_failures = 0
    
    async def execute(
        self, 
        operation: Callable[[], T], 
        context: str,
        timeout: float | None = None
    ) -> T | None:
        """
        Execute operation with error boundary protection.
        
        Args:
            operation: Async or sync callable to execute
            context: Description for logging (e.g. "ollama.chat")
            timeout: Optional timeout in seconds
        
        Returns:
            Result from operation, or fallback value on failure
        """
        self._total_calls += 1
        
        # Try operation with retries
        last_error = None
        delay = self.config.base_delay
        
        for attempt in range(self.config.max_retries):
            try:
                # Execute with optional timeout
                if timeout:
                    if asyncio.iscoroutinefunction(operation):
                        result = await asyncio.wait_for(
                            operation(),
                            timeout=timeout
                        )
                    else:
                        # Sync function with timeout
                        loop = asyncio.get_event_loop()
                        result = await asyncio.wait_for(
                            loop.run_in_executor(None, operation),
                            timeout=timeout
                        )
                else:
                    # No timeout
                    if asyncio.iscoroutinefunction(operation):
                        result = await operation()
                    else:
                        result = operation()
                
                # Success!
                self._consecutive_failures = 0
                self._last_success_time = time.time()
                self._cached_value = result
                
                if attempt > 0:
                    log.info(
                        f"{context}: Succeeded on attempt {attempt + 1}/{self.config.max_retries}"
                    )
                
                return result
                
            except asyncio.TimeoutError as e:
                last_error = e
                self._consecutive_failures += 1
                self._total_failures += 1
                
                log.warning(
                    f"{context}: Timeout on attempt {attempt + 1}/{self.config.max_retries}"
                )
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2.0  # Exponential backoff
            
            except Exception as e:
                last_error = e
                self._consecutive_failures += 1
                self._total_failures += 1
                
                log.warning(
                    f"{context}: Failed on attempt {attempt + 1}/{self.config.max_retries}: {e}"
                )
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2.0  # Exponential backoff
        
        # All retries failed - use fallback
        log.error(
            f"{context}: All {self.config.max_retries} attempts failed. "
            f"Using fallback strategy: {self.config.strategy.value}"
        )
        
        return self._fallback(context, last_error)
    
    def _fallback(self, context: str, error: Exception | None) -> Any:
        """Apply configured fallback strategy."""
        
        if self.config.strategy == FallbackStrategy.RETURN_DEFAULT:
            log.info(f"{context}: Returning default value: {self.config.default_value}")
            return self.config.default_value
        
        elif self.config.strategy == FallbackStrategy.USE_CACHE:
            if self._cached_value is not None:
                cache_age = time.time() - (self._last_success_time or 0)
                if cache_age < self.config.cache_ttl:
                    log.info(
                        f"{context}: Using cached value from {cache_age:.0f}s ago"
                    )
                    return self._cached_value
                else:
                    log.warning(
                        f"{context}: Cache expired ({cache_age:.0f}s > {self.config.cache_ttl}s). "
                        f"Returning None"
                    )
            else:
                log.warning(f"{context}: No cached value available. Returning None")
            return None
        
        elif self.config.strategy == FallbackStrategy.SKIP_STEP:
            log.info(f"{context}: Skipping step (returning None)")
            return None
        
        else:  # RETRY - should not reach here normally
            log.error(f"{context}: RETRY strategy not implemented in fallback")
            return None
    
    def get_stats(self) -> dict:
        """Get error boundary statistics."""
        failure_rate = (
            self._total_failures / self._total_calls 
            if self._total_calls > 0 
            else 0.0
        )
        
        cache_age = (
            time.time() - self._last_success_time 
            if self._last_success_time 
            else None
        )
        
        return {
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "consecutive_failures": self._consecutive_failures,
            "failure_rate": failure_rate,
            "has_cached_value": self._cached_value is not None,
            "cache_age_seconds": cache_age,
            "last_success_time": (
                time.strftime(
                    "%Y-%m-%dT%H:%M:%S",
                    time.localtime(self._last_success_time)
                ) if self._last_success_time else None
            )
        }
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._total_calls = 0
        self._total_failures = 0
        self._consecutive_failures = 0
        log.debug("Error boundary stats reset")


class ErrorBoundaryFactory:
    """
    Factory for creating pre-configured error boundaries.
    """
    
    @staticmethod
    def for_ollama() -> ErrorBoundary:
        """Error boundary for Ollama LLM calls - use cache on failure."""
        return ErrorBoundary(
            ErrorBoundaryConfig(
                strategy=FallbackStrategy.USE_CACHE,
                max_retries=3,
                base_delay=1.0,
                cache_ttl=600  # 10 minutes
            )
        )
    
    @staticmethod
    def for_memory_write() -> ErrorBoundary:
        """Error boundary for memory writes - skip on failure."""
        return ErrorBoundary(
            ErrorBoundaryConfig(
                strategy=FallbackStrategy.SKIP_STEP,
                max_retries=2,
                base_delay=0.5
            )
        )
    
    @staticmethod
    def for_file_operation() -> ErrorBoundary:
        """Error boundary for file I/O - retry with backoff."""
        return ErrorBoundary(
            ErrorBoundaryConfig(
                strategy=FallbackStrategy.SKIP_STEP,
                max_retries=3,
                base_delay=1.0
            )
        )
    
    @staticmethod
    def for_critical_operation(default_value: Any = None) -> ErrorBoundary:
        """Error boundary for critical ops - return default."""
        return ErrorBoundary(
            ErrorBoundaryConfig(
                strategy=FallbackStrategy.RETURN_DEFAULT,
                max_retries=5,
                base_delay=2.0,
                default_value=default_value
            )
        )
