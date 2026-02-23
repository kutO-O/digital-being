"""Agent Registry for Multi-Agent Coordination.

Manages multiple autonomous agents working together:
- Agent registration and discovery
- Health monitoring
- Task distribution
- Agent communication

Phase 3 - Multi-Agent System
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("digital_being.multi_agent.registry")


class AgentStatus(Enum):
    """Agent operational status."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class AgentRole(Enum):
    """Agent specialization roles."""
    GENERALIST = "generalist"      # Can handle any task
    RESEARCHER = "researcher"      # Web research, knowledge gathering
    ANALYST = "analyst"            # Data analysis, pattern recognition
    CREATOR = "creator"            # Content creation, generation
    EXECUTOR = "executor"          # Action execution, shell commands
    COORDINATOR = "coordinator"    # Task delegation, orchestration
    MONITOR = "monitor"            # System monitoring, health checks


@dataclass
class AgentCapability:
    """Describes what an agent can do."""
    name: str
    description: str
    skill_level: float = 1.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    agent_id: str
    name: str
    role: AgentRole
    status: AgentStatus
    capabilities: List[AgentCapability]
    
    # Metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    average_task_time: float = 0.0
    
    # Health
    last_heartbeat: float = field(default_factory=time.time)
    health_score: float = 1.0  # 0.0 to 1.0
    
    # Connection
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "skill_level": cap.skill_level,
                }
                for cap in self.capabilities
            ],
            "metrics": {
                "tasks_completed": self.tasks_completed,
                "tasks_failed": self.tasks_failed,
                "average_task_time": self.average_task_time,
                "success_rate": self._calculate_success_rate(),
            },
            "health": {
                "score": self.health_score,
                "last_heartbeat": self.last_heartbeat,
                "time_since_heartbeat": time.time() - self.last_heartbeat,
            },
            "metadata": self.metadata,
        }
    
    def _calculate_success_rate(self) -> float:
        """Calculate task success rate."""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 1.0
        return self.tasks_completed / total


class AgentRegistry:
    """
    Central registry for multi-agent coordination.
    
    Responsibilities:
    - Agent registration and discovery
    - Health monitoring
    - Task distribution
    - Communication coordination
    
    Example:
        registry = AgentRegistry()
        
        # Register agent
        agent_info = AgentInfo(
            agent_id="agent_1",
            name="Research Assistant",
            role=AgentRole.RESEARCHER,
            status=AgentStatus.ACTIVE,
            capabilities=[
                AgentCapability("web_search", "Search the web", skill_level=0.9)
            ]
        )
        registry.register(agent_info)
        
        # Find agents by role
        researchers = registry.find_by_role(AgentRole.RESEARCHER)
    """
    
    def __init__(self, heartbeat_timeout: float = 60.0):
        """
        Args:
            heartbeat_timeout: Seconds before agent considered offline
        """
        self._agents: Dict[str, AgentInfo] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._event_listeners: List[Callable] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        log.info(
            f"AgentRegistry initialized (heartbeat_timeout={heartbeat_timeout}s)"
        )
    
    def register(self, agent_info: AgentInfo) -> None:
        """Register a new agent."""
        agent_id = agent_info.agent_id
        
        if agent_id in self._agents:
            log.warning(f"Agent {agent_id} already registered, updating info")
        
        self._agents[agent_id] = agent_info
        
        log.info(
            f"Agent registered: {agent_id} (name={agent_info.name}, "
            f"role={agent_info.role.value})"
        )
        
        self._emit_event("agent_registered", agent_info.to_dict())
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id not in self._agents:
            log.warning(f"Cannot unregister unknown agent: {agent_id}")
            return False
        
        agent_info = self._agents.pop(agent_id)
        
        log.info(f"Agent unregistered: {agent_id} (name={agent_info.name})")
        
        self._emit_event("agent_unregistered", {"agent_id": agent_id})
        
        return True
    
    def heartbeat(self, agent_id: str) -> None:
        """Update agent heartbeat."""
        if agent_id not in self._agents:
            log.warning(f"Heartbeat from unknown agent: {agent_id}")
            return
        
        agent = self._agents[agent_id]
        agent.last_heartbeat = time.time()
        
        # If agent was offline, mark as active
        if agent.status == AgentStatus.OFFLINE:
            agent.status = AgentStatus.ACTIVE
            log.info(f"Agent {agent_id} back online")
    
    def update_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update agent status."""
        if agent_id not in self._agents:
            log.warning(f"Cannot update status for unknown agent: {agent_id}")
            return
        
        agent = self._agents[agent_id]
        old_status = agent.status
        agent.status = status
        
        log.debug(f"Agent {agent_id} status: {old_status.value} -> {status.value}")
        
        self._emit_event(
            "agent_status_changed",
            {
                "agent_id": agent_id,
                "old_status": old_status.value,
                "new_status": status.value,
            },
        )
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent info by ID."""
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> List[AgentInfo]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    def find_by_role(self, role: AgentRole) -> List[AgentInfo]:
        """Find all agents with specific role."""
        return [agent for agent in self._agents.values() if agent.role == role]
    
    def find_by_capability(
        self, capability_name: str, min_skill: float = 0.0
    ) -> List[AgentInfo]:
        """Find agents with specific capability."""
        result = []
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if cap.name == capability_name and cap.skill_level >= min_skill:
                    result.append(agent)
                    break
        return result
    
    def find_available(self, role: Optional[AgentRole] = None) -> List[AgentInfo]:
        """Find available (idle or active) agents."""
        available_statuses = {AgentStatus.IDLE, AgentStatus.ACTIVE}
        agents = self._agents.values()
        
        if role:
            agents = [a for a in agents if a.role == role]
        
        return [a for a in agents if a.status in available_statuses]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total = len(self._agents)
        
        status_counts = {}
        for status in AgentStatus:
            count = sum(1 for a in self._agents.values() if a.status == status)
            status_counts[status.value] = count
        
        role_counts = {}
        for role in AgentRole:
            count = sum(1 for a in self._agents.values() if a.role == role)
            role_counts[role.value] = count
        
        total_tasks = sum(a.tasks_completed + a.tasks_failed for a in self._agents.values())
        total_completed = sum(a.tasks_completed for a in self._agents.values())
        
        return {
            "total_agents": total,
            "status_distribution": status_counts,
            "role_distribution": role_counts,
            "total_tasks": total_tasks,
            "total_completed": total_completed,
            "overall_success_rate": (
                total_completed / total_tasks if total_tasks > 0 else 0.0
            ),
        }
    
    def add_event_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add event listener for registry events."""
        self._event_listeners.append(callback)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit event to all listeners."""
        for listener in self._event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                log.error(f"Event listener error: {e}")
    
    async def start_monitoring(self) -> None:
        """Start monitoring agent health."""
        if self._running:
            log.warning("Monitoring already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info("Agent monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring agent health."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        log.info("Agent monitoring stopped")
    
    async def _monitor_loop(self) -> None:
        """Monitor agent health periodically."""
        while self._running:
            try:
                await self._check_health()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Monitor loop error: {e}")
    
    async def _check_health(self) -> None:
        """Check health of all agents."""
        current_time = time.time()
        
        for agent in self._agents.values():
            time_since_heartbeat = current_time - agent.last_heartbeat
            
            # Mark offline if no heartbeat
            if time_since_heartbeat > self._heartbeat_timeout:
                if agent.status != AgentStatus.OFFLINE:
                    log.warning(
                        f"Agent {agent.agent_id} offline "
                        f"(no heartbeat for {time_since_heartbeat:.1f}s)"
                    )
                    agent.status = AgentStatus.OFFLINE
                    self._emit_event(
                        "agent_offline",
                        {
                            "agent_id": agent.agent_id,
                            "time_since_heartbeat": time_since_heartbeat,
                        },
                    )
