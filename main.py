"""
Digital Being — Entry Point
Phase 1: Config loading + system bootstrap
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from pathlib import Path

import yaml


# ────────────────────────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent.resolve()
CONFIG_PATH = ROOT_DIR / "config.yaml"
SEED_PATH   = ROOT_DIR / "seed.yaml"


# ────────────────────────────────────────────────────────────────────
# Config loading
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

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "digital_being.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger("digital_being")


def ensure_directories(cfg: dict) -> None:
    """Create required directories if they don't exist."""
    paths_to_create = [
        Path(cfg["memory"]["episodic_db"]).parent,
        Path(cfg["memory"]["semantic_lance"]).parent,
        Path(cfg["logging"]["dir"]),
        Path(cfg["paths"]["state"]).parent,
    ]
    for p in paths_to_create:
        p.mkdir(parents=True, exist_ok=True)


# ────────────────────────────────────────────────────────────────────
# Graceful shutdown
# ────────────────────────────────────────────────────────────────────
_shutdown_requested = False


def _handle_signal(signum, frame):  # noqa: ANN001
    global _shutdown_requested
    _shutdown_requested = True


# ────────────────────────────────────────────────────────────────────
# Bootstrap check
# ────────────────────────────────────────────────────────────────────
def is_first_run(cfg: dict) -> bool:
    return not Path(cfg["paths"]["state"]).exists()


def bootstrap_from_seed(seed: dict, cfg: dict, logger: logging.Logger) -> None:
    """On first run, write initial state from seed.yaml."""
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

    logger.info(f"First run detected. State bootstrapped from seed.yaml as '{state['name']}'.")
    logger.info(f"Starting scores: {scores}")
    logger.info(f"Pending tasks ({len(tasks)}): {[t['id'] for t in tasks]}")


# ────────────────────────────────────────────────────────────────────
# Tick loop (stub — Phase 2+)
# ────────────────────────────────────────────────────────────────────
def run_loop(cfg: dict, logger: logging.Logger) -> None:
    light_tick = cfg["ticks"]["light_tick_sec"]
    heavy_tick = cfg["ticks"]["heavy_tick_sec"]

    tick_count      = 0
    last_heavy_time = time.monotonic()

    logger.info("Main loop started.")
    logger.info(f"  light_tick={light_tick}s | heavy_tick={heavy_tick}s")
    logger.info(f"  Resource budget: {cfg['resources']['budget']}")

    while not _shutdown_requested:
        tick_start = time.monotonic()
        tick_count += 1

        # ── Light tick ──────────────────────────────────────────────
        logger.debug(f"[TICK #{tick_count}] light tick")
        # TODO Phase 2: score update, boredom decay, lightweight checks

        # ── Heavy tick ──────────────────────────────────────────────
        elapsed = tick_start - last_heavy_time
        if elapsed >= heavy_tick:
            last_heavy_time = tick_start
            logger.info(f"[TICK #{tick_count}] heavy tick — elapsed since last: {elapsed:.1f}s")
            # TODO Phase 2: goal evaluation, LLM strategy call, memory write

        # ── Sleep until next light tick ─────────────────────────────
        elapsed_this_tick = time.monotonic() - tick_start
        time.sleep(max(0.0, light_tick - elapsed_this_tick))

    logger.info("Shutdown signal received. Exiting cleanly.")


# ────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────
def main() -> None:
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

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

    run_loop(cfg, logger)


if __name__ == "__main__":
    main()
