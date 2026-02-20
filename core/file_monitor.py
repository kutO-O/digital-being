"""
Digital Being — FileMonitor
Phase 2: Filesystem watcher using watchdog.

Monitors the project directory (read-only observation) and publishes
events to the EventBus when files are created, modified, or deleted.
Runs in a background thread — does NOT block the async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from core.event_bus import EventBus

log = logging.getLogger("digital_being.file_monitor")

# Directories to ignore — runtime data, not meaningful world signals
IGNORED_DIRS = {"memory", "logs", ".git", "__pycache__", ".venv", "venv"}


class _EventHandler(FileSystemEventHandler):
    """
    Watchdog event handler.
    Bridges the watchdog thread into the asyncio event loop.
    """

    def __init__(self, bus: EventBus, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._bus  = bus
        self._loop = loop

    def _should_ignore(self, path: str) -> bool:
        parts = Path(path).parts
        return any(part in IGNORED_DIRS for part in parts)

    def _emit(self, event_name: str, path: str) -> None:
        if self._should_ignore(path):
            return
        data = {"path": path}
        # Schedule coroutine safely from watchdog's background thread
        asyncio.run_coroutine_threadsafe(
            self._bus.publish(event_name, data),
            self._loop,
        )

    def on_modified(self, event: FileModifiedEvent) -> None:   # type: ignore[override]
        if not event.is_directory:
            log.debug(f"File modified: {event.src_path}")
            self._emit("world.file_changed", event.src_path)

    def on_created(self, event: FileCreatedEvent) -> None:    # type: ignore[override]
        if not event.is_directory:
            log.debug(f"File created: {event.src_path}")
            self._emit("world.file_created", event.src_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:    # type: ignore[override]
        if not event.is_directory:
            log.debug(f"File deleted: {event.src_path}")
            self._emit("world.file_deleted", event.src_path)


class FileMonitor:
    """
    Starts a watchdog Observer in a background thread.
    Publishes world.file_* events through EventBus.
    """

    def __init__(self, watch_path: Path, bus: EventBus) -> None:
        self._watch_path = watch_path
        self._bus        = bus
        self._observer: Observer | None = None
        self._thread:   threading.Thread | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        handler       = _EventHandler(self._bus, loop)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._watch_path), recursive=True)
        self._observer.start()
        log.info(f"FileMonitor started. Watching: {self._watch_path}")

    def stop(self) -> None:
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
            log.info("FileMonitor stopped.")
