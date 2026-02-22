"""
Digital Being — Advanced Multi-Agent System
Stage 28: Task delegation, specialization, consensus building

This module extends Stage 27's multi-agent capabilities with:
- Task delegation and distribution
- Agent specialization and roles
- Consensus building for decisions
- Advanced skill sharing
- Conflict resolution protocols
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.multi_agent_coordinator import MultiAgentCoordinator
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.advanced_multi_agent")


class AgentRole(Enum):
    """Agent specialization roles"""
    RESEARCHER = "researcher"  # Searches, analyzes, gathers info
    EXECUTOR = "executor"      # Executes tasks, runs code
    ANALYST = "analyst"        # Analyzes results, provides insights
    COORDINATOR = "coordinator" # Coordinates other agents
    CRITIC = "critic"          # Reviews and critiques work
    CREATIVE = "creative"      # Generates ideas and solutions


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Task:
    """Represents a delegatable task"""
    id: str
    description: str
    priority: TaskPriority
    required_role: AgentRole | None = None
    assigned_to: str | None = None
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Any = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    dependencies: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority.value,
            "required_role": self.required_role.value if self.required_role else None,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "dependencies": self.dependencies
        }


@dataclass
class Vote:
    """Represents a vote in consensus building"""
    agent_id: str
    proposal_id: str
    vote: bool  # True = approve, False = reject
    reasoning: str
    timestamp: float = field(default_factory=time.time)


class AdvancedMultiAgent:
    """
    Advanced multi-agent coordination system.
    
    Features:
    - Task delegation and assignment
    - Agent specialization
    - Consensus-based decision making
    - Skill sharing protocols
    - Conflict resolution
    """
    
    def __init__(
        self,
        multi_agent: MultiAgentCoordinator,
        memory: EpisodicMemory,
        memory_dir: Path
    ):
        self._multi_agent = multi_agent
        self._memory = memory
        self._state_file = memory_dir / "advanced_multi_agent.json"
        
        # Task management
        self._tasks: dict[str, Task] = {}
        self._task_counter = 0
        
        # Agent roles and specializations
        self._agent_roles: dict[str, AgentRole] = {}
        
        # Consensus mechanism
        self._proposals: dict[str, dict] = {}
        self._votes: dict[str, list[Vote]] = {}
        
        # Conflict resolution
        self._conflicts: list[dict] = []
        
        # Statistics
        self._stats = {
            "tasks_delegated": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "consensus_reached": 0,
            "conflicts_resolved": 0
        }
        
        self._load_state()
        log.info("AdvancedMultiAgent initialized")
    
    def _load_state(self) -> None:
        """Load state from disk"""
        if not self._state_file.exists():
            return
        
        try:
            with self._state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._agent_roles = {
                k: AgentRole(v) for k, v in data.get("agent_roles", {}).items()
            }
            self._stats = data.get("stats", self._stats)
            self._task_counter = data.get("task_counter", 0)
            
            log.info(f"AdvancedMultiAgent: loaded state. roles={len(self._agent_roles)}")
        except Exception as e:
            log.error(f"Failed to load AdvancedMultiAgent state: {e}")
    
    def _save_state(self) -> None:
        """Save state to disk"""
        try:
            data = {
                "agent_roles": {k: v.value for k, v in self._agent_roles.items()},
                "stats": self._stats,
                "task_counter": self._task_counter
            }
            
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with self._state_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to save AdvancedMultiAgent state: {e}")
    
    def assign_role(self, agent_id: str, role: AgentRole) -> None:
        """Assign a specialization role to an agent"""
        self._agent_roles[agent_id] = role
        self._save_state()
        
        self._memory.add_episode(
            event_type="agent.role_assigned",
            data={
                "agent_id": agent_id,
                "role": role.value
            },
            importance=0.6
        )
        
        log.info(f"Assigned role {role.value} to agent {agent_id}")
    
    def create_task(
        self,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        required_role: AgentRole | None = None,
        dependencies: list[str] | None = None
    ) -> Task:
        """Create a new task for delegation"""
        self._task_counter += 1
        task_id = f"task_{self._task_counter}_{int(time.time())}"
        
        task = Task(
            id=task_id,
            description=description,
            priority=priority,
            required_role=required_role,
            dependencies=dependencies or []
        )
        
        self._tasks[task_id] = task
        self._stats["tasks_delegated"] += 1
        self._save_state()
        
        log.info(f"Created task {task_id}: {description[:50]}...")
        return task
    
    def delegate_task(self, task: Task) -> str | None:
        """Delegate task to appropriate agent based on role and availability"""
        # Check dependencies
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if not dep or dep.status != "completed":
                log.info(f"Task {task.id} waiting for dependency {dep_id}")
                return None
        
        # Find suitable agent
        candidates = []
        online_agents = self._multi_agent.get_online_agents()
        
        for agent in online_agents:
            agent_id = agent["agent_id"]
            agent_role = self._agent_roles.get(agent_id)
            
            # Check role match
            if task.required_role and agent_role != task.required_role:
                continue
            
            # Check if agent is busy
            busy = any(
                t.assigned_to == agent_id and t.status == "in_progress"
                for t in self._tasks.values()
            )
            if busy:
                continue
            
            candidates.append(agent_id)
        
        if not candidates:
            log.info(f"No suitable agent found for task {task.id}")
            return None
        
        # Assign to first available candidate
        assigned_agent = candidates[0]
        task.assigned_to = assigned_agent
        task.status = "in_progress"
        task.started_at = time.time()
        
        # Send task to agent via message broker
        self._multi_agent.send_message(
            to_agent_id=assigned_agent,
            message_type="task_assignment",
            content={
                "task_id": task.id,
                "description": task.description,
                "priority": task.priority.value
            }
        )
        
        self._memory.add_episode(
            event_type="task.delegated",
            data={
                "task_id": task.id,
                "assigned_to": assigned_agent,
                "description": task.description
            },
            importance=0.7
        )
        
        log.info(f"Delegated task {task.id} to agent {assigned_agent}")
        return assigned_agent
    
    def complete_task(self, task_id: str, result: Any, success: bool = True) -> None:
        """Mark task as completed with result"""
        task = self._tasks.get(task_id)
        if not task:
            return
        
        task.status = "completed" if success else "failed"
        task.result = result
        task.completed_at = time.time()
        
        if success:
            self._stats["tasks_completed"] += 1
        else:
            self._stats["tasks_failed"] += 1
        
        self._save_state()
        
        self._memory.add_episode(
            event_type="task.completed" if success else "task.failed",
            data={
                "task_id": task_id,
                "result": result,
                "duration": task.completed_at - (task.started_at or task.created_at)
            },
            importance=0.8 if success else 0.6
        )
        
        log.info(f"Task {task_id} {'completed' if success else 'failed'}")
    
    def create_proposal(self, proposal_id: str, description: str, data: dict) -> None:
        """Create a proposal for consensus building"""
        self._proposals[proposal_id] = {
            "id": proposal_id,
            "description": description,
            "data": data,
            "created_at": time.time(),
            "status": "voting"
        }
        self._votes[proposal_id] = []
        
        # Broadcast to all agents
        online_agents = self._multi_agent.get_online_agents()
        for agent in online_agents:
            self._multi_agent.send_message(
                to_agent_id=agent["agent_id"],
                message_type="proposal",
                content={
                    "proposal_id": proposal_id,
                    "description": description,
                    "data": data
                }
            )
        
        log.info(f"Created proposal {proposal_id}: {description}")
    
    def vote_on_proposal(
        self,
        proposal_id: str,
        agent_id: str,
        approve: bool,
        reasoning: str
    ) -> None:
        """Agent votes on a proposal"""
        if proposal_id not in self._proposals:
            return
        
        vote = Vote(
            agent_id=agent_id,
            proposal_id=proposal_id,
            vote=approve,
            reasoning=reasoning
        )
        
        self._votes[proposal_id].append(vote)
        log.info(f"Agent {agent_id} voted {approve} on proposal {proposal_id}")
    
    def check_consensus(self, proposal_id: str, threshold: float = 0.66) -> bool | None:
        """
        Check if consensus is reached on a proposal.
        
        Returns:
            True if approved, False if rejected, None if still voting
        """
        if proposal_id not in self._proposals:
            return None
        
        votes = self._votes.get(proposal_id, [])
        online_agents = self._multi_agent.get_online_agents()
        
        # Wait for all agents to vote
        if len(votes) < len(online_agents):
            return None
        
        # Calculate approval rate
        approvals = sum(1 for v in votes if v.vote)
        approval_rate = approvals / len(votes) if votes else 0
        
        # Determine outcome
        approved = approval_rate >= threshold
        
        self._proposals[proposal_id]["status"] = "approved" if approved else "rejected"
        self._proposals[proposal_id]["approval_rate"] = approval_rate
        
        if approved:
            self._stats["consensus_reached"] += 1
        
        self._memory.add_episode(
            event_type="consensus.reached",
            data={
                "proposal_id": proposal_id,
                "approved": approved,
                "approval_rate": approval_rate,
                "votes": len(votes)
            },
            importance=0.9
        )
        
        log.info(f"Consensus on {proposal_id}: {'APPROVED' if approved else 'REJECTED'} ({approval_rate:.1%})")
        return approved
    
    def detect_conflict(self, agent1_id: str, agent2_id: str, issue: str) -> str:
        """Detect and log a conflict between agents"""
        conflict = {
            "id": f"conflict_{int(time.time())}",
            "agent1": agent1_id,
            "agent2": agent2_id,
            "issue": issue,
            "timestamp": time.time(),
            "status": "pending"
        }
        
        self._conflicts.append(conflict)
        
        self._memory.add_episode(
            event_type="conflict.detected",
            data=conflict,
            importance=0.8
        )
        
        log.warning(f"Conflict detected between {agent1_id} and {agent2_id}: {issue}")
        return conflict["id"]
    
    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        mediator: str | None = None
    ) -> None:
        """Resolve a conflict"""
        for conflict in self._conflicts:
            if conflict["id"] == conflict_id:
                conflict["status"] = "resolved"
                conflict["resolution"] = resolution
                conflict["mediator"] = mediator
                conflict["resolved_at"] = time.time()
                
                self._stats["conflicts_resolved"] += 1
                
                self._memory.add_episode(
                    event_type="conflict.resolved",
                    data=conflict,
                    importance=0.9
                )
                
                log.info(f"Conflict {conflict_id} resolved: {resolution}")
                break
    
    def get_stats(self) -> dict:
        """Get system statistics"""
        return {
            **self._stats,
            "active_tasks": sum(1 for t in self._tasks.values() if t.status == "in_progress"),
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == "pending"),
            "agent_roles": {k: v.value for k, v in self._agent_roles.items()},
            "active_proposals": sum(1 for p in self._proposals.values() if p["status"] == "voting"),
            "pending_conflicts": sum(1 for c in self._conflicts if c["status"] == "pending")
        }
    
    def get_tasks(self, status: str | None = None) -> list[dict]:
        """Get tasks, optionally filtered by status"""
        tasks = self._tasks.values()
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]
