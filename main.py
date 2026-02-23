"""
Digital Being — Entry Point
Stage 28-30: FINAL INTEGRATION - Advanced Multi-Agent + Memory + Self-Evolution (COMPLETE)
+ HOT RELOADER: Live Python code reloading without restart! 🔥
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

from core.attention_system import AttentionSystem
from core.belief_system import BeliefSystem
from core.contradiction_resolver import ContradictionResolver
from core.curiosity_engine import CuriosityEngine
from core.dream_mode import DreamMode
from core.emotion_engine import EmotionEngine
from core.event_bus import EventBus
from core.file_monitor import FileMonitor
from core.goal_persistence import GoalPersistence

# Fault-Tolerant Architecture
from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick

# Goal Hierarchy & Tools & Learning
from core.goal_integration import GoalOrientedBehavior
from core.tools import ToolRegistry, initialize_default_tools
from core.learning import LearningEngine, PatternGuidedPlanner

# Advanced Cognitive Features
from core.memory_consolidation import MemoryConsolidation
from core.theory_of_mind import UserModel
from core.proactive_behavior import ProactiveBehaviorEngine
from core.meta_learning import MetaOptimizer

# Stage 26 - Skill Library
from core.skill_library import SkillLibrary

# Stage 27-28 - Multi-Agent System (Phase 3)
from core.multi_agent_integration import MultiAgentSystem, create_multi_agent_system
from core.multi_agent import AgentRole

# Stage 29 - Long-term Memory
from core.memory.memory_consolidation import MemoryConsolidation as LongTermMemoryConsolidation
from core.memory.semantic_memory import SemanticMemory
from core.memory.memory_retrieval import MemoryRetrieval

# Stage 30 - Self-Evolution (COMPLETE)
from core.self_evolution import (
    SelfEvolutionManager,
    EvolutionMode,
    ChangeType,
    # Priority 1: Critical
    LLMCodeAssistant,
    SafetyValidator,
    PerformanceMonitor,
    AutoRollbackHandler,
    # Priority 2: Advanced
    DependencyAnalyzer,
    PriorityQueue,
    EvolutionRateLimiter,
    CanaryDeployment,
)

# 🔥 HOT RELOADER - Live code changes!
from core.hot_reloader import HotReloader

from core.introspection_api import IntrospectionAPI
from core.light_tick import LightTick
from core.memory.episodic import EpisodicMemory
from core.memory.vector_memory import VectorMemory
from core.meta_cognition import MetaCognition
from core.milestones import Milestones
from core.narrative_engine import NarrativeEngine
from core.ollama_client import OllamaClient
from core.reflection_engine import ReflectionEngine
from core.self_model import SelfModel
from core.self_modification import SelfModificationEngine
from core.shell_executor import ShellExecutor
from core.social_layer import SocialLayer
from core.strategy_engine import StrategyEngine
from core.time_perception import TimePerception
from core.value_engine import ValueEngine
from core.world_model import WorldModel

ROOT_DIR      = Path(__file__).parent.resolve()
CONFIG_PATH   = ROOT_DIR / "config.yaml"
SEED_PATH     = ROOT_DIR / "seed.yaml"
_MAX_DESC_LEN = 1000

def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def setup_logging(cfg: dict) -> logging.Logger:
    log_dir   = Path(cfg["logging"]["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, cfg["logging"].get("level", "INFO").upper(), logging.INFO)
    fmt       = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    datefmt   = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=log_level, format=fmt, datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "digital_being.log", encoding="utf-8"),
        ],
    )
    a_handler = logging.FileHandler(log_dir / "actions.log", encoding="utf-8")
    a_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logging.getLogger("digital_being.actions").addHandler(a_handler)
    return logging.getLogger("digital_being")

def ensure_directories(cfg: dict) -> None:
    dirs = [
        Path(cfg["memory"]["episodic_db"]).parent,
        Path(cfg["memory"]["semantic_lance"]).parent,
        Path(cfg["logging"]["dir"]),
        Path(cfg["paths"]["state"]).parent,
        Path(cfg["paths"]["snapshots"]),
        Path(cfg["scores"]["drift"]["snapshot_dir"]),
        ROOT_DIR / "memory" / "self_snapshots",
        ROOT_DIR / "milestones",
        ROOT_DIR / "sandbox",
        ROOT_DIR / "data",
        ROOT_DIR / "memory" / "multi_agent",
        ROOT_DIR / "memory" / "semantic",
        ROOT_DIR / "memory" / "self_evolution",
    ]
    for p in dirs:
        p.mkdir(parents=True, exist_ok=True)
    for key in ("inbox", "outbox"):
        p = Path(cfg["paths"][key])
        if not p.exists():
            p.touch()

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

def make_memory_handlers(mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_user_message(data: dict) -> None:
        text = data.get("text", "")
        logger.info(f"[EVENT] user.message → '{text[:120]}'")
        mem.add_episode("user.message", text[:_MAX_DESC_LEN] or "(empty)", data={"tick": data.get("tick")})
    async def on_user_urgent(data: dict) -> None:
        text = data.get("text", "")
        logger.warning(f"[EVENT] user.urgent ⚡ → '{text[:120]}'")
        mem.add_episode("urgent", text[:_MAX_DESC_LEN] or "(empty)", data={"tick": data.get("tick")})
    async def on_file_changed(data: dict) -> None:
        mem.add_episode("world.file_changed", f"File modified: {data.get('path','?')}")
    async def on_file_created(data: dict) -> None:
        mem.add_episode("world.file_created", f"File created: {data.get('path','?')}")
    async def on_file_deleted(data: dict) -> None:
        mem.add_episode("world.file_deleted", f"File deleted: {data.get('path','?')}")
    return {
        "user.message": on_user_message, "user.urgent": on_user_urgent,
        "world.file_changed": on_file_changed, "world.file_created": on_file_created,
        "world.file_deleted": on_file_deleted,
    }

def make_world_handlers(logger: logging.Logger) -> dict:
    async def on_world_ready(data: dict) -> None:
        logger.info(f"[WorldModel] Ready. Indexed {data.get('file_count', '?')} files.")
    async def on_world_updated(data: dict) -> None:
        logger.debug(f"[WorldModel] Updated: {data.get('summary', '')}")
    return {"world.ready": on_world_ready, "world.updated": on_world_updated}

def make_value_handlers(values: ValueEngine, mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_value_changed(data: dict) -> None:
        logger.info(f"[ValueEngine] {data.get('context', '')}")
        for w in values.check_drift():
            mem.add_episode("value.drift_warning", w[:_MAX_DESC_LEN])
    return {"value.changed": on_value_changed}

def make_self_handlers(self_model: SelfModel, mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_self_drift_detected(data: dict) -> None:
        msg = f"Self drift: v{data.get('past_version')} → v{data.get('current_version')} (Δ{data.get('delta')})"
        logger.warning(f"[SelfModel] {msg}")
        mem.add_episode("self.drift_detected", msg[:_MAX_DESC_LEN])
    return {"self.drift_detected": on_self_drift_detected}

def make_strategy_handlers(milestones: Milestones, mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_vector_changed(data: dict) -> None:
        vector = data.get("vector", "")
        logger.info(f"[StrategyEngine] Long-term vector changed: '{vector[:120]}'")
        milestones.achieve("first_vector_change", f"Долгосрочный вектор изменён: '{vector[:80]}'")
        mem.add_episode("strategy.vector_changed", f"Новый долгосрочный вектор: '{vector[:200]}'", outcome="success")
    return {"strategy.vector_changed": on_vector_changed}

def make_dream_handlers(mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_dream_completed(data: dict) -> None:
        logger.info(f"[DreamMode] Completed. insights={data.get('insights_count', 0)} vector_updated={data.get('vector_updated', False)} principle_added={data.get('principle_added', False)} run_count={data.get('run_count', '?')}")
        mem.add_episode("dream.completed", f"Цикл мечтаний завершён. Инсайтов: {data.get('insights_count', 0)}, вектор обновлён: {data.get('vector_updated', False)}", outcome="success")
    return {"dream.completed": on_dream_completed}

def make_reflection_handlers(mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_reflection_completed(data: dict) -> None:
        tick = data.get("tick", "?")
        contradictions = data.get("contradictions", 0)
        logger.info(f"[ReflectionEngine] Reflection completed at tick #{tick}. contradictions={contradictions}")
    return {"reflection.completed": on_reflection_completed}

def make_narrative_handlers(mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_narrative_entry_written(data: dict) -> None:
        tick = data.get("tick", "?")
        logger.info(f"[NarrativeEngine] Diary entry written at tick #{tick}.")
    return {"narrative.entry_written": on_narrative_entry_written}

def make_self_modification_handlers(mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_config_modified(data: dict) -> None:
        key = data.get("key", "?")
        new_value = data.get("new_value", "?")
        old_value = data.get("old_value", "?")
        logger.info(f"[SelfModification] Config changed: {key} = {new_value} (was {old_value})")
    return {"config.modified": on_config_modified}

async def _dream_loop(dream: DreamMode, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("DreamMode loop started.")
    while not stop_event.is_set():
        await asyncio.sleep(300)
        if stop_event.is_set():
            break
        if dream.should_run():
            logger.info("DreamMode: interval elapsed — starting dream cycle.")
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, dream.run)
                if result.get("skipped"):
                    logger.info(f"DreamMode: skipped ({result.get('reason', '?')}).")
            except Exception as e:
                logger.error(f"DreamMode loop error: {e}")
    logger.info("DreamMode loop stopped.")

async def _consolidation_loop(consolidator: MemoryConsolidation, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("MemoryConsolidation loop started.")
    while not stop_event.is_set():
        await asyncio.sleep(3600)
        if stop_event.is_set():
            break
        if consolidator.should_consolidate():
            logger.info("MemoryConsolidation: starting sleep cycle...")
            try:
                result = await consolidator.consolidate()
                logger.info(f"MemoryConsolidation: {result}")
            except Exception as e:
                logger.error(f"MemoryConsolidation error: {e}")
    logger.info("MemoryConsolidation loop stopped.")

async def _multi_agent_loop(system: MultiAgentSystem, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("🤝 Multi-Agent system polling started.")
    poll_interval = 2.0
    while not stop_event.is_set():
        try:
            await system.tick()
            await asyncio.sleep(poll_interval)
        except Exception as e:
            logger.error(f"Multi-agent polling error: {e}")
            await asyncio.sleep(poll_interval)
    logger.info("🤝 Multi-Agent loop stopped.")

async def _longterm_memory_loop(
    mem_consolidation: LongTermMemoryConsolidation,
    semantic_mem: SemanticMemory,
    episodic_mem: EpisodicMemory,
    stop_event: asyncio.Event,
    logger: logging.Logger
) -> None:
    logger.info("🧠 Long-term Memory consolidation loop started.")
    while not stop_event.is_set():
        await asyncio.sleep(7200)
        if stop_event.is_set():
            break
        
        try:
            recent = episodic_mem.get_recent_episodes(100)
            result = mem_consolidation.run_consolidation_cycle(recent)
            logger.info(
                f"🧠 Memory consolidation: consolidated={result['consolidated']}, "
                f"forgotten={result['forgotten']}, total={result['total_memories']}"
            )
            for episode in recent:
                semantic_mem.extract_knowledge_from_episode(episode)
            logger.debug("🧠 Semantic knowledge extraction complete")
        except Exception as e:
            logger.error(f"🧠 Long-term memory error: {e}")
    
    logger.info("🧠 Long-term Memory loop stopped.")