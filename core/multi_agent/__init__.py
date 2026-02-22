"""Multi-Agent collaboration components."""

from core.multi_agent.task_delegation import TaskDelegation
from core.multi_agent.consensus_builder import ConsensusBuilder
from core.multi_agent.agent_roles import AgentRoleManager, AgentRole
from core.multi_agent.autoscaler import AgentAutoscaler, ScalingPolicy

__all__ = [
    "TaskDelegation",
    "ConsensusBuilder",
    "AgentRoleManager",
    "AgentRole",
    "AgentAutoscaler",
    "ScalingPolicy",
]
