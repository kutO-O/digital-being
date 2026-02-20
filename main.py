"""
Digital Being — Entry Point
Phase 6: SelfModel + Milestones integrated.
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
from core.milestones import Milestones
from core.self_model import SelfModel
from core.value_engine import ValueEngine
from core.world_model import WorldModel


# ────────────────────────────────────────────────────────────────────
ROOT_DIR      = Path(__file__).parent.resolve()
CONFIG_PATH   = ROOT_DIR / "config.yaml"
SEED_PATH     = ROOT_DIR / "seed.yaml"
_MAX_DESC_LEN = 1000


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
        level=log_level, format=fmt, datefmt=datefmt,
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
    for p in [
        Path(cfg["memory"]["episodic_db"]).parent,
        Path(cfg["memory"]["semantic_lance"]).parent,
        Path(cfg["logging"]["dir"]),
        Path(cfg["paths"]["state"]).parent,
        Path(cfg["paths"]["snapshots"]),
        Path(cfg["scores"]["drift"]["snapshot_dir"]),
        ROOT_DIR / "memory" / "self_snapshots",
        ROOT_DIR / "milestones",
    ]:
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
    state = {
        "name":           identity.get("name", "Digital Being"),
        "purpose":        identity.get("purpose", ""),
        "scores":         seed.get("scores", {}),
        "pending_tasks":  seed.get("first_instructions", []),
        "anchor_values":  seed.get("anchor_values", {}),
        "tick_count":     0,
        "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    state_path = Path(cfg["paths"]["state"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    logger.info(f"First run: state bootstrapped as '{state['name']}'.")
    logger.info(f"Starting scores: {state['scores']}")
    logger.info(f"Pending tasks ({len(state['pending_tasks'])}): "
                f"{[t['id'] for t in state['pending_tasks']]}")


# ────────────────────────────────────────────────────────────────────
# EventBus handler factories
# ────────────────────────────────────────────────────────────────────
def make_memory_handlers(mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_user_message(data: dict) -> None:
        text = data.get("text", "")
        logger.info(f"[EVENT] user.message → '{text[:120]}'")
        mem.add_episode("user.message", text[:_MAX_DESC_LEN] or "(empty)",
                        data={"tick": data.get("tick")})

    async def on_user_urgent(data: dict) -> None:
        text = data.get("text", "")
        logger.warning(f"[EVENT] user.urgent ⚡ → '{text[:120]}'")
        # TODO Phase 7: interrupt heavy tick immediately on !URGENT
        mem.add_episode("urgent", text[:_MAX_DESC_LEN] or "(empty)",
                        data={"tick": data.get("tick")})

    async def on_file_changed(data: dict) -> None:
        path = data.get("path", "?")
        logger.debug(f"[EVENT] world.file_changed → {path}")
        mem.add_episode("world.file_changed", f"File modified: {path}")

    async def on_file_created(data: dict) -> None:
        path = data.get("path", "?")
        logger.debug(f"[EVENT] world.file_created → {path}")
        mem.add_episode("world.file_created", f"File created: {path}")

    async def on_file_deleted(data: dict) -> None:
        path = data.get("path", "?")
        logger.debug(f"[EVENT] world.file_deleted → {path}")
        mem.add_episode("world.file_deleted", f"File deleted: {path}")

    return {
        "user.message":       on_user_message,
        "user.urgent":        on_user_urgent,
        "world.file_changed": on_file_changed,
        "world.file_created": on_file_created,
        "world.file_deleted": on_file_deleted,
    }


def make_world_handlers(logger: logging.Logger) -> dict:
    async def on_world_ready(data: dict) -> None:
        logger.info(f"[WorldModel] Ready. Indexed {data.get('file_count', '?')} files.")

    async def on_world_updated(data: dict) -> None:
        logger.debug(f"[WorldModel] Updated: {data.get('summary', '')}")

    return {"world.ready": on_world_ready, "world.updated": on_world_updated}


def make_value_handlers(values: ValueEngine, mem: EpisodicMemory,
                        logger: logging.Logger) -> dict:
    async def on_value_changed(data: dict) -> None:
        ctx = data.get("context", "")
        logger.info(f"[ValueEngine] {ctx}")
        warnings = values.check_drift()
        for w in warnings:
            mem.add_episode("value.drift_warning", w[:_MAX_DESC_LEN])

    return {"value.changed": on_value_changed}


def make_self_handlers(self_model: SelfModel, mem: EpisodicMemory,
                       logger: logging.Logger) -> dict:
    async def on_self_drift_detected(data: dict) -> None:
        msg = (
            f"Self drift detected: version {data.get('past_version')} → "
            f"{data.get('current_version')} (Δ{data.get('delta')})"
        )
        logger.warning(f"[SelfModel] {msg}")
        mem.add_episode("self.drift_detected", msg[:_MAX_DESC_LEN])

    return {"self.drift_detected": on_self_drift_detected}


# ────────────────────────────────────────────────────────────────────
# Async main
# ────────────────────────────────────────────────────────────────────
async def async_main(cfg: dict, logger: logging.Logger) -> None:
    loop       = asyncio.get_running_loop()
    state_path = Path(cfg["paths"]["state"])

    # 1. EpisodicMemory
    mem = EpisodicMemory(Path(cfg["memory"]["episodic_db"]))
    mem.init()
    if not mem.health_check():
        logger.error("EpisodicMemory health check FAILED. Aborting.")
        return
    mem.add_episode("system.start", "Digital Being started", outcome="success")

    principles = mem.get_active_principles()
    if principles:
        logger.info(f"Active principles: {len(principles)}")
        for p in principles:
            logger.info(f"  • [{p['id']}] {p['text']}")

    # 2. EventBus
    bus = EventBus()

    # 3. ValueEngine
    values = ValueEngine(cfg=cfg, bus=bus)
    values.load(state_path=state_path, seed_path=SEED_PATH)
    values.subscribe()
    values.save_weekly_snapshot()

    # 4. SelfModel
    self_model = SelfModel(bus=bus)
    self_model.load(
        self_model_path=ROOT_DIR / "self_model.json",
        seed_path=SEED_PATH,
        snapshots_dir=ROOT_DIR / "memory" / "self_snapshots",
    )
    self_model.subscribe()
    self_model.save_weekly_snapshot()

    # 5. Milestones
    milestones = Milestones(bus=bus)
    milestones.load(ROOT_DIR / "milestones" / "milestones.json")
    milestones.subscribe()

    # 6. Wire all EventBus handlers
    for event_name, handler in make_memory_handlers(mem, logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_world_handlers(logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_value_handlers(values, mem, logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_self_handlers(self_model, mem, logger).items():
        bus.subscribe(event_name, handler)

    # 7. WorldModel
    world = WorldModel(bus=bus, mem=mem)
    world.subscribe()

    # 8. FileMonitor
    monitor = FileMonitor(watch_path=ROOT_DIR, bus=bus)
    monitor.start(loop)

    # 9. LightTick
    ticker    = LightTick(cfg=cfg, bus=bus)
    tick_task = asyncio.create_task(ticker.start(), name="light_tick")

    # 10. Initial world scan
    file_count = await world.scan(ROOT_DIR)
    mem.add_episode(
        "world.scan",
        f"Initial file scan complete: {file_count} files indexed",
        outcome="success",
        data={"file_count": file_count},
    )

    # 11. Startup banner
    logger.info("=" * 50)
    logger.info(f"  World      : {world.summary()}")
    logger.info(f"  Values     : {values.to_prompt_context()}")
    logger.info(f"  Self v{self_model.get_version():<3}  : {self_model.get_identity()['name']}")
    logger.info(f"  Principles : {len(self_model.get_principles())}")
    logger.info(f"  {milestones.summary()}")
    logger.info("=" * 50)
    logger.info("Running... (Ctrl+C to stop)")

    # 12. Shutdown signal
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

    # 13. Graceful shutdown
    ticker.stop()
    monitor.stop()
    tick_task.cancel()
    try:
        await tick_task
    except asyncio.CancelledError:
        pass

    # Final snapshots + drift checks
    values.save_weekly_snapshot()
    self_model.save_weekly_snapshot()
    await self_model.check_drift(values)

    mem.add_episode("system.stop", "Digital Being stopped cleanly", outcome="success")
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
