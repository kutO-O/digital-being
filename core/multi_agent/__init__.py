"""Multi-Agent System for Digital Being.

Provides coordination infrastructure for multiple autonomous agents:
- Agent registration and discovery
- Task distribution and execution
- Inter-agent communication
- Consensus-based decision making
- Health monitoring

Phase 3 - Multi-Agent Coordination
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
]

__version__ = "0.2.0"
