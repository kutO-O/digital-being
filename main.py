"""
Digital Being — Entry Point
Phase 3: EpisodicMemory integrated via EventBus.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import time
from pathlib import Path

import yaml

from core.event_bus import EventBus
from core.file_monitor import FileMonitor
from core.light_tick import LightTick
from core.memory.episodic import EpisodicMemory


# ────────────────────────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent.resolve()
CONFIG_PATH = ROOT_DIR / "config.yaml"
SEED_PATH   = ROOT_DIR / "seed.yaml"


# ────────────────────────────────────────────────────────────────────
# Config / logging
# ────────────────────────────────────────────────────────────────────
def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(cfg: dict) -> logging.Logger:
    log_dir = Path(cfg["logging"]["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, cfg["logging"].get("level", "INFO").upper(), logging.INFO)
    fmt     = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "digital_being.log", encoding="utf-8"),
        ],
    )

    actions_handler = logging.FileHandler(log_dir / "actions.log", encoding="utf-8")
    actions_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logging.getLogger("digital_being.actions").addHandler(actions_handler)

    return logging.getLogger("digital_being")


def ensure_directories(cfg: dict) -> None:
    paths_to_create = [
        Path(cfg["memory"]["episodic_db"]).parent,
        Path(cfg["memory"]["semantic_lance"]).parent,
        Path(cfg["logging"]["dir"]),
        Path(cfg["paths"]["state"]).parent,
        Path(cfg["paths"]["snapshots"]),
    ]
    for p in paths_to_create:
        p.mkdir(parents=True, exist_ok=True)
    for key in ("inbox", "outbox"):
        p = Path(cfg["paths"][key])
        if not p.exists():
            p.touch()


# ────────────────────────────────────────────────────────────────────
# Bootstrap
# ────────────────────────────────────────────────────────────────────
def is_first_run(cfg: dict) -> bool:
    return not Path(cfg["paths"]["state"]).exists()


def bootstrap_from_seed(seed: dict, cfg: dict, logger: logging.Logger) -> None:
    identity = seed.get("identity", {})
    scores   = seed.get("scores", {})
    tasks    = seed.get("first_instructions", [])
    anchors  = seed.get("anchor_values", {})

    state = {
        "name":           identity.get("name", "Digital Being"),
        "purpose":        identity.get("purpose", ""),
        "scores":         scores,
        "pending_tasks":  tasks,
        "anchor_values":  anchors,
        "tick_count":     0,
        "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    state_path = Path(cfg["paths"]["state"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    logger.info(f"First run: state bootstrapped as '{state['name']}'.")
    logger.info(f"Starting scores: {scores}")
    logger.info(f"Pending tasks ({len(tasks)}): {[t['id'] for t in tasks]}")


# ────────────────────────────────────────────────────────────────────
# EventBus handlers — write to EpisodicMemory
# ────────────────────────────────────────────────────────────────────
def make_memory_handlers(mem: EpisodicMemory, logger: logging.Logger):
    """
    Returns a dict of {event_name: async_handler} that write to episodic memory.
    Defined as a factory so mem is captured in closure — no globals.
    """

    async def on_user_message(data: dict) -> None:
        text = data.get("text", "")
        logger.info(f"[EVENT] user.message → '{text[:120]}'")
        mem.add_episode(
            event_type="user.message",
            description=text[:_MAX_DESC_LEN] if text else "(empty)",
            outcome="unknown",
            data={"tick": data.get("tick")},
        )

    async def on_user_urgent(data: dict) -> None:
        text = data.get("text", "")
        logger.warning(f"[EVENT] user.urgent ⚡ → '{text[:120]}'")
        # NOTE: Phase 4+ TODO — !URGENT should interrupt the current tick immediately
        mem.add_episode(
            event_type="urgent",
            description=text[:_MAX_DESC_LEN] if text else "(empty)",
            outcome="unknown",
            data={"tick": data.get("tick")},
        )

    async def on_file_changed(data: dict) -> None:
        path = data.get("path", "?")
        logger.debug(f"[EVENT] world.file_changed → {path}")
        mem.add_episode(
            event_type="world.file_changed",
            description=f"File modified: {path}",
            outcome="unknown",
        )

    async def on_file_created(data: dict) -> None:
        path = data.get("path", "?")
        logger.debug(f"[EVENT] world.file_created → {path}")
        mem.add_episode(
            event_type="world.file_created",
            description=f"File created: {path}",
            outcome="unknown",
        )

    async def on_file_deleted(data: dict) -> None:
        path = data.get("path", "?")
        logger.debug(f"[EVENT] world.file_deleted → {path}")
        mem.add_episode(
            event_type="world.file_deleted",
            description=f"File deleted: {path}",
            outcome="unknown",
        )

    return {
        "user.message":       on_user_message,
        "user.urgent":        on_user_urgent,
        "world.file_changed": on_file_changed,
        "world.file_created": on_file_created,
        "world.file_deleted": on_file_deleted,
    }


# Import constant from episodic for description truncation
_MAX_DESC_LEN = 1000


# ────────────────────────────────────────────────────────────────────
# Async main
# ────────────────────────────────────────────────────────────────────
async def async_main(cfg: dict, logger: logging.Logger) -> None:
    loop = asyncio.get_running_loop()

    # 1. EpisodicMemory
    mem = EpisodicMemory(Path(cfg["memory"]["episodic_db"]))
    mem.init()

    if not mem.health_check():
        logger.error("EpisodicMemory health check FAILED. Aborting.")
        return

    # First episode: system start
    mem.add_episode(
        event_type="system.start",
        description="Digital Being started",
        outcome="success",
    )

    # Log active principles if any
    principles = mem.get_active_principles()
    if principles:
        logger.info(f"Active principles loaded: {len(principles)}")
        for p in principles:
            logger.info(f"  • [{p['id']}] {p['text']}")

    # 2. EventBus
    bus = EventBus()

    # 3. Wire memory handlers to EventBus
    handlers = make_memory_handlers(mem, logger)
    for event_name, handler in handlers.items():
        bus.subscribe(event_name, handler)

    # 4. FileMonitor
    monitor = FileMonitor(watch_path=ROOT_DIR, bus=bus)
    monitor.start(loop)

    # 5. LightTick
    ticker    = LightTick(cfg=cfg, bus=bus)
    tick_task = asyncio.create_task(ticker.start(), name="light_tick")

    logger.info("All subsystems started. Running... (Ctrl+C to stop)")

    # 6. Wait for shutdown signal
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: stop_event.set())

    await stop_event.wait()

    # 7. Graceful shutdown
    ticker.stop()
    monitor.stop()
    tick_task.cancel()
    try:
        await tick_task
    except asyncio.CancelledError:
        pass

    mem.add_episode(
        event_type="system.stop",
        description="Digital Being stopped cleanly",
        outcome="success",
    )
    mem.close()
    logger.info("Digital Being shut down cleanly.")


def main() -> None:
    cfg  = load_yaml(CONFIG_PATH)
    seed = load_yaml(SEED_PATH)

    logger = setup_logging(cfg)
    logger.info("=" * 60)
    logger.info("  Digital Being — starting up")
    logger.info(f"  Version        : {cfg['system']['version']}")
    logger.info(f"  Strategy model : {cfg['ollama']['strategy_model']}")
    logger.info(f"  Embed model    : {cfg['ollama']['embed_model']}")
    logger.info("=" * 60)

    ensure_directories(cfg)

    if is_first_run(cfg):
        bootstrap_from_seed(seed, cfg, logger)
    else:
        logger.info("Existing state found. Resuming from memory/state.json.")

    anchors = seed.get("anchor_values", {})
    if anchors.get("locked"):
        logger.info(f"Anchor values LOCKED ({len(anchors.get('values', []))} rules).")

    asyncio.run(async_main(cfg, logger))


if __name__ == "__main__":
    main()
