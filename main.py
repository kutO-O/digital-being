"""
Digital Being — Entry Point
Stage 27.5: Multi-Agent Integration
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

# NEW: Fault-Tolerant Architecture
from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick

# NEW: Goal Hierarchy & Tools & Learning
from core.goal_integration import GoalOrientedBehavior
from core.tools import ToolRegistry, initialize_default_tools
from core.learning import LearningEngine, PatternGuidedPlanner

# NEW: Advanced Cognitive Features
from core.memory_consolidation import MemoryConsolidation
from core.theory_of_mind import UserModel
from core.proactive_behavior import ProactiveBehaviorEngine
from core.meta_learning import MetaOptimizer

# NEW: Stage 26 - Skill Library
from core.skill_library import SkillLibrary

# NEW: Stage 27 - Multi-Agent Communication
from core.multi_agent_coordinator import MultiAgentCoordinator

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
        ROOT_DIR / "data",  # NEW: for cognitive features
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

# NEW: Memory consolidation loop
async def _consolidation_loop(consolidator: MemoryConsolidation, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("MemoryConsolidation loop started.")
    while not stop_event.is_set():
        await asyncio.sleep(3600)  # Check every hour
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

# NEW: Multi-agent message polling loop
async def _multi_agent_loop(coordinator: MultiAgentCoordinator, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("🤝 Multi-Agent message polling started.")
    poll_interval = coordinator._config.get("message_processing", {}).get("poll_interval_sec", 2)
    while not stop_event.is_set():
        try:
            processed = await coordinator.process_messages()
            if processed > 0:
                logger.debug(f"🤝 Processed {processed} messages from network")
        except Exception as e:
            logger.error(f"Multi-agent polling error: {e}")
        await asyncio.sleep(poll_interval)
    logger.info("🤝 Multi-Agent loop stopped.")

async def async_main(cfg: dict, logger: logging.Logger) -> None:
    loop = asyncio.get_running_loop()
    state_path = Path(cfg["paths"]["state"])
    log_dir = Path(cfg["logging"]["dir"])
    start_time = time.time()

    mem = EpisodicMemory(Path(cfg["memory"]["episodic_db"]))
    mem.init()
    if not mem.health_check():
        logger.error("EpisodicMemory health check FAILED. Aborting.")
        return
    mem.add_episode("system.start", "Digital Being started with Multi-Agent support", outcome="success")

    principles_stored = mem.get_active_principles()
    if principles_stored:
        for p in principles_stored:
            logger.info(f"  • [{p['id']}] {p['text']}")

    vector_mem = VectorMemory(ROOT_DIR / "memory" / "vector_memory.db")
    vector_mem.init()
    logger.info(f"VectorMemory ready. Stored vectors: {vector_mem.count()}")

    bus = EventBus()
    values = ValueEngine(cfg=cfg, bus=bus)
    values.load(state_path=state_path, seed_path=SEED_PATH)
    values.subscribe()
    values.save_weekly_snapshot()

    self_model = SelfModel(bus=bus)
    self_model.load(self_model_path=ROOT_DIR / "self_model.json", seed_path=SEED_PATH, snapshots_dir=ROOT_DIR / "memory" / "self_snapshots")
    self_model.subscribe()
    self_model.save_weekly_snapshot()

    milestones = Milestones(bus=bus)
    milestones.load(ROOT_DIR / "milestones" / "milestones.json")
    milestones.subscribe()

    ollama = OllamaClient(cfg)
    ollama_ok = ollama.is_available()
    if ollama_ok:
        logger.info("Ollama: ✅ available")
    else:
        logger.warning("Ollama: ❌ unavailable. HeavyTick will skip ticks until Ollama comes up.")

    for event_name, handler in make_memory_handlers(mem, logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_world_handlers(logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_value_handlers(values, mem, logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_self_handlers(self_model, mem, logger).items():
        bus.subscribe(event_name, handler)
    for event_name, handler in make_dream_handlers(mem, logger).items():
        bus.subscribe(event_name, handler)

    world = WorldModel(bus=bus, mem=mem)
    world.subscribe()

    monitor = FileMonitor(watch_path=ROOT_DIR, bus=bus)
    monitor.start(loop)

    strategy = StrategyEngine(memory_dir=ROOT_DIR / "memory", event_bus=bus)
    strategy.load()
    for event_name, handler in make_strategy_handlers(milestones, mem, logger).items():
        bus.subscribe(event_name, handler)

    dream_cfg = cfg.get("dream", {})
    dream_enabled = dream_cfg.get("enabled", True)
    dream_interval = float(dream_cfg.get("interval_hours", 6))
    dream = DreamMode(episodic=mem, vector_memory=vector_mem, strategy=strategy, values=values, self_model=self_model,
                      ollama=ollama, event_bus=bus, memory_dir=ROOT_DIR / "memory", interval_hours=dream_interval)

    emotion_engine = EmotionEngine(memory_dir=ROOT_DIR / "memory")
    emotion_engine.load()
    dominant_name, dominant_val = emotion_engine.get_dominant()
    logger.info(f"EmotionEngine ready. Dominant: {dominant_name}({dominant_val:.2f}) | Tone: {emotion_engine.get_tone_modifier()}")

    reflection_cfg = cfg.get("reflection", {})
    reflection_every = int(reflection_cfg.get("every_n_ticks", 10))
    reflection_engine = ReflectionEngine(episodic=mem, value_engine=values, self_model=self_model, emotion_engine=emotion_engine,
                                         strategy_engine=strategy, ollama=ollama, event_bus=bus, memory_dir=ROOT_DIR / "memory",
                                         every_n_ticks=reflection_every)
    for event_name, handler in make_reflection_handlers(mem, logger).items():
        bus.subscribe(event_name, handler)
    logger.info(f"ReflectionEngine ready. Runs every {reflection_every} ticks.")

    narrative_cfg = cfg.get("narrative", {})
    narrative_every = int(narrative_cfg.get("every_n_ticks", 15))
    narrative_engine = NarrativeEngine(episodic=mem, emotion_engine=emotion_engine, strategy_engine=strategy, self_model=self_model,
                                       ollama=ollama, memory_dir=ROOT_DIR / "memory", every_n_ticks=narrative_every, event_bus=bus)
    for event_name, handler in make_narrative_handlers(mem, logger).items():
        bus.subscribe(event_name, handler)
    logger.info(f"NarrativeEngine ready. Writes diary every {narrative_every} ticks.")

    goal_persistence = GoalPersistence(memory_dir=ROOT_DIR / "memory")
    goal_persistence.load()
    if goal_persistence.was_interrupted():
        ag = goal_persistence.get_active()
        last_goal = ag.get("goal", "?") if ag else "?"
        logger.warning(f"[GoalPersistence] System recovering from interruption. Last goal: '{last_goal[:120]}'")
    else:
        logger.info("[GoalPersistence] Clean start — no interrupted goal.")

    attention_system = AttentionSystem(memory_dir=ROOT_DIR / "memory", emotion_engine=emotion_engine, value_engine=values)
    logger.info(f"AttentionSystem ready. Focus: {attention_system.get_focus_summary()}")

    curiosity_cfg = cfg.get("curiosity", {})
    curiosity_enabled = bool(curiosity_cfg.get("enabled", True))
    curiosity_engine = CuriosityEngine(memory_dir=ROOT_DIR / "memory")
    curiosity_engine.load()
    cur_stats = curiosity_engine.get_stats()
    logger.info(f"CuriosityEngine ready. open={cur_stats['open']} answered={cur_stats['answered']} total_asked={cur_stats['total_asked']}")

    self_modification = SelfModificationEngine(config_path=CONFIG_PATH, memory_dir=ROOT_DIR / "memory", ollama=ollama, event_bus=bus)
    for event_name, handler in make_self_modification_handlers(mem, logger).items():
        bus.subscribe(event_name, handler)
    mod_stats = self_modification.get_stats()
    logger.info(f"SelfModificationEngine ready. applied={mod_stats['total_applied']} approved={mod_stats['approved']} rejected={mod_stats['rejected']}")

    belief_system = BeliefSystem(state_path=ROOT_DIR / "memory" / "beliefs.json")
    belief_stats = belief_system.get_stats()
    logger.info(f"BeliefSystem ready. active={belief_stats['active']} strong={belief_stats['strong']} rejected={belief_stats['rejected']} total_formed={belief_stats['total_beliefs_formed']}")

    contradiction_resolver = ContradictionResolver(state_path=ROOT_DIR / "memory" / "contradictions.json")
    contr_stats = contradiction_resolver.get_stats()
    logger.info(f"ContradictionResolver ready. pending={contr_stats['pending']} resolved={contr_stats['resolved']} total_detected={contr_stats['total_detected']}")

    shell_cfg = cfg.get("shell", {})
    shell_enabled = bool(shell_cfg.get("enabled", True))
    shell_executor = None
    if shell_enabled:
        allowed_dir = Path(shell_cfg.get("allowed_dir", "."))
        if not allowed_dir.is_absolute():
            allowed_dir = ROOT_DIR / allowed_dir
        max_output_chars = int(shell_cfg.get("max_output_chars", 2000))
        shell_executor = ShellExecutor(allowed_dir=allowed_dir, memory_dir=ROOT_DIR / "memory", max_output_chars=max_output_chars)
        shell_stats = shell_executor.get_stats()
        logger.info(f"ShellExecutor ready. executed={shell_stats['total_executed']} rejected={shell_stats['total_rejected']} errors={shell_stats['total_errors']}")
    else:
        logger.info("ShellExecutor disabled.")

    time_perc_cfg = cfg.get("time_perception", {})
    time_perc_enabled = bool(time_perc_cfg.get("enabled", True))
    time_perc = None
    if time_perc_enabled:
        time_perc = TimePerception(memory_dir=ROOT_DIR / "memory")
        time_perc.load()
        time_stats = time_perc.get_stats()
        logger.info(f"TimePerception ready. patterns={time_stats['total_patterns']} time_of_day={time_stats['current_time_of_day']}")
    else:
        logger.info("TimePerception disabled.")

    social_cfg = cfg.get("social", {})
    social_enabled = bool(social_cfg.get("enabled", True))
    social_layer = None
    if social_enabled:
        inbox_path = ROOT_DIR / cfg["paths"]["inbox"]
        outbox_path = ROOT_DIR / cfg["paths"]["outbox"]
        social_layer = SocialLayer(inbox_path=inbox_path, outbox_path=outbox_path, memory_dir=ROOT_DIR / "memory")
        social_layer.load()
        social_stats = social_layer.get_stats()
        logger.info(f"SocialLayer ready. incoming={social_stats['total_incoming']} outgoing={social_stats['total_outgoing']} pending={social_stats['pending_response']}")
    else:
        logger.info("SocialLayer disabled.")

    meta_cog_cfg = cfg.get("meta_cognition", {})
    meta_cog_enabled = bool(meta_cog_cfg.get("enabled", True))
    meta_cog = None
    if meta_cog_enabled:
        meta_cog = MetaCognition(memory_dir=ROOT_DIR / "memory", config=meta_cog_cfg)
        meta_cog.load()
        meta_stats = meta_cog.get_stats()
        logger.info(f"MetaCognition ready. insights={meta_stats['total_insights']} decisions_logged={meta_stats['total_decisions_logged']} calibration={meta_stats['calibration_score']:.2f}")
    else:
        logger.info("MetaCognition disabled.")

    # ============================================================
    # NEW: 8-Layer Cognitive Architecture + Stage 26 & 27
    # ============================================================
    
    # Layer 2: Tool Registry
    tool_registry = ToolRegistry()
    initialize_default_tools(tool_registry, allowed_dirs=[ROOT_DIR / "sandbox", ROOT_DIR / "data"])
    tool_stats = tool_registry.get_statistics()
    logger.info(f"🛠️  ToolRegistry ready. tools={tool_stats['total_tools']} executions={tool_stats.get('total_executions', 0)}")
    
    # Layer 3: Continuous Learning
    learning_engine = LearningEngine(
        memory=mem,
        storage_path=ROOT_DIR / "data" / "learning_patterns.json"
    )
    learning_stats = learning_engine.get_statistics()
    logger.info(f"🧠 LearningEngine ready. patterns={learning_stats.get('total_patterns', 0)}")
    
    # NEW: Stage 26 - Skill Library
    skill_cfg = cfg.get("skills", {})
    skill_enabled = bool(skill_cfg.get("enabled", True))
    skill_library = None
    if skill_enabled:
        skill_library = SkillLibrary(memory_dir=ROOT_DIR / "memory", ollama=ollama)
        skill_library.load()
        skill_stats = skill_library.get_stats()
        logger.info(f"📚 SkillLibrary ready. skills={skill_stats['total_skills']} extractions={skill_stats['total_extractions']} uses={skill_stats['total_skill_uses']}")
    else:
        logger.info("📚 SkillLibrary disabled.")
    
    # NEW: Stage 27 - Multi-Agent Communication
    multi_agent_cfg = cfg.get("multi_agent", {})
    multi_agent_enabled = bool(multi_agent_cfg.get("enabled", False))
    multi_agent_coordinator = None
    if multi_agent_enabled and skill_library:
        agent_id = f"{multi_agent_cfg.get('agent_name', 'primary')}_{int(time.time())}"
        storage_dir = ROOT_DIR / "memory"
        shared_registry = Path(multi_agent_cfg.get("shared_storage", {}).get("registry_path", "memory/multi_agent/shared_registry.json"))
        shared_messages = Path(multi_agent_cfg.get("shared_storage", {}).get("message_storage", "memory/multi_agent/shared_messages"))
        if not shared_registry.is_absolute():
            shared_registry = ROOT_DIR / shared_registry
        if not shared_messages.is_absolute():
            shared_messages = ROOT_DIR / shared_messages
        shared_registry.parent.mkdir(parents=True, exist_ok=True)
        shared_messages.mkdir(parents=True, exist_ok=True)
        
        multi_agent_coordinator = MultiAgentCoordinator(
            agent_id=agent_id,
            agent_name=multi_agent_cfg.get("agent_name", "primary"),
            specialization=multi_agent_cfg.get("specialization", "general"),
            skill_library=skill_library,
            config=multi_agent_cfg,
            storage_dir=storage_dir,
        )
        # Registration happens automatically in __init__ when auto_register=True
        ma_stats = multi_agent_coordinator.get_stats()
        logger.info(f"🤝 MultiAgentCoordinator ready. agent_id={agent_id[:20]}... online_agents={ma_stats['registry']['online_agents']}")
    elif multi_agent_enabled and not skill_library:
        logger.warning("🤝 MultiAgent requires SkillLibrary. Enable skills to use multi-agent features.")
    else:
        logger.info("🤝 MultiAgentCoordinator disabled.")
    
    # Layer 4: Memory Consolidation
    consolidation_cfg = cfg.get("consolidation", {})
    consolidation_enabled = bool(consolidation_cfg.get("enabled", True))
    consolidator = None
    if consolidation_enabled:
        consolidator = MemoryConsolidation(
            memory=mem,
            ollama=ollama,
            beliefs=belief_system,
            consolidation_interval=int(consolidation_cfg.get("interval_hours", 24)) * 3600
        )
        consol_stats = consolidator.get_statistics()
        logger.info(f"💤 MemoryConsolidation ready. consolidations={consol_stats['total_consolidations']}")
    else:
        logger.info("💤 MemoryConsolidation disabled.")
    
    # Layer 5: Theory of Mind (User Model)
    user_model_cfg = cfg.get("user_model", {})
    user_model_enabled = bool(user_model_cfg.get("enabled", True))
    user_model = None
    if user_model_enabled:
        user_model = UserModel(storage_path=ROOT_DIR / "data" / "user_model.json")
        logger.info(f"🧠 UserModel ready. interactions={user_model._interaction_count}")
    else:
        logger.info("🧠 UserModel disabled.")
    
    # Layer 7: Proactive Behavior
    proactive_cfg = cfg.get("proactive", {})
    proactive_enabled = bool(proactive_cfg.get("enabled", True))
    proactive = None
    if proactive_enabled and user_model:
        proactive = ProactiveBehaviorEngine(user_model=user_model, memory=mem)
        proactive_stats = proactive.get_statistics()
        logger.info(f"🚀 ProactiveBehavior ready. triggers={len(proactive._triggers)}")
    else:
        logger.info("🚀 ProactiveBehavior disabled.")
    
    # Layer 8: Meta-Learning
    meta_learn_cfg = cfg.get("meta_learning", {})
    meta_learn_enabled = bool(meta_learn_cfg.get("enabled", True))
    meta_optimizer = None
    if meta_learn_enabled:
        meta_optimizer = MetaOptimizer(storage_path=ROOT_DIR / "data" / "meta_learning.json")
        logger.info(f"🔬 MetaOptimizer ready. tests={len(meta_optimizer._ab_tests)}")
    else:
        logger.info("🔬 MetaOptimizer disabled.")
    
    # Layer 1: Goal-Oriented Behavior (integrates with heavy tick)
    goal_oriented = GoalOrientedBehavior(
        ollama=ollama,
        world=world,
        memory=mem,
        storage_dir=ROOT_DIR / "memory",
        shell_executor=shell_executor,
    )
    logger.info(f"🎯 GoalOrientedBehavior ready.")
    
    # Layer 0: Fault-Tolerant HeavyTick
    heavy = FaultTolerantHeavyTick(
        cfg=cfg,
        ollama=ollama,
        world=world,
        values=values,
        self_model=self_model,
        mem=mem,
        milestones=milestones,
        log_dir=log_dir,
        sandbox_dir=ROOT_DIR / "sandbox",
        strategy=strategy,
        vector_memory=vector_mem,
        emotion_engine=emotion_engine,
        reflection_engine=reflection_engine,
        narrative_engine=narrative_engine,
        goal_persistence=goal_persistence,
        attention_system=attention_system,
        curiosity_engine=curiosity_engine if curiosity_enabled else None,
        self_modification=self_modification,
        belief_system=belief_system,
        contradiction_resolver=contradiction_resolver,
        shell_executor=shell_executor,
        time_perception=time_perc,
        social_layer=social_layer,
        meta_cognition=meta_cog,
        # NEW: Cognitive architecture components
        goal_oriented=goal_oriented,
        tool_registry=tool_registry,
        learning_engine=learning_engine,
        skill_library=skill_library,
        user_model=user_model,
        proactive=proactive,
        meta_optimizer=meta_optimizer,
        multi_agent_coordinator=multi_agent_coordinator,  # NEW: Stage 27
    )
    logger.info("⚡ FaultTolerantHeavyTick initialized with Multi-Agent support.")

    ticker = LightTick(cfg=cfg, bus=bus)

    api_cfg = cfg.get("api", {})
    api_enabled = api_cfg.get("enabled", True)
    api_components = {
        "episodic": mem, "vector_memory": vector_mem, "value_engine": values, "strategy_engine": strategy,
        "self_model": self_model, "milestones": milestones, "dream_mode": dream, "ollama": ollama,
        "heavy_tick": heavy, "emotion_engine": emotion_engine, "reflection_engine": reflection_engine,
        "narrative_engine": narrative_engine, "goal_persistence": goal_persistence, "attention_system": attention_system,
        "curiosity_engine": curiosity_engine, "self_modification": self_modification,
        "belief_system": belief_system, "contradiction_resolver": contradiction_resolver,
        "shell_executor": shell_executor, "time_perception": time_perc, "social_layer": social_layer,
        "meta_cognition": meta_cog,
        # NEW components
        "tool_registry": tool_registry,
        "learning_engine": learning_engine,
        "skill_library": skill_library,
        "user_model": user_model,
        "proactive": proactive,
        "meta_optimizer": meta_optimizer,
        "goal_oriented": goal_oriented,
        "multi_agent_coordinator": multi_agent_coordinator,  # NEW: Stage 27
    }
    api = IntrospectionAPI(
        host=api_cfg.get("host", "127.0.0.1"),
        port=int(api_cfg.get("port", 8765)),
        components=api_components,
        start_time=start_time,
    )
    if api_enabled:
        await api.start()

    file_count = await world.scan(ROOT_DIR)
    mem.add_episode("world.scan", f"Initial scan: {file_count} files", outcome="success", data={"file_count": file_count})

    gp_stats = goal_persistence.get_stats()
    logger.info("=" * 72)
    logger.info(f"  World        : {world.summary()}")
    logger.info(f"  Values       : {values.to_prompt_context()}")
    logger.info(f"  Self v{self_model.get_version():<3}    : {self_model.get_identity()['name']}")
    logger.info(f"  Principles   : {len(self_model.get_principles())}")
    logger.info(f"  {milestones.summary()}")
    logger.info(f"  Strategy     : {strategy.to_prompt_context()!r:.120}")
    logger.info(f"  Vectors      : {vector_mem.count()} stored")
    logger.info(f"  DreamMode    : {'enabled' if dream_enabled else 'disabled'}, interval={dream_interval}h")
    logger.info(f"  EmotionEngine: dominant={dominant_name}({dominant_val:.2f})")
    logger.info(f"  Reflection   : every {reflection_every} ticks")
    logger.info(f"  Narrative    : every {narrative_every} ticks")
    logger.info(f"  GoalPersist  : completed={gp_stats['total_completed']} resumes={gp_stats['resume_count']} interrupted={gp_stats['interrupted']}")
    logger.info(f"  Attention    : {attention_system.get_focus_summary()}")
    logger.info(f"  Curiosity    : {'enabled' if curiosity_enabled else 'disabled'} open={cur_stats['open']} total_asked={cur_stats['total_asked']}")
    logger.info(f"  SelfMod      : applied={mod_stats['total_applied']} approved={mod_stats['approved']} rejected={mod_stats['rejected']}")
    logger.info(f"  Beliefs      : active={belief_stats['active']} strong={belief_stats['strong']} rejected={belief_stats['rejected']}")
    logger.info(f"  Contradictns : pending={contr_stats['pending']} resolved={contr_stats['resolved']}")
    if shell_executor:
        shell_stats = shell_executor.get_stats()
        logger.info(f"  ShellExec    : executed={shell_stats['total_executed']} rejected={shell_stats['total_rejected']}")
    if time_perc:
        time_stats = time_perc.get_stats()
        logger.info(f"  TimePerc     : patterns={time_stats['total_patterns']} time={time_stats['current_time_of_day']}")
    if social_layer:
        social_stats = social_layer.get_stats()
        logger.info(f"  SocialLayer  : incoming={social_stats['total_incoming']} outgoing={social_stats['total_outgoing']}")
    if meta_cog:
        meta_stats = meta_cog.get_stats()
        logger.info(f"  MetaCog      : insights={meta_stats['total_insights']} calibration={meta_stats['calibration_score']:.2f}")
    # NEW architecture stats
    logger.info(f"  🛠️  Tools       : {tool_stats['total_tools']} registered")
    logger.info(f"  🧠 Learning    : {learning_stats.get('total_patterns', 0)} patterns")
    if skill_library:
        logger.info(f"  📚 Skills      : {skill_stats['total_skills']} skills, {skill_stats['total_skill_uses']} uses")
    if multi_agent_coordinator:
        logger.info(f"  🤝 MultiAgent  : {ma_stats['registry']['online_agents']} agents online")
    if consolidator:
        logger.info(f"  💤 Consolidatn : {'enabled' if consolidation_enabled else 'disabled'}")
    if user_model:
        logger.info(f"  🧠 UserModel   : {user_model._interaction_count} interactions")
    if proactive:
        logger.info(f"  🚀 Proactive   : {len(proactive._triggers)} triggers")
    if meta_optimizer:
        logger.info(f"  🔬 MetaLearn   : {len(meta_optimizer._ab_tests)} A/B tests")
    logger.info(f"  API          : {'http://' + api_cfg.get('host','127.0.0.1') + ':' + str(api_cfg.get('port',8765)) if api_enabled else 'disabled'}")
    logger.info(f"  Ollama       : {'ok' if ollama_ok else 'unavailable'}")
    logger.info("=" * 72)
    logger.info("🧠 8-Layer Cognitive Architecture + Stage 27 Multi-Agent ACTIVE")
    logger.info("Running... (Ctrl+C to stop)")

    stop_event = asyncio.Event()
    def _signal_handler():
        logger.info("Shutdown signal received.")
        stop_event.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: stop_event.set())

    light_task = asyncio.create_task(ticker.start(), name="light_tick")
    heavy_task = asyncio.create_task(heavy.start(), name="heavy_tick")
    dream_task = asyncio.create_task(_dream_loop(dream, stop_event, logger), name="dream_loop") if dream_enabled else None
    consolidation_task = asyncio.create_task(_consolidation_loop(consolidator, stop_event, logger), name="consolidation_loop") if (consolidation_enabled and consolidator) else None
    multi_agent_task = asyncio.create_task(_multi_agent_loop(multi_agent_coordinator, stop_event, logger), name="multi_agent_loop") if multi_agent_enabled and multi_agent_coordinator else None

    await stop_event.wait()

    goal_persistence.mark_interrupted()
    ticker.stop()
    heavy.stop()
    monitor.stop()
    if api_enabled:
        await api.stop()

    tasks_to_cancel = [light_task, heavy_task]
    if dream_task is not None:
        tasks_to_cancel.append(dream_task)
    if consolidation_task is not None:
        tasks_to_cancel.append(consolidation_task)
    if multi_agent_task is not None:
        tasks_to_cancel.append(multi_agent_task)
    for task in tasks_to_cancel:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    values.save_weekly_snapshot()
    self_model.save_weekly_snapshot()
    await self_model.check_drift(values)
    
    # Save new components
    if learning_engine:
        learning_engine.save()
    if user_model:
        user_model.save()
    if meta_optimizer:
        meta_optimizer.save()
    if skill_library:
        skill_library.save()

    mem.add_episode("system.stop", "Digital Being stopped cleanly", outcome="success")
    vector_mem.close()
    mem.close()
    logger.info("Digital Being shut down cleanly.")

def main() -> None:
    cfg = load_yaml(CONFIG_PATH)
    seed = load_yaml(SEED_PATH)
    logger = setup_logging(cfg)
    logger.info("=" * 60)
    logger.info("  🧠 Digital Being — Stage 27.5: Multi-Agent Integration")
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
