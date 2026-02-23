# 🚀 Multi-Agent Integration Plan - Phase 3

**Date:** 2026-02-23  
**Status:** 🟡 In Progress

---

## 🎯 Objective

Integrate Phase 3 Multi-Agent System (86.5KB production code) into `main.py`, replacing old Stage 27-28 implementation.

---

## 📊 Current State Analysis

### **Existing Components (Stage 27-28):**

```python
# OLD - To be replaced
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.multi_agent.task_delegation import TaskDelegation
from core.multi_agent.consensus_builder import ConsensusBuilder
from core.multi_agent.agent_roles import AgentRoleManager
```

### **New Components (Phase 3):**

```python
# NEW - Phase 3 production-ready
from core.multi_agent import (
    # Core infrastructure
    AgentRegistry,
    TaskCoordinator,
    MessageBus,
    ConsensusVoting,
    
    # Advanced features
    AgentSpecialization,
    DistributedMemory,
    
    # Enums & Types
    AgentRole,
    AgentCapability,
    AgentStatus,
    TaskPriority,
    MessageType,
    VotingStrategy,
)
```

---

## 🔧 Integration Steps

### **Step 1: Update Imports** ✅

Replace old imports with Phase 3 imports:

```python
# Remove
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.multi_agent.task_delegation import TaskDelegation
from core.multi_agent.consensus_builder import ConsensusBuilder

# Add
from core.multi_agent import (
    AgentRegistry,
    TaskCoordinator,
    MessageBus,
    ConsensusVoting,
    AgentSpecialization,
    DistributedMemory,
    AgentRole,
    AgentInfo,
    AgentCapability,
    Task,
    TaskPriority,
    Message,
    MessageType,
    VotingProposal,
    VotingStrategy,
    MemoryEntry,
    MemoryScope,
)
```

### **Step 2: Initialize AgentRegistry** 🔴

Replace `MultiAgentCoordinator` with `AgentRegistry`:

```python
if multi_agent_enabled:
    registry_path = storage_dir / "multi_agent" / "registry.json"
    
    # Initialize registry
    agent_registry = AgentRegistry(registry_path)
    
    # Register self
    agent_info = AgentInfo(
        agent_id=agent_id,
        name=multi_agent_cfg.get("agent_name", "primary"),
        role=AgentRole.COORDINATOR,
        capabilities=[
            AgentCapability.TASK_COORDINATION,
            AgentCapability.CONSENSUS_VOTING,
            AgentCapability.LEARNING,
        ],
        specializations=["general", "coordination"],
        endpoint="local",
        metadata={"version": cfg["system"]["version"]}
    )
    
    agent_registry.register_agent(agent_info)
    logger.info(f"🤖 AgentRegistry: registered {agent_id}")
```

### **Step 3: Initialize MessageBus** 🔴

```python
    # Message bus for async communication
    message_bus = MessageBus()
    
    # Subscribe to relevant topics
    message_bus.subscribe("task.created", agent_id)
    message_bus.subscribe("task.completed", agent_id)
    message_bus.subscribe("consensus.proposal", agent_id)
    message_bus.subscribe("memory.update", agent_id)
    
    logger.info("📨 MessageBus initialized")
```

### **Step 4: Initialize TaskCoordinator** 🔴

```python
    # Task coordination system
    task_coordinator = TaskCoordinator(
        agent_registry=agent_registry,
        message_bus=message_bus
    )
    
    logger.info("📋 TaskCoordinator initialized")
```

### **Step 5: Initialize ConsensusVoting** 🔴

```python
    # Consensus voting for decisions
    consensus_voting = ConsensusVoting(
        agent_id=agent_id,
        agent_registry=agent_registry,
        message_bus=message_bus
    )
    
    logger.info("🗳️ ConsensusVoting initialized")
```

### **Step 6: Initialize AgentSpecialization** 🔴

```python
    # Agent skill learning system
    specialization_path = storage_dir / "multi_agent" / "specialization.json"
    
    agent_specialization = AgentSpecialization(
        agent_id=agent_id,
        storage_path=specialization_path
    )
    
    logger.info("🎓 AgentSpecialization initialized")
```

### **Step 7: Initialize DistributedMemory** 🔴

```python
    # Distributed memory for knowledge sharing
    memory_path = storage_dir / "multi_agent" / "distributed_memory.json"
    
    distributed_memory = DistributedMemory(
        agent_id=agent_id,
        storage_path=memory_path
    )
    
    logger.info("🧠 DistributedMemory initialized")
```

### **Step 8: Create Multi-Agent Loop** 🔴

Replace old `_multi_agent_loop` with new implementation:

```python
async def _multi_agent_loop(
    agent_id: str,
    message_bus: MessageBus,
    task_coordinator: TaskCoordinator,
    consensus_voting: ConsensusVoting,
    agent_specialization: AgentSpecialization,
    distributed_memory: DistributedMemory,
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
    logger.info("🤝 Multi-Agent coordination loop started")
    
    poll_interval = 2.0
    
    while not stop_event.is_set():
        try:
            # Process incoming messages
            messages = message_bus.get_messages(agent_id, limit=10)
            
            for msg in messages:
                # Handle different message types
                if msg.message_type == MessageType.TASK_ASSIGNMENT:
                    # Process task assignment
                    task_data = msg.payload
                    logger.debug(f"📋 Received task: {task_data.get('task_id')}")
                    
                elif msg.message_type == MessageType.VOTING_REQUEST:
                    # Process voting request
                    proposal_id = msg.payload.get("proposal_id")
                    logger.debug(f"🗳️ Voting request: {proposal_id}")
                    
                elif msg.message_type == MessageType.MEMORY_SYNC:
                    # Process memory sync
                    logger.debug("🧠 Memory sync received")
                    
                # Mark message as processed
                message_bus.acknowledge(msg.message_id, agent_id)
            
            # Check for pending tasks
            pending_tasks = task_coordinator.get_agent_tasks(
                agent_id,
                status="pending"
            )
            
            if pending_tasks:
                logger.debug(f"📋 {len(pending_tasks)} pending tasks")
            
            # Update agent heartbeat
            # agent_registry.update_heartbeat(agent_id)  # This would be automatic
            
        except Exception as e:
            logger.error(f"🤝 Multi-agent loop error: {e}")
        
        await asyncio.sleep(poll_interval)
    
    logger.info("🤝 Multi-Agent loop stopped")
```

### **Step 9: Update API Components** 🔴

Add new components to introspection API:

```python
api_components = {
    # ... existing ...
    
    # Phase 3 Multi-Agent
    "agent_registry": agent_registry,
    "message_bus": message_bus,
    "task_coordinator": task_coordinator,
    "consensus_voting": consensus_voting,
    "agent_specialization": agent_specialization,
    "distributed_memory": distributed_memory,
}
```

### **Step 10: Add Stats Logging** 🔴

Update startup stats:

```python
if agent_registry:
    reg_stats = agent_registry.get_stats()
    logger.info(f"  🤖 AgentRegistry: {reg_stats['online_agents']} online, {reg_stats['total_tasks_coordinated']} tasks coordinated")
    
    tc_stats = task_coordinator.get_stats()
    logger.info(f"  📋 TaskCoordinator: {tc_stats['active_tasks']} active, {tc_stats['completed_tasks']} completed")
    
    cv_stats = consensus_voting.get_stats()
    logger.info(f"  🗳️ ConsensusVoting: {cv_stats['active_proposals']} active, {cv_stats['completed_votes']} completed")
    
    as_stats = agent_specialization.get_stats()
    logger.info(f"  🎓 Specialization: {as_stats['total_skills']} skills, expertise={as_stats['average_expertise']:.2f}")
    
    dm_stats = distributed_memory.get_stats()
    logger.info(f"  🧠 DistMemory: {dm_stats['total_memories']} memories, {dm_stats['shared_count']} shared")
```

---

## 📝 Code Replacement Summary

### **Remove:**
- `MultiAgentCoordinator` class usage
- `TaskDelegation` class usage
- `ConsensusBuilder` class usage
- Old message broker logic
- Old agent registration

### **Add:**
- `AgentRegistry` initialization
- `MessageBus` initialization
- `TaskCoordinator` initialization
- `ConsensusVoting` initialization
- `AgentSpecialization` initialization
- `DistributedMemory` initialization
- New multi-agent loop
- Stats logging for all components

---

## ✅ Benefits

1. **Production-ready code** (86.5KB tested)
2. **Full type safety** (MyPy validated)
3. **Comprehensive features**:
   - Intelligent task assignment
   - Async message passing
   - Democratic voting
   - Skill learning
   - Knowledge sharing
4. **Clean architecture** (6 independent modules)
5. **Extensible design** (easy to add features)

---
## 🚦 Testing Plan

1. **Unit tests** - Already exist in `tests/multi_agent/`
2. **Integration test** - Create `test_multi_agent_integration.py`
3. **Live test** - Run Digital Being with 2+ agents
4. **Performance test** - Measure overhead

---

## 📊 Expected Results

After integration:

```
🤖 AgentRegistry: 6 agents online
📨 MessageBus: 0 pending messages
📋 TaskCoordinator: 0 active tasks
🗳️ ConsensusVoting: 0 active proposals
🎓 AgentSpecialization: 0 skills learned
🧠 DistributedMemory: 0 shared memories
```

As system runs:
- Tasks get coordinated intelligently
- Agents vote on decisions
- Skills are learned from experience
- Knowledge is shared across agents

---

## 📞 Next Steps

1. Create integration branch
2. Update imports
3. Replace old code
4. Add new initialization
5. Update loops
6. Test thoroughly
7. Merge to main
8. Document usage

---

**Ready to implement!** 🚀
