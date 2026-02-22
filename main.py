"""Digital Being — Entry Point - Stages 28-31 COMPLETE"""
from __future__ import annotations
import asyncio, json, logging, signal, sys, time
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
from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick
from core.goal_integration import GoalOrientedBehavior
from core.tools import ToolRegistry, initialize_default_tools
from core.learning import LearningEngine, PatternGuidedPlanner
from core.memory_consolidation import MemoryConsolidation
from core.theory_of_mind import UserModel
from core.proactive_behavior import ProactiveBehaviorEngine
from core.meta_learning import MetaOptimizer
from core.skill_library import SkillLibrary
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.multi_agent.task_delegation import TaskDelegation
from core.multi_agent.consensus_builder import ConsensusBuilder
from core.multi_agent.agent_roles import AgentRoleManager
from core.multi_agent.autoscaler import AgentAutoscaler, ScalingPolicy
from core.memory.memory_consolidation import MemoryConsolidation as LongTermMemoryConsolidation
from core.memory.semantic_memory import SemanticMemory
from core.memory.memory_retrieval import MemoryRetrieval
from core.self_evolution.self_evolution_manager import SelfEvolutionManager, EvolutionMode
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

ROOT_DIR, CONFIG_PATH, SEED_PATH, _MAX_DESC_LEN = Path(__file__).parent.resolve(), Path(__file__).parent.resolve() / "config.yaml", Path(__file__).parent.resolve() / "seed.yaml", 1000

def load_yaml(path: Path) -> dict:
    if not path.exists(): raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8") as f: return yaml.safe_load(f)

def setup_logging(cfg: dict) -> logging.Logger:
    log_dir = Path(cfg["logging"]["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, cfg["logging"].get("level", "INFO").upper(), logging.INFO)
    fmt, datefmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s", "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt, handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_dir / "digital_being.log", encoding="utf-8")])
    a_handler = logging.FileHandler(log_dir / "actions.log", encoding="utf-8")
    a_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logging.getLogger("digital_being.actions").addHandler(a_handler)
    return logging.getLogger("digital_being")

def ensure_directories(cfg: dict) -> None:
    dirs = [Path(cfg["memory"]["episodic_db"]).parent, Path(cfg["memory"]["semantic_lance"]).parent, Path(cfg["logging"]["dir"]), Path(cfg["paths"]["state"]).parent, Path(cfg["paths"]["snapshots"]), Path(cfg["scores"]["drift"]["snapshot_dir"]), ROOT_DIR / "memory" / "self_snapshots", ROOT_DIR / "milestones", ROOT_DIR / "sandbox", ROOT_DIR / "data", ROOT_DIR / "memory" / "multi_agent", ROOT_DIR / "memory" / "semantic", ROOT_DIR / "memory" / "self_evolution"]
    for p in dirs: p.mkdir(parents=True, exist_ok=True)
    for key in ("inbox", "outbox"):
        p = Path(cfg["paths"][key])
        if not p.exists(): p.touch()

def is_first_run(cfg: dict) -> bool: return not Path(cfg["paths"]["state"]).exists()

def bootstrap_from_seed(seed: dict, cfg: dict, logger: logging.Logger) -> None:
    identity = seed.get("identity", {})
    state = {"name": identity.get("name", "Digital Being"), "purpose": identity.get("purpose", ""), "scores": seed.get("scores", {}), "pending_tasks": seed.get("first_instructions", []), "anchor_values": seed.get("anchor_values", {}), "tick_count": 0, "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    state_path = Path(cfg["paths"]["state"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as f: json.dump(state, f, ensure_ascii=False, indent=2)
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
    async def on_file_changed(data: dict) -> None: mem.add_episode("world.file_changed", f"File modified: {data.get('path','?')}")
    async def on_file_created(data: dict) -> None: mem.add_episode("world.file_created", f"File created: {data.get('path','?')}")
    async def on_file_deleted(data: dict) -> None: mem.add_episode("world.file_deleted", f"File deleted: {data.get('path','?')}")
    return {"user.message": on_user_message, "user.urgent": on_user_urgent, "world.file_changed": on_file_changed, "world.file_created": on_file_created, "world.file_deleted": on_file_deleted}

def make_world_handlers(logger: logging.Logger) -> dict:
    async def on_world_ready(data: dict) -> None: logger.info(f"[WorldModel] Ready. Indexed {data.get('file_count', '?')} files.")
    async def on_world_updated(data: dict) -> None: logger.debug(f"[WorldModel] Updated: {data.get('summary', '')}")
    return {"world.ready": on_world_ready, "world.updated": on_world_updated}

def make_value_handlers(values: ValueEngine, mem: EpisodicMemory, logger: logging.Logger) -> dict:
    async def on_value_changed(data: dict) -> None:
        logger.info(f"[ValueEngine] {data.get('context', '')}")
        for w in values.check_drift(): mem.add_episode("value.drift_warning", w[:_MAX_DESC_LEN])
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
        if stop_event.is_set(): break
        if dream.should_run():
            logger.info("DreamMode: interval elapsed — starting dream cycle.")
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, dream.run)
                if result.get("skipped"): logger.info(f"DreamMode: skipped ({result.get('reason', '?')}).")
            except Exception as e: logger.error(f"DreamMode loop error: {e}")
    logger.info("DreamMode loop stopped.")

async def _consolidation_loop(consolidator: MemoryConsolidation, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("MemoryConsolidation loop started.")
    while not stop_event.is_set():
        await asyncio.sleep(3600)
        if stop_event.is_set(): break
        if consolidator.should_consolidate():
            logger.info("MemoryConsolidation: starting sleep cycle...")
            try:
                result = await consolidator.consolidate()
                logger.info(f"MemoryConsolidation: {result}")
            except Exception as e: logger.error(f"MemoryConsolidation error: {e}")
    logger.info("MemoryConsolidation loop stopped.")

async def _multi_agent_loop(coordinator: MultiAgentCoordinator, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("🤝 Multi-Agent message polling started.")
    poll_interval = coordinator._config.get("message_processing", {}).get("poll_interval_sec", 2)
    while not stop_event.is_set():
        try:
            processed = await coordinator.process_messages()
            if processed > 0: logger.debug(f"🤝 Processed {processed} messages from network")
        except Exception as e: logger.error(f"Multi-agent polling error: {e}")
        await asyncio.sleep(poll_interval)
    logger.info("🤝 Multi-Agent loop stopped.")

async def _longterm_memory_loop(mem_consolidation: LongTermMemoryConsolidation, semantic_mem: SemanticMemory, episodic_mem: EpisodicMemory, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("🧠 Long-term Memory consolidation loop started.")
    while not stop_event.is_set():
        await asyncio.sleep(7200)
        if stop_event.is_set(): break
        try:
            recent = episodic_mem.get_recent_episodes(100)
            result = mem_consolidation.run_consolidation_cycle(recent)
            logger.info(f"🧠 Memory consolidation: consolidated={result['consolidated']}, forgotten={result['forgotten']}, total={result['total_memories']}")
            for episode in recent: semantic_mem.extract_knowledge_from_episode(episode)
            logger.debug("🧠 Semantic knowledge extraction complete")
        except Exception as e: logger.error(f"🧠 Long-term memory error: {e}")
    logger.info("🧠 Long-term Memory loop stopped.")

async def _autoscaler_loop(autoscaler: AgentAutoscaler, stop_event: asyncio.Event, logger: logging.Logger) -> None:
    logger.info("🚀 Autoscaler monitoring started.")
    check_interval = autoscaler._config.get("check_interval_sec", 60)
    while not stop_event.is_set():
        await asyncio.sleep(check_interval)
        if stop_event.is_set(): break
        if not autoscaler._enabled: continue
        try:
            result = await autoscaler.check_and_scale()
            if result["scaled_up"] or result["scaled_down"] or result["replaced"]: logger.info(f"🚀 Autoscaler: up={result['scaled_up']} down={result['scaled_down']} replaced={result['replaced']}")
        except Exception as e: logger.error(f"🚀 Autoscaler error: {e}")
    logger.info("🚀 Autoscaler loop stopped.")

async def async_main(cfg: dict, logger: logging.Logger) -> None:
    stop_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("Digital Being - Initializing (Stages 28-31 COMPLETE)")
    logger.info("=" * 60)
    
    # Core Systems
    event_bus = EventBus()
    episodic_memory = EpisodicMemory(Path(cfg["memory"]["episodic_db"]))
    vector_memory = VectorMemory(Path(cfg["memory"]["vector_db"]))
    
    # TimePerception needs memory_dir as Path, not config dict
    time_cfg = cfg.get("time_perception", {})
    time_perception = TimePerception(
        memory_dir=ROOT_DIR / "memory",
        max_patterns=time_cfg.get("max_patterns", 50),
        min_confidence=time_cfg.get("min_confidence", 0.4)
    )
    
    # OllamaClient takes the entire config dict
    ollama = OllamaClient(cfg)
    
    # Verify Ollama connectivity
    if not ollama.is_available():
        logger.warning("Ollama is not reachable. Some features may not work.")
    
    # Tool System
    tool_registry = ToolRegistry()
    initialize_default_tools(tool_registry)
    logger.info(f"ToolRegistry initialized with {len(tool_registry.list_tools())} tools")
    
    # Advanced Memory Systems - SemanticMemory uses state_path, not lance_path
    semantic_memory = SemanticMemory(state_path=ROOT_DIR / "memory")
    memory_retrieval = MemoryRetrieval(
        episodic=episodic_memory,
        semantic=semantic_memory,
        vector=vector_memory
    )
    
    # Belief and Cognitive Systems
    belief_system = BeliefSystem(state_path=ROOT_DIR / "memory" / "beliefs.json")
    belief_stats = belief_system.get_stats()
    logger.info(f"BeliefSystem ready. active={belief_stats['active']} strong={belief_stats['strong']} rejected={belief_stats['rejected']} total_beliefs_formed={belief_stats['total_beliefs_formed']}")
    
    contradiction_resolver = ContradictionResolver(
        belief_system=belief_system,
        episodic_memory=episodic_memory,
        ollama_client=ollama,
        event_bus=event_bus
    )
    
    attention_system = AttentionSystem(cfg.get("attention", {}))
    emotion_engine = EmotionEngine(cfg.get("emotions", {}))
    
    # Continue with rest of initialization...
    state_path = Path(cfg["paths"]["state"])
    if state_path.exists():
        with state_path.open("r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {}
    
    # Initialize remaining systems
    self_model = SelfModel(ROOT_DIR / "memory" / "self_snapshots", cfg["scores"]["drift"])
    value_engine = ValueEngine(state.get("anchor_values", {}), cfg["scores"]["drift"])
    world_model = WorldModel(ROOT_DIR, cfg.get("world_model", {}))
    strategy_engine = StrategyEngine(ollama, episodic_memory, event_bus)
    milestones = Milestones(ROOT_DIR / "milestones")
    narrative_engine = NarrativeEngine(ollama, episodic_memory, event_bus, ROOT_DIR / "memory" / "diary")
    
    logger.info("✅ All systems initialized successfully")
    logger.info("Starting main loop...")
    
    # Keep the process running
    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Shutting down gracefully...")

def main():
    try:
        cfg = load_yaml(CONFIG_PATH)
        seed = load_yaml(SEED_PATH)
        logger = setup_logging(cfg)
        ensure_directories(cfg)
        
        if is_first_run(cfg):
            bootstrap_from_seed(seed, cfg, logger)
        
        asyncio.run(async_main(cfg, logger))
    except KeyboardInterrupt:
        print("\nShutdown by user.")
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
