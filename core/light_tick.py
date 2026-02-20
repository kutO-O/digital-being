"""
Digital Being — LightTick
Phase 2: Fast heartbeat loop (every light_tick_sec seconds).

Responsibilities per tick:
  1. Read inbox.txt — publish user.message (or user.urgent if !URGENT prefix)
  2. Take a mini-snapshot of state.json → memory/snapshots/
  3. Keep only the last N snapshots (configurable)
  4. Log each tick to logs/actions.log
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path

from core.event_bus import EventBus

log = logging.getLogger("digital_being.light_tick")

# Dedicated action logger (logs/actions.log)
action_log = logging.getLogger("digital_being.actions")


class LightTick:
    """
    Async light-tick engine.
    Call start() to run the loop as an asyncio task.
    """

    URGENT_PREFIX = "!URGENT"
    MAX_SNAPSHOTS = 10

    def __init__(self, cfg: dict, bus: EventBus) -> None:
        self._cfg          = cfg
        self._bus          = bus
        self._interval     = cfg["ticks"]["light_tick_sec"]
        self._inbox_path   = Path(cfg["paths"]["inbox"])
        self._state_path   = Path(cfg["paths"]["state"])
        self._snapshot_dir = Path(cfg["paths"]["snapshots"])
        self._tick_count   = 0
        self._running      = False

    async def start(self) -> None:
        """Run the light tick loop until stop() is called."""
        self._running = True
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"LightTick started. Interval: {self._interval}s")

        while self._running:
            tick_start = time.monotonic()
            self._tick_count += 1

            await self._process_inbox()
            await self._take_snapshot()
            self._log_tick()

            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))

    def stop(self) -> None:
        self._running = False
        log.info("LightTick stopped.")

    # ──────────────────────────────────────────────────────────────
    # Inbox
    # ──────────────────────────────────────────────────────────────
    async def _process_inbox(self) -> None:
        """Read inbox.txt, publish event, then clear the file."""
        if not self._inbox_path.exists():
            # Create empty inbox if missing
            self._inbox_path.touch()
            return

        content = self._inbox_path.read_text(encoding="utf-8").strip()
        if not content:
            return

        # Determine event type
        if content.startswith(self.URGENT_PREFIX):
            text = content[len(self.URGENT_PREFIX):].strip()
            event = "user.urgent"
            log.info(f"[TICK #{self._tick_count}] URGENT message received: {text[:80]}")
        else:
            text  = content
            event = "user.message"
            log.info(f"[TICK #{self._tick_count}] Message received: {text[:80]}")

        # Clear inbox BEFORE publishing (avoid double-read on error)
        self._inbox_path.write_text("", encoding="utf-8")

        await self._bus.publish(event, {"text": text, "tick": self._tick_count})

    # ──────────────────────────────────────────────────────────────
    # Snapshots
    # ──────────────────────────────────────────────────────────────
    async def _take_snapshot(self) -> None:
        """Copy state.json → memory/snapshots/state_<timestamp>.json"""
        if not self._state_path.exists():
            return

        ts       = time.strftime("%Y%m%d_%H%M%S")
        dest     = self._snapshot_dir / f"state_{ts}.json"
        shutil.copy2(self._state_path, dest)

        # Rotate: keep only the last MAX_SNAPSHOTS files
        snapshots = sorted(self._snapshot_dir.glob("state_*.json"))
        if len(snapshots) > self.MAX_SNAPSHOTS:
            for old in snapshots[: len(snapshots) - self.MAX_SNAPSHOTS]:
                old.unlink()
                log.debug(f"Rotated old snapshot: {old.name}")

    # ──────────────────────────────────────────────────────────────
    # Action log
    # ──────────────────────────────────────────────────────────────
    def _log_tick(self) -> None:
        action_log.info(
            f"tick={self._tick_count} "
            f"inbox_checked=true "
            f"snapshot=true"
        )
