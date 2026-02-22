"""
Digital Being - Agent Autoscaler
Stage 30: Automatic scaling of agents based on workload.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.agent_registry import AgentRegistry, AgentInfo

log = logging.getLogger("digital_being.autoscaler")


@dataclass
class ScalingPolicy:
    """Policy for autoscaling decisions."""
    
    # Scale-up thresholds
    scale_up_threshold: float = 0.75  # 75% load triggers scale-up
    scale_up_cooldown: float = 300.0  # 5 min cooldown between scale-ups
    min_agents_per_type: int = 1
    max_agents_per_type: int = 5
    
    # Scale-down thresholds
    scale_down_threshold: float = 0.25  # 25% load triggers scale-down
    scale_down_cooldown: float = 600.0  # 10 min cooldown between scale-downs
    
    # Health checks
    unhealthy_threshold: int = 3  # Failed heartbeats before considered unhealthy
    heartbeat_timeout: float = 120.0  # 2 min
    
    def to_dict(self) -> dict:
        return {
            "scale_up_threshold": self.scale_up_threshold,
            "scale_up_cooldown": self.scale_up_cooldown,
            "min_agents_per_type": self.min_agents_per_type,
            "max_agents_per_type": self.max_agents_per_type,
            "scale_down_threshold": self.scale_down_threshold,
            "scale_down_cooldown": self.scale_down_cooldown,
            "unhealthy_threshold": self.unhealthy_threshold,
            "heartbeat_timeout": self.heartbeat_timeout,
        }


@dataclass
class ScalingEvent:
    """Record of a scaling event."""
    
    timestamp: float
    event_type: str  # "scale_up", "scale_down", "replace_unhealthy"
    specialization: str
    reason: str
    agent_id: Optional[str] = None
    load_before: float = 0.0
    load_after: float = 0.0


class AgentAutoscaler:
    """Automatically scale agents based on workload and health."""
    
    def __init__(
        self,
        registry: "AgentRegistry",
        storage_dir: Path,
        policy: Optional[ScalingPolicy] = None
    ):
        self._registry = registry
        self._storage_dir = storage_dir
        self._policy = policy or ScalingPolicy()
        
        # Tracking
        self._last_scale_up: dict[str, float] = {}  # specialization -> timestamp
        self._last_scale_down: dict[str, float] = {}  # specialization -> timestamp
        self._scaling_history: list[ScalingEvent] = []
        self._unhealthy_counts: dict[str, int] = {}  # agent_id -> failed_checks
        
        # Available agent templates
        self._agent_templates = {
            "research": {
                "specialization": "research",
                "port_range": (9101, 9150),
                "capabilities": ["web_search", "data_analysis", "information_gathering"]
            },
            "execution": {
                "specialization": "execution",
                "port_range": (9201, 9250),
                "capabilities": ["python_execute", "file_write", "shell_execute"]
            },
            "analysis": {
                "specialization": "analysis",
                "port_range": (9301, 9350),
                "capabilities": ["data_analysis", "pattern_recognition", "reporting"]
            },
            "planning": {
                "specialization": "planning",
                "port_range": (9401, 9450),
                "capabilities": ["strategic_planning", "goal_setting", "task_breakdown"]
            },
            "testing": {
                "specialization": "testing",
                "port_range": (9501, 9550),
                "capabilities": ["testing", "validation", "quality_assurance"]
            },
        }
        
        log.info(f"AgentAutoscaler initialized with policy: {self._policy.to_dict()}")
    
    def check_and_scale(self) -> dict[str, any]:
        """Check all agents and make scaling decisions."""
        decisions = {
            "scaled_up": [],
            "scaled_down": [],
            "replaced": [],
            "no_action": True
        }
        
        # Get all specializations in use
        specializations = set()
        for agent in self._registry.get_all_online():
            specializations.add(agent.specialization)
        
        # Check each specialization
        for spec in specializations:
            # Check if scale-up needed
            scale_up_decision = self._check_scale_up(spec)
            if scale_up_decision:
                new_agent = self._scale_up(spec, scale_up_decision["reason"])
                if new_agent:
                    decisions["scaled_up"].append(new_agent)
                    decisions["no_action"] = False
            
            # Check if scale-down needed
            scale_down_decision = self._check_scale_down(spec)
            if scale_down_decision:
                removed_agent = self._scale_down(spec, scale_down_decision["reason"])
                if removed_agent:
                    decisions["scaled_down"].append(removed_agent)
                    decisions["no_action"] = False
        
        # Check for unhealthy agents
        unhealthy = self._check_unhealthy_agents()
        for agent_id in unhealthy:
            replaced = self._replace_unhealthy_agent(agent_id)
            if replaced:
                decisions["replaced"].append(replaced)
                decisions["no_action"] = False
        
        return decisions
    
    def _check_scale_up(self, specialization: str) -> Optional[dict]:
        """Check if scale-up is needed for specialization."""
        # Check cooldown
        last_scale = self._last_scale_up.get(specialization, 0)
        if time.time() - last_scale < self._policy.scale_up_cooldown:
            return None
        
        # Get agents of this type
        agents = self._registry.find_by_specialization(specialization)
        if len(agents) >= self._policy.max_agents_per_type:
            return None
        
        # Check average load
        if not agents:
            return None
        
        avg_load = sum(a.load for a in agents) / len(agents)
        
        if avg_load > self._policy.scale_up_threshold:
            return {
                "reason": f"High load: {avg_load:.2f} > {self._policy.scale_up_threshold}",
                "current_agents": len(agents),
                "avg_load": avg_load
            }
        
        return None
    
    def _check_scale_down(self, specialization: str) -> Optional[dict]:
        """Check if scale-down is needed for specialization."""
        # Check cooldown
        last_scale = self._last_scale_down.get(specialization, 0)
        if time.time() - last_scale < self._policy.scale_down_cooldown:
            return None
        
        # Get agents of this type
        agents = self._registry.find_by_specialization(specialization)
        if len(agents) <= self._policy.min_agents_per_type:
            return None
        
        # Check average load
        if not agents:
            return None
        
        avg_load = sum(a.load for a in agents) / len(agents)
        
        if avg_load < self._policy.scale_down_threshold:
            return {
                "reason": f"Low load: {avg_load:.2f} < {self._policy.scale_down_threshold}",
                "current_agents": len(agents),
                "avg_load": avg_load
            }
        
        return None
    
    def _check_unhealthy_agents(self) -> list[str]:
        """Check for unhealthy agents."""
        unhealthy = []
        
        for agent in self._registry._agents.values():
            if not agent.is_alive(self._policy.heartbeat_timeout):
                # Increment unhealthy count
                self._unhealthy_counts[agent.agent_id] = \
                    self._unhealthy_counts.get(agent.agent_id, 0) + 1
                
                if self._unhealthy_counts[agent.agent_id] >= self._policy.unhealthy_threshold:
                    unhealthy.append(agent.agent_id)
            else:
                # Reset unhealthy count
                if agent.agent_id in self._unhealthy_counts:
                    del self._unhealthy_counts[agent.agent_id]
        
        return unhealthy
    
    def _scale_up(self, specialization: str, reason: str) -> Optional[dict]:
        """Create a new agent of given specialization."""
        if specialization not in self._agent_templates:
            log.warning(f"No template for specialization: {specialization}")
            return None
        
        template = self._agent_templates[specialization]
        
        # Find available port
        port = self._find_available_port(template["port_range"])
        if not port:
            log.error(f"No available ports for {specialization}")
            return None
        
        # Create agent ID
        agent_id = f"{specialization}_agent_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Register new agent
        self._registry.register(
            agent_id=agent_id,
            name=f"{specialization}_{len(self._registry.find_by_specialization(specialization)) + 1}",
            specialization=specialization,
            host="localhost",
            port=port,
            capabilities=template["capabilities"]
        )
        
        # Record event
        event = ScalingEvent(
            timestamp=time.time(),
            event_type="scale_up",
            specialization=specialization,
            reason=reason,
            agent_id=agent_id
        )
        self._scaling_history.append(event)
        self._last_scale_up[specialization] = time.time()
        
        log.info(f"✅ Scaled up: {agent_id} ({specialization}) - {reason}")
        
        return {
            "agent_id": agent_id,
            "specialization": specialization,
            "port": port,
            "reason": reason
        }
    
    def _scale_down(self, specialization: str, reason: str) -> Optional[dict]:
        """Remove least-loaded agent of given specialization."""
        agents = self._registry.find_by_specialization(specialization)
        if not agents:
            return None
        
        # Find agent with lowest load
        agent_to_remove = min(agents, key=lambda a: a.load)
        
        # Don't remove primary agents
        if agent_to_remove.name in ["primary", "researcher", "executor", "analyst", "planner", "tester"]:
            log.debug(f"Skipping scale-down of core agent: {agent_to_remove.name}")
            return None
        
        # Unregister
        self._registry.unregister(agent_to_remove.agent_id)
        
        # Record event
        event = ScalingEvent(
            timestamp=time.time(),
            event_type="scale_down",
            specialization=specialization,
            reason=reason,
            agent_id=agent_to_remove.agent_id,
            load_before=agent_to_remove.load
        )
        self._scaling_history.append(event)
        self._last_scale_down[specialization] = time.time()
        
        log.info(f"⬇️ Scaled down: {agent_to_remove.agent_id} ({specialization}) - {reason}")
        
        return {
            "agent_id": agent_to_remove.agent_id,
            "specialization": specialization,
            "reason": reason
        }
    
    def _replace_unhealthy_agent(self, agent_id: str) -> Optional[dict]:
        """Replace an unhealthy agent with a new one."""
        agent = self._registry.get_agent(agent_id)
        if not agent:
            return None
        
        log.warning(f"Replacing unhealthy agent: {agent_id} ({agent.specialization})")
        
        # Don't replace core agents, just mark offline
        if agent.name in ["primary", "researcher", "executor", "analyst", "planner", "tester"]:
            self._registry.update_status(agent_id, "offline")
            log.info(f"Core agent {agent.name} marked offline, not replacing")
            return None
        
        # Create replacement
        new_agent = self._scale_up(
            agent.specialization,
            reason=f"Replacing unhealthy: {agent_id}"
        )
        
        # Remove old agent
        self._registry.unregister(agent_id)
        
        # Record event
        if new_agent:
            event = ScalingEvent(
                timestamp=time.time(),
                event_type="replace_unhealthy",
                specialization=agent.specialization,
                reason=f"Unhealthy: {self._unhealthy_counts.get(agent_id, 0)} failed checks",
                agent_id=new_agent["agent_id"]
            )
            self._scaling_history.append(event)
        
        # Clear unhealthy count
        if agent_id in self._unhealthy_counts:
            del self._unhealthy_counts[agent_id]
        
        return new_agent
    
    def _find_available_port(self, port_range: tuple[int, int]) -> Optional[int]:
        """Find an available port in range."""
        used_ports = {agent.port for agent in self._registry._agents.values()}
        
        for port in range(port_range[0], port_range[1] + 1):
            if port not in used_ports:
                return port
        
        return None
    
    def get_stats(self) -> dict:
        """Get autoscaler statistics."""
        specializations = {}
        
        for agent in self._registry.get_all_online():
            spec = agent.specialization
            if spec not in specializations:
                specializations[spec] = {
                    "count": 0,
                    "total_load": 0.0,
                    "avg_load": 0.0
                }
            
            specializations[spec]["count"] += 1
            specializations[spec]["total_load"] += agent.load
        
        # Calculate averages
        for spec_stats in specializations.values():
            if spec_stats["count"] > 0:
                spec_stats["avg_load"] = spec_stats["total_load"] / spec_stats["count"]
        
        return {
            "policy": self._policy.to_dict(),
            "specializations": specializations,
            "scaling_events": len(self._scaling_history),
            "last_scale_up": {k: time.time() - v for k, v in self._last_scale_up.items()},
            "last_scale_down": {k: time.time() - v for k, v in self._last_scale_down.items()},
            "unhealthy_agents": len(self._unhealthy_counts),
        }
    
    def get_recent_events(self, limit: int = 10) -> list[dict]:
        """Get recent scaling events."""
        recent = self._scaling_history[-limit:]
        return [
            {
                "timestamp": event.timestamp,
                "type": event.event_type,
                "specialization": event.specialization,
                "reason": event.reason,
                "agent_id": event.agent_id
            }
            for event in recent
        ]
