"""
Digital Being — EventBus
Phase 2: Central async event system.

All modules communicate exclusively through EventBus.
No direct module-to-module calls allowed.

Features:
  - Async pub/sub pattern
  - Concurrent handler execution
  - Error isolation and tracking
  - Dead letter queue for critical events
  - Health reporting for monitoring

Changelog:
  TD-007 fix — added comprehensive error tracking and monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

log = logging.getLogger("digital_being.event_bus")

# Type alias: handler is an async function that receives event data
Handler = Callable[[dict], Coroutine[Any, Any, None]]


@dataclass
class ErrorRecord:
    """Record of a handler error for tracking."""
    timestamp: float
    event_name: str
    handler_name: str
    error: Exception
    data: dict


class EventBus:
    """
    Async pub/sub event bus with error tracking.

    Usage:
        bus = EventBus()
        bus.subscribe("user.message", my_handler)
        await bus.publish("user.message", {"text": "hello"})
        
        # Monitor health
        report = bus.get_health_report()
    """

    def __init__(self, max_error_history: int = 100) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        
        # TD-007: Error tracking
        self._error_history: deque[ErrorRecord] = deque(maxlen=max_error_history)
        self._handler_error_counts: dict[str, int] = defaultdict(int)
        self._dead_letter_queue: list[dict] = []
        self._critical_events = {"system.crash", "ollama.unavailable", "memory.full"}

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register an async handler for the given event name."""
        self._subscribers[event_name].append(handler)
        log.debug(f"Subscribed '{handler.__name__}' to '{event_name}'")

    async def publish(self, event_name: str, data: dict | None = None) -> None:
        """
        Publish an event to all subscribers.
        All handlers are called concurrently via asyncio.gather.
        Tracks errors and maintains dead letter queue for critical events.
        """
        if data is None:
            data = {}

        handlers = self._subscribers.get(event_name, [])
        if not handlers:
            log.debug(f"Event '{event_name}' published but no subscribers.")
            return

        log.debug(f"Publishing '{event_name}' to {len(handlers)} handler(s).")

        results = await asyncio.gather(
            *[h(data) for h in handlers],
            return_exceptions=True,
        )

        # Track handler errors
        for handler, result in zip(handlers, results):
            if isinstance(result, Exception):
                self._handle_error(
                    event_name=event_name,
                    handler=handler,
                    error=result,
                    data=data
                )

    def _handle_error(
        self, 
        event_name: str, 
        handler: Handler, 
        error: Exception, 
        data: dict
    ) -> None:
        """Track and log handler errors."""
        handler_name = handler.__name__
        
        # Record error
        error_record = ErrorRecord(
            timestamp=time.time(),
            event_name=event_name,
            handler_name=handler_name,
            error=error,
            data=data
        )
        self._error_history.append(error_record)
        self._handler_error_counts[handler_name] += 1
        
        # Add to dead letter queue if critical
        if self._is_critical_event(event_name):
            self._dead_letter_queue.append({
                "event_name": event_name,
                "data": data,
                "error": str(error),
                "handler": handler_name,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
            log.critical(
                f"⚠️ CRITICAL: Handler '{handler_name}' failed on "
                f"critical event '{event_name}': {error}"
            )
        
        # Log error with failure count
        failure_count = self._handler_error_counts[handler_name]
        log.error(
            f"Handler '{handler_name}' failed on '{event_name}'. "
            f"Total failures: {failure_count}",
            exc_info=error
        )
        
        # Alert if handler is repeatedly failing
        if failure_count >= 5:
            log.critical(
                f"⚠️ ALERT: Handler '{handler_name}' has failed "
                f"{failure_count} times! System may be unstable."
            )
    
    def _is_critical_event(self, event_name: str) -> bool:
        """Check if event is critical and should be queued on failure."""
        return event_name in self._critical_events
    
    def add_critical_event(self, event_name: str) -> None:
        """Mark an event type as critical."""
        self._critical_events.add(event_name)
        log.info(f"Marked '{event_name}' as critical event")
    
    def get_health_report(self) -> dict:
        """
        Get error statistics for monitoring.
        
        Returns:
            dict with:
              - total_errors: Total errors in history
              - errors_last_hour: Errors in past hour
              - dead_letter_queue_size: Critical events that failed
              - failing_handlers: Dict of handler -> failure count
              - recent_errors: Last 5 error details
        """
        now = time.time()
        one_hour_ago = now - 3600
        
        errors_last_hour = [
            e for e in self._error_history
            if e.timestamp > one_hour_ago
        ]
        
        recent_errors = [
            {
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", 
                    time.localtime(e.timestamp)
                ),
                "event_name": e.event_name,
                "handler_name": e.handler_name,
                "error": str(e.error)
            }
            for e in list(self._error_history)[-5:]
        ]
        
        return {
            "total_errors": len(self._error_history),
            "errors_last_hour": len(errors_last_hour),
            "dead_letter_queue_size": len(self._dead_letter_queue),
            "failing_handlers": dict(self._handler_error_counts),
            "recent_errors": recent_errors,
            "healthy": len(errors_last_hour) < 10  # Arbitrary threshold
        }
    
    def get_dead_letter_queue(self) -> list[dict]:
        """Get all critical events that failed."""
        return self._dead_letter_queue.copy()
    
    def clear_dead_letter_queue(self) -> int:
        """Clear dead letter queue and return count cleared."""
        count = len(self._dead_letter_queue)
        self._dead_letter_queue.clear()
        log.info(f"Cleared {count} items from dead letter queue")
        return count
