"""
Digital Being — Multi-Agent Integration (Phase 3)

Integration layer for Phase 3 multi-agent system.
Provides unified interface for main.py.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

from core.multi_agent import (
    # Core infrastructure
    AgentRegistry,
    TaskCoordinator,
    MessageBus,
    ConsensusVoting,
    AgentSpecialization,
    DistributedMemory,
    
    # Types
    AgentRole,
    AgentInfo,
    AgentCapability,
    AgentStatus,
    Task,
    TaskPriority,
    TaskStatus,
    Message,
    MessageType,
    MessagePriority,
    VotingProposal,
    VoteOption,
    VotingStrategy,
    VoteStatus,
    MemoryEntry,
    MemoryScope,
    MemoryType,
)

log = logging.getLogger("digital_being.multi_agent_integration")


class MultiAgentSystem:
    """
    Unified multi-agent system integrating all Phase 3 components.
    
    Components:
    - AgentRegistry: Agent discovery and management
    - MessageBus: Async message passing
    - TaskCoordinator: Intelligent task distribution
    - ConsensusVoting: Democratic decision making
    - AgentSpecialization: Skill learning
    - DistributedMemory: Knowledge sharing
    
    Usage:
        system = MultiAgentSystem(agent_id, config, storage_dir)
        await system.initialize()
        
        # In main loop:
        await system.process_cycle()
        
        # Cleanup:
        await system.shutdown()
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        role: AgentRole,
        config: Dict[str, Any],
        storage_dir: Path,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.role = role
        self.config = config
        self.storage_dir = storage_dir
        
        # Components (initialized in initialize())
        self.registry: Optional[AgentRegistry] = None
        self.message_bus: Optional[MessageBus] = None
        self.task_coordinator: Optional[TaskCoordinator] = None
        self.consensus_voting: Optional[ConsensusVoting] = None
        self.specialization: Optional[AgentSpecialization] = None
        self.distributed_memory: Optional[DistributedMemory] = None
        
        # State
        self._initialized = False
        self._running = False
        
        # Statistics
        self._stats = {
            "messages_processed": 0,
            "tasks_executed": 0,
            "votes_cast": 0,
            "skills_learned": 0,
            "memories_shared": 0,
            "errors": 0,
        }
    
    async def initialize(self) -> bool:
        """
        Initialize all multi-agent components.
        
        Returns:
            True if successful
        """
        if self._initialized:
            log.warning("MultiAgentSystem already initialized")
            return True
        
        try:
            log.info(f"🤖 Initializing MultiAgentSystem for {self.agent_name} ({self.agent_id})")
            
            # Create storage directories
            ma_dir = self.storage_dir / "multi_agent"
            ma_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. AgentRegistry
            self.registry = AgentRegistry(heartbeat_timeout=60.0)
            
            # Determine capabilities based on role
            capabilities = self._get_capabilities_for_role(self.role)
            
            # Register self
            agent_info = AgentInfo(
                agent_id=self.agent_id,
                name=self.agent_name,
                role=self.role,
                status=AgentStatus.ACTIVE,
                capabilities=capabilities,
                metadata={
                    "version": "1.0",
                    "initialized_at": time.time(),
                }
            )
            
            self.registry.register(agent_info)
            log.info(f"✅ AgentRegistry initialized - {self.agent_name} registered")
            
            # 2. MessageBus
            self.message_bus = MessageBus()
            
            # Subscribe to relevant topics with handlers
            topics = [
                "task.created",
                "task.completed",
                "consensus.proposal",
                "consensus.result",
                "memory.update",
                "agent.status",
            ]
            
            for topic in topics:
                self.message_bus.subscribe(
                    self.agent_id,
                    topic,
                    self._create_message_handler(topic)
                )
            
            log.info(f"✅ MessageBus initialized - subscribed to {len(topics)} topics")
            
            # 3. TaskCoordinator
            self.task_coordinator = TaskCoordinator(
                agent_registry=self.registry,
                message_bus=self.message_bus
            )
            
            log.info("✅ TaskCoordinator initialized")
            
            # 4. ConsensusVoting
            self.consensus_voting = ConsensusVoting(
                agent_id=self.agent_id,
                agent_registry=self.registry,
                message_bus=self.message_bus
            )
            
            log.info("✅ ConsensusVoting initialized")
            
            # 5. AgentSpecialization
            specialization_path = ma_dir / f"specialization_{self.agent_id}.json"
            self.specialization = AgentSpecialization(
                agent_id=self.agent_id,
                storage_path=specialization_path
            )
            
            log.info("✅ AgentSpecialization initialized")
            
            # 6. DistributedMemory
            memory_path = ma_dir / f"distributed_memory_{self.agent_id}.json"
            self.distributed_memory = DistributedMemory(
                agent_id=self.agent_id,
                storage_path=memory_path
            )
            
            log.info("✅ DistributedMemory initialized")
            
            self._initialized = True
            log.info("🎉 MultiAgentSystem initialization complete!")
            
            return True
            
        except Exception as e:
            log.error(f"❌ MultiAgentSystem initialization failed: {e}")
            self._stats["errors"] += 1
            return False
    
    def _create_message_handler(self, topic: str):
        """Create a message handler for a specific topic."""
        async def handler(msg: Message) -> None:
            """Handle message for topic."""
            try:
                log.debug(f"📨 Received message on topic '{topic}': {msg.message_id}")
                
                if topic == "task.created":
                    # Handle new task
                    pass
                elif topic == "task.completed":
                    # Handle task completion
                    pass
                elif topic == "consensus.proposal":
                    # Handle voting proposal
                    pass
                elif topic == "consensus.result":
                    # Handle voting result
                    pass
                elif topic == "memory.update":
                    # Handle memory sync
                    pass
                elif topic == "agent.status":
                    # Handle agent status change
                    pass
                    
                self._stats["messages_processed"] += 1
                
            except Exception as e:
                log.error(f"Error handling message on topic '{topic}': {e}")
                self._stats["errors"] += 1
        
        return handler
    
    def _get_capabilities_for_role(self, role: AgentRole) -> list[AgentCapability]:
        """Map role to capabilities."""
        # Helper to create capability instance
        def cap(name: str, desc: str, skill: float = 0.8) -> AgentCapability:
            return AgentCapability(name=name, description=desc, skill_level=skill)
        
        role_capabilities = {
            AgentRole.COORDINATOR: [
                cap("task_coordination", "Coordinate tasks across agents", 0.9),
                cap("consensus_voting", "Facilitate consensus decisions", 0.85),
                cap("monitoring", "Monitor system health", 0.8),
            ],
            AgentRole.RESEARCHER: [
                cap("information_gathering", "Gather information from sources", 0.9),
                cap("data_analysis", "Analyze collected data", 0.8),
            ],
            AgentRole.EXECUTOR: [
                cap("code_execution", "Execute code safely", 0.85),
                cap("file_operations", "Perform file operations", 0.9),
            ],
            AgentRole.ANALYST: [
                cap("data_analysis", "Analyze complex data", 0.95),
                cap("pattern_recognition", "Identify patterns", 0.9),
            ],
            AgentRole.GENERALIST: [
                cap("general_purpose", "Handle various tasks", 0.7),
            ],
            AgentRole.CREATOR: [
                cap("content_creation", "Create content", 0.85),
                cap("generation", "Generate outputs", 0.8),
            ],
            AgentRole.MONITOR: [
                cap("monitoring", "Monitor system state", 0.95),
                cap("health_checks", "Perform health checks", 0.9),
            ],
        }
        
        return role_capabilities.get(role, [
            cap("general_purpose", "General task handling", 0.5)
        ])
    
    async def process_cycle(self) -> Dict[str, Any]:
        """
        Process one cycle of multi-agent operations.
        
        - Process messages
        - Check for tasks
        - Handle voting
        - Update skills
        - Sync memory
        
        Returns:
            Cycle statistics
        """
        if not self._initialized:
            log.error("Cannot process cycle - not initialized")
            return {"error": "not_initialized"}
        
        cycle_stats = {
            "messages_processed": 0,
            "tasks_checked": 0,
            "votes_handled": 0,
        }
        
        try:
            # 1. Messages are handled automatically by subscriptions
            
            # 2. Check for assigned tasks
            pending_tasks = self.task_coordinator.get_agent_tasks(
                self.agent_id,
                status=TaskStatus.ASSIGNED
            )
            
            cycle_stats["tasks_checked"] = len(pending_tasks)
            
            # 3. Check active votes
            active_votes = self.consensus_voting.get_active_proposals()
            cycle_stats["votes_handled"] = len(active_votes)
            
            # 4. Update agent heartbeat
            self.registry.heartbeat(self.agent_id)
            self.registry.update_status(
                self.agent_id,
                AgentStatus.BUSY if pending_tasks else AgentStatus.IDLE
            )
            
            return cycle_stats
            
        except Exception as e:
            log.error(f"❌ Process cycle error: {e}")
            self._stats["errors"] += 1
            return {"error": str(e)}
    
    async def _handle_message(self, msg: Message) -> None:
        """Handle individual message based on type."""
        try:
            if msg.message_type == MessageType.TASK_ASSIGNMENT:
                log.debug(f"📋 Task assignment: {msg.payload.get('task_id')}")
                # Task handling logic here
                
            elif msg.message_type == MessageType.VOTING_REQUEST:
                log.debug(f"🗳️ Voting request: {msg.payload.get('proposal_id')}")
                # Voting logic here
                
            elif msg.message_type == MessageType.MEMORY_SYNC:
                log.debug("🧠 Memory sync request")
                # Memory sync logic here
                
            elif msg.message_type == MessageType.STATUS_UPDATE:
                log.debug(f"📊 Status update from {msg.sender_id}")
                # Status handling
                
        except Exception as e:
            log.error(f"Message handling error: {e}")
            self._stats["errors"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        stats = {
            "initialized": self._initialized,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role.value if self.role else None,
            **self._stats
        }
        
        if self._initialized:
            stats.update({
                "registry": self.registry.get_statistics(),
                "message_bus": self.message_bus.get_statistics(),
                "task_coordinator": self.task_coordinator.get_stats(),
                "consensus_voting": self.consensus_voting.get_stats(),
                "specialization": self.specialization.get_stats(),
                "distributed_memory": self.distributed_memory.get_stats(),
            })
        
        return stats
    
    async def shutdown(self) -> None:
        """Graceful shutdown of multi-agent system."""
        log.info("💬 Shutting down MultiAgentSystem...")
        
        if self.registry:
            self.registry.unregister(self.agent_id)
            log.info("✅ Agent deregistered")
        
        self._initialized = False
        self._running = False
        
        log.info("✅ MultiAgentSystem shutdown complete")


async def create_multi_agent_system(
    agent_name: str,
    role: AgentRole,
    config: Dict[str, Any],
    storage_dir: Path,
) -> Optional[MultiAgentSystem]:
    """
    Factory function to create and initialize multi-agent system.
    
    Args:
        agent_name: Name of this agent
        role: Agent role
        config: Configuration dict
        storage_dir: Storage directory
    
    Returns:
        Initialized MultiAgentSystem or None on failure
    """
    agent_id = f"{agent_name}_{int(time.time())}"
    
    system = MultiAgentSystem(
        agent_id=agent_id,
        agent_name=agent_name,
        role=role,
        config=config,
        storage_dir=storage_dir,
    )
    
    success = await system.initialize()
    
    if success:
        return system
    else:
        return None
