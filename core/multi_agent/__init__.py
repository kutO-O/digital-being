"""Multi-Agent System for Digital Being.

Complete infrastructure for coordinating multiple autonomous agents:
- Agent registration and discovery
- Intelligent task distribution
- Inter-agent communication
- Consensus-based decision making
- Skill learning and specialization
- Distributed knowledge sharing
- Health monitoring

Phase 3 - Multi-Agent Coordination (COMPLETE!)
"""

from .agent_registry import (
    AgentCapability,
    AgentInfo,
    AgentRegistry,
    AgentRole,
    AgentStatus,
)
from .task_coordinator import (
    Task,
    TaskCoordinator,
    TaskPriority,
    TaskStatus,
)
from .message_bus import (
    Message,
    MessageBus,
    MessagePriority,
    MessageType,
)
from .consensus_voting import (
    ConsensusVoting,
    Vote,
    VoteOption,
    VotingProposal,
    VotingStrategy,
    VoteStatus,
)
from .agent_specialization import (
    AgentSpecialization,
    PerformanceProfile,
    SkillExperience,
)
from .distributed_memory import (
    DistributedMemory,
    MemoryEntry,
    MemoryScope,
    MemoryType,
)

__all__ = [
    # Agent Registry
    "AgentRegistry",
    "AgentInfo",
    "AgentRole",
    "AgentStatus",
    "AgentCapability",
    # Task Coordinator
    "TaskCoordinator",
    "Task",
    "TaskPriority",
    "TaskStatus",
    # Message Bus
    "MessageBus",
    "Message",
    "MessageType",
    "MessagePriority",
    # Consensus Voting
    "ConsensusVoting",
    "VotingProposal",
    "Vote",
    "VoteOption",
    "VotingStrategy",
    "VoteStatus",
    # Agent Specialization
    "AgentSpecialization",
    "PerformanceProfile",
    "SkillExperience",
    # Distributed Memory
    "DistributedMemory",
    "MemoryEntry",
    "MemoryScope",
    "MemoryType",
]

__version__ = "1.0.0"  # Production ready!
