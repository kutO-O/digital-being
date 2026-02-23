"""Multi-Agent System for Digital Being.

Provides coordination infrastructure for multiple autonomous agents:
- Agent registration and discovery
- Task distribution and execution
- Health monitoring
- Communication protocols

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
]

__version__ = "0.1.0"
