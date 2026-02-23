# 🚀 Integration Example - Phase 3 Multi-Agent

## Quick Integration Guide

How to replace old multi-agent code in `main.py` with Phase 3 system.

---

## Step 1: Update Imports

### OLD (remove):
```python
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.multi_agent.task_delegation import TaskDelegation
from core.multi_agent.consensus_builder import ConsensusBuilder
from core.multi_agent.agent_roles import AgentRoleManager
```

### NEW (add):
```python
from core.multi_agent_integration import (
    MultiAgentSystem,
    create_multi_agent_system,
)
from core.multi_agent import AgentRole
```

---

## Step 2: Initialize System

### OLD code (lines ~700-780 in main.py):
```python
# OLD - Remove this entire block
multi_agent_coordinator = MultiAgentCoordinator(
    agent_id=agent_id,
    agent_name=multi_agent_cfg.get("agent_name", "primary"),
    specialization=multi_agent_cfg.get("specialization", "general"),
    skill_library=skill_library,
    config=multi_agent_cfg,
    storage_dir=storage_dir,
)

task_delegation = TaskDelegation(...)
consensus_builder = ConsensusBuilder(...)
agent_roles = AgentRoleManager(...)
```

### NEW code (replace with):
```python
# NEW - Phase 3 Multi-Agent System
multi_agent_system = None

if multi_agent_enabled:
    role_map = {
        "coordinator": AgentRole.COORDINATOR,
        "researcher": AgentRole.RESEARCHER,
        "executor": AgentRole.EXECUTOR,
        "analyst": AgentRole.ANALYST,
        "planner": AgentRole.PLANNER,
        "tester": AgentRole.TESTER,
    }
    
    agent_role = role_map.get(
        multi_agent_cfg.get("agent_name", "primary").lower(),
        AgentRole.COORDINATOR
    )
    
    multi_agent_system = await create_multi_agent_system(
        agent_name=multi_agent_cfg.get("agent_name", "primary"),
        role=agent_role,
        config=multi_agent_cfg,
        storage_dir=ROOT_DIR / "memory",
    )
    
    if multi_agent_system:
        ma_stats = multi_agent_system.get_stats()
        logger.info(f"🤝 MultiAgentSystem ready: {ma_stats['agent_name']} ({ma_stats['role']})")
        logger.info(f"   Registry: {ma_stats['registry']['online_agents']} agents online")
        logger.info(f"   Tasks: {ma_stats['task_coordinator']['active_tasks']} active")
        logger.info(f"   Voting: {ma_stats['consensus_voting']['active_proposals']} proposals")
    else:
        logger.error("❌ Failed to initialize MultiAgentSystem")
else:
    logger.info("🤝 MultiAgentSystem disabled")
```

---

## Step 3: Update Main Loop

### OLD loop (lines ~980-1000):
```python
# OLD - Remove
async def _multi_agent_loop(
    coordinator: MultiAgentCoordinator,
    stop_event: asyncio.Event,
    logger: logging.Logger
) -> None:
    while not stop_event.is_set():
        processed = await coordinator.process_messages()
        await asyncio.sleep(poll_interval)
```

### NEW loop (replace with):
```python
# NEW - Phase 3 Multi-Agent Loop
async def _multi_agent_loop(
    system: MultiAgentSystem,
    stop_event: asyncio.Event,
    logger: logging.Logger
) -> None:
    """
    Main multi-agent coordination loop.
    
    Handles:
    - Message processing
    - Task coordination
    - Consensus voting
    - Skill learning
    - Memory synchronization
    """
    logger.info("🤝 Multi-Agent system loop started")
    
    poll_interval = 2.0
    cycle_count = 0
    
    while not stop_event.is_set():
        try:
            # Process one cycle
            cycle_stats = await system.process_cycle()
            
            if cycle_stats.get("messages_processed", 0) > 0:
                logger.debug(
                    f"📨 Cycle #{cycle_count}: "
                    f"messages={cycle_stats['messages_processed']}, "
                    f"tasks={cycle_stats.get('tasks_checked', 0)}"
                )
            
            cycle_count += 1
            
            # Log stats every 30 cycles (~1 minute)
            if cycle_count % 30 == 0:
                stats = system.get_stats()
                logger.info(
                    f"📊 Multi-Agent stats: "
                    f"messages={stats['messages_processed']}, "
                    f"tasks={stats['tasks_executed']}, "
                    f"errors={stats['errors']}"
                )
        
        except Exception as e:
            logger.error(f"🤝 Multi-agent loop error: {e}")
        
        await asyncio.sleep(poll_interval)
    
    logger.info("🤝 Multi-Agent loop stopped")
```

---

## Step 4: Update Task Creation

### Creating new task in loop:
```python
# Update task creation in main loop
multi_agent_task = None

if multi_agent_system:
    multi_agent_task = asyncio.create_task(
        _multi_agent_loop(multi_agent_system, stop_event, logger),
        name="multi_agent_loop"
    )
```

---

## Step 5: Update API Components

### OLD:
```python
"multi_agent": multi_agent_coordinator,
```

### NEW:
```python
"multi_agent_system": multi_agent_system,
```

---

## Step 6: Update Stats Logging

### Add to startup stats (line ~900):
```python
if multi_agent_system:
    stats = multi_agent_system.get_stats()
    
    logger.info(f"  🤖 AgentRegistry: {stats['registry']['online_agents']} online")
    logger.info(f"  📨 MessageBus: {stats['message_bus']['total_messages']} messages")
    logger.info(f"  📋 TaskCoord: {stats['task_coordinator']['active_tasks']} active")
    logger.info(f"  🗳️ Consensus: {stats['consensus_voting']['active_proposals']} proposals")
    logger.info(f"  🎓 Specialization: {stats['specialization']['total_skills']} skills")
    logger.info(f"  🧠 DistMemory: {stats['distributed_memory']['total_memories']} memories")
```

---

## Step 7: Update Shutdown

### Add to shutdown (line ~1060):
```python
if multi_agent_system:
    await multi_agent_system.shutdown()
    logger.info("✅ MultiAgentSystem shut down")
```

---

## Complete Diff Summary

### Lines to REMOVE:
- Imports: `MultiAgentCoordinator`, `TaskDelegation`, `ConsensusBuilder`, `AgentRoleManager`
- Initialization: ~80 lines of old multi-agent setup
- Loop: Old `_multi_agent_loop` function

### Lines to ADD:
- Imports: `MultiAgentSystem`, `create_multi_agent_system`, `AgentRole`
- Initialization: ~20 lines of new setup
- Loop: New `_multi_agent_loop` with Phase 3 system
- Stats logging: ~6 lines

**Net change: -60 lines, +cleaner code, +more features!**

---

## Testing

After integration:

```bash
# Run Digital Being
python main.py

# Check logs for:
✅ AgentRegistry initialized
✅ MessageBus initialized  
✅ TaskCoordinator initialized
✅ ConsensusVoting initialized
✅ AgentSpecialization initialized
✅ DistributedMemory initialized
🎉 MultiAgentSystem initialization complete!
```

---

## Benefits

1. **Cleaner code** - Single unified interface
2. **More features** - 6 integrated components
3. **Better performance** - Optimized message processing
4. **Type safety** - Full MyPy compliance
5. **Easier debugging** - Unified stats and logging

---

## Next Steps

1. Test with single agent
2. Test with multiple agents
3. Monitor performance
4. Add custom handlers
5. Extend with new features

**Ready to integrate!** 🚀
