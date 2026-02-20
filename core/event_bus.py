"""
Digital Being — EventBus
Phase 2: Central async event system.

All modules communicate exclusively through EventBus.
No direct module-to-module calls allowed.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

log = logging.getLogger("digital_being.event_bus")

# Type alias: handler is an async function that receives event data
Handler = Callable[[dict], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async pub/sub event bus.

    Usage:
        bus = EventBus()
        await bus.subscribe("user.message", my_handler)
        await bus.publish("user.message", {"text": "hello"})
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        """Register an async handler for the given event name."""
        self._subscribers[event_name].append(handler)
        log.debug(f"Subscribed '{handler.__name__}' to '{event_name}'")

    async def publish(self, event_name: str, data: dict | None = None) -> None:
        """
        Publish an event to all subscribers.
        All handlers are called concurrently via asyncio.gather.
        """
        if data is None:
            data = {}

        handlers = self._subscribers.get(event_name, [])
        if not handlers:
            log.debug(f"Event '{event_name}' published but no subscribers.")
            return

        log.debug(f"Publishing '{event_name}' to {len(handlers)} handler(s). data={data}")

        results = await asyncio.gather(
            *[h(data) for h in handlers],
            return_exceptions=True,
        )

        # Log any handler exceptions without crashing the bus
        for handler, result in zip(handlers, results):
            if isinstance(result, Exception):
                log.error(
                    f"Handler '{handler.__name__}' raised on event '{event_name}': {result}",
                    exc_info=result,
                )
