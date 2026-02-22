"""
Digital Being - Agent Registry
Stage 27: Discover and register agents in the network.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("digital_being.agent_registry")


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    
    agent_id: str
    name: str
    specialization: str
    host: str
    port: int
    status: str  # "online", "offline", "busy"
    last_heartbeat: float
    capabilities: list[str]
    load: float  # 0.0-1.0, current workload
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> AgentInfo:
        return cls(**data)
    
    def is_alive(self, timeout: float = 300.0) -> bool:  # ✅ FIX: 5 минут вместо 30 сек
        """Check if agent is alive based on heartbeat."""
        return (time.time() - self.last_heartbeat) < timeout


class AgentRegistry:
    """Registry for all agents in the network."""
    
    def __init__(self, registry_file: Path):
        self._registry_file = registry_file
        self._agents: dict[str, AgentInfo] = {}
        self._load()
        log.info("AgentRegistry initialized.")
    
    def register(
        self,
        agent_id: str,
        name: str,
        specialization: str,
        host: str,
        port: int,
        capabilities: list[str] | None = None
    ) -> bool:
        """Register a new agent."""
        if agent_id in self._agents:
            log.warning(f"Agent {agent_id} already registered. Updating.")
        
        agent = AgentInfo(
            agent_id=agent_id,
            name=name,
            specialization=specialization,
            host=host,
            port=port,
            status="online",
            last_heartbeat=time.time(),
            capabilities=capabilities or [],
            load=0.0
        )
        
        self._agents[agent_id] = agent
        self._save()
        log.info(f"Registered agent: {name} ({agent_id}) - {specialization}")
        return True
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id not in self._agents:
            return False
        
        name = self._agents[agent_id].name
        del self._agents[agent_id]
        self._save()
        log.info(f"Unregistered agent: {name} ({agent_id})")
        return True
    
    def heartbeat(self, agent_id: str, load: float = 0.0) -> bool:
        """Update agent heartbeat."""
        if agent_id not in self._agents:
            log.warning(f"Heartbeat from unknown agent: {agent_id}")
            return False
        
        self._agents[agent_id].last_heartbeat = time.time()
        self._agents[agent_id].load = load
        self._agents[agent_id].status = "online"
        return True
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent info by ID."""
        return self._agents.get(agent_id)
    
    def find_by_name(self, name: str) -> Optional[AgentInfo]:
        """Find agent by name."""
        for agent in self._agents.values():
            if agent.name == name:
                return agent
        return None
    
    def find_by_specialization(self, specialization: str) -> list[AgentInfo]:
        """Find all agents with given specialization."""
        return [
            agent for agent in self._agents.values()
            if agent.specialization == specialization and agent.is_alive()
        ]
    
    def get_all_online(self) -> list[AgentInfo]:
        """Get all online agents."""
        return [agent for agent in self._agents.values() if agent.is_alive()]
    
    def get_best_for_task(self, task_type: str) -> Optional[AgentInfo]:
        """Find best agent for a task based on specialization and load."""
        candidates = self.find_by_specialization(task_type)
        if not candidates:
            # Fallback to any online agent
            candidates = self.get_all_online()
        
        if not candidates:
            return None
        
        # Sort by load (ascending)
        candidates.sort(key=lambda a: a.load)
        return candidates[0]
    
    def update_status(self, agent_id: str, status: str) -> bool:
        """Update agent status."""
        if agent_id not in self._agents:
            return False
        self._agents[agent_id].status = status
        self._save()
        return True
    
    def cleanup_stale(self, timeout: float = 600.0) -> int:  # ✅ FIX: 10 минут timeout
        """Remove stale agents that haven't sent heartbeat."""
        stale = [
            agent_id for agent_id, agent in self._agents.items()
            if not agent.is_alive(timeout)
        ]
        
        for agent_id in stale:
            self.unregister(agent_id)
        
        if stale:
            log.info(f"Cleaned up {len(stale)} stale agents")
        
        return len(stale)
    
    def get_stats(self) -> dict:
        """Get registry statistics."""
        online = self.get_all_online()
        return {
            "total_agents": len(self._agents),
            "online_agents": len(online),
            "specializations": list(set(a.specialization for a in self._agents.values())),
            "avg_load": sum(a.load for a in online) / len(online) if online else 0.0
        }
    
    def _load(self):
        """Load registry from file."""
        if not self._registry_file.exists():
            log.info("No registry file found. Starting fresh.")
            return
        
        try:
            data = json.loads(self._registry_file.read_text(encoding="utf-8"))
            current_time = time.time()  # ✅ FIX: Получаем текущее время
            
            for agent_id, agent_data in data.items():
                # ✅ FIX: Обновляем heartbeat при загрузке чтобы агенты были "alive"
                if agent_data.get('status') == 'online':
                    agent_data['last_heartbeat'] = current_time
                
                self._agents[agent_id] = AgentInfo.from_dict(agent_data)
            
            log.info(f"Loaded {len(self._agents)} agents from registry.")
            
            # ✅ FIX: Логируем каждого агента
            for agent_id, agent in self._agents.items():
                log.info(f"  - {agent.name} ({agent.specialization}) - status: {agent.status}")
                
        except Exception as e:
            log.error(f"Failed to load registry: {e}")
    
    def _save(self):
        """Save registry to file."""
        try:
            data = {agent_id: agent.to_dict() for agent_id, agent in self._agents.items()}
            self._registry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to save registry: {e}")
