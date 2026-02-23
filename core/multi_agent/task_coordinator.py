"""Task Coordinator for Multi-Agent System.

Manages task distribution and execution across multiple agents:
- Task creation and lifecycle
- Intelligent agent selection
- Priority queue management
- Dependency handling
- Progress tracking

Phase 3 - Multi-Agent System
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .agent_registry import AgentInfo, AgentRegistry, AgentRole, AgentStatus

log = logging.getLogger("digital_being.multi_agent.coordinator")


class TaskStatus(Enum):
    """Task lifecycle status."""
    PENDING = "pending"          # Waiting to be assigned
    ASSIGNED = "assigned"        # Assigned to an agent
    IN_PROGRESS = "in_progress"  # Being executed
    COMPLETED = "completed"      # Successfully finished
    FAILED = "failed"            # Execution failed
    CANCELLED = "cancelled"      # Manually cancelled
    RETRY = "retry"              # Waiting for retry


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3
    CRITICAL = 4


@dataclass
class Task:
    """Represents a task to be executed by an agent."""
    task_id: str
    name: str
    description: str
    required_capability: Optional[str] = None
    preferred_role: Optional[AgentRole] = None
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Execution
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Task IDs
    blocks: List[str] = field(default_factory=list)      # Task IDs blocked by this
    
    # Timing
    created_at: float = field(default_factory=time.time)
    assigned_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Retry logic
    max_retries: int = 3
    retry_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "required_capability": self.required_capability,
            "preferred_role": self.preferred_role.value if self.preferred_role else None,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_agent_id": self.assigned_agent_id,
            "result": self.result,
            "error": self.error,
            "depends_on": self.depends_on,
            "timing": {
                "created_at": self.created_at,
                "assigned_at": self.assigned_at,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "duration": self._calculate_duration(),
            },
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }
    
    def _calculate_duration(self) -> Optional[float]:
        """Calculate task execution duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class TaskCoordinator:
    """
    Coordinates task distribution across multiple agents.
    
    Features:
    - Intelligent agent selection based on capabilities
    - Priority-based task queue
    - Dependency management
    - Automatic retry on failure
    - Progress tracking
    
    Example:
        coordinator = TaskCoordinator(agent_registry)
        
        # Create task
        task = Task(
            task_id=str(uuid.uuid4()),
            name="Research topic",
            description="Research AI safety",
            preferred_role=AgentRole.RESEARCHER,
            priority=TaskPriority.HIGH
        )
        
        # Add and process
        coordinator.add_task(task)
        await coordinator.process_tasks()
    """
    
    def __init__(self, agent_registry: AgentRegistry):
        """
        Args:
            agent_registry: Registry of available agents
        """
        self._registry = agent_registry
        self._tasks: Dict[str, Task] = {}
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running = False
        self._process_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_task_complete: List[Callable[[Task], None]] = []
        self._on_task_failed: List[Callable[[Task], None]] = []
        
        log.info("TaskCoordinator initialized")
    
    def add_task(self, task: Task) -> None:
        """Add a new task to the queue."""
        # Validate dependencies exist
        for dep_id in task.depends_on:
            if dep_id not in self._tasks:
                log.warning(
                    f"Task {task.task_id} depends on unknown task {dep_id}"
                )
        
        self._tasks[task.task_id] = task
        
        # Add to priority queue (negative priority for correct ordering)
        self._task_queue.put_nowait((-task.priority.value, task.task_id))
        
        log.info(
            f"Task added: {task.task_id} (name={task.name}, "
            f"priority={task.priority.value})"
        )
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or assigned task."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            log.warning(f"Cannot cancel task {task_id} in status {task.status.value}")
            return False
        
        task.status = TaskStatus.CANCELLED
        log.info(f"Task cancelled: {task_id}")
        return True
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks."""
        return [
            task for task in self._tasks.values()
            if task.status == TaskStatus.PENDING
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get task statistics."""
        total = len(self._tasks)
        
        status_counts = {}
        for status in TaskStatus:
            count = sum(1 for t in self._tasks.values() if t.status == status)
            status_counts[status.value] = count
        
        completed = status_counts.get(TaskStatus.COMPLETED.value, 0)
        failed = status_counts.get(TaskStatus.FAILED.value, 0)
        
        return {
            "total_tasks": total,
            "status_distribution": status_counts,
            "completion_rate": completed / total if total > 0 else 0.0,
            "failure_rate": failed / total if total > 0 else 0.0,
        }
    
    def _find_best_agent(self, task: Task) -> Optional[AgentInfo]:
        """Find the best agent for a task."""
        # Get available agents
        available = self._registry.find_available(role=task.preferred_role)
        
        if not available:
            log.debug(f"No available agents for task {task.task_id}")
            return None
        
        # Filter by capability if required
        if task.required_capability:
            candidates = self._registry.find_by_capability(
                task.required_capability, min_skill=0.5
            )
            available = [a for a in available if a in candidates]
        
        if not available:
            log.debug(
                f"No agents with required capability '{task.required_capability}'"
            )
            return None
        
        # Score agents
        def score_agent(agent: AgentInfo) -> float:
            score = 0.0
            
            # Prefer idle agents
            if agent.status == AgentStatus.IDLE:
                score += 2.0
            
            # Success rate
            success_rate = agent._calculate_success_rate()
            score += success_rate * 3.0
            
            # Health
            score += agent.health_score * 2.0
            
            # Capability match
            if task.required_capability:
                for cap in agent.capabilities:
                    if cap.name == task.required_capability:
                        score += cap.skill_level * 5.0
                        break
            
            # Role match
            if task.preferred_role and agent.role == task.preferred_role:
                score += 3.0
            
            return score
        
        # Return best agent
        best_agent = max(available, key=score_agent)
        log.debug(
            f"Selected agent {best_agent.agent_id} for task {task.task_id} "
            f"(score={score_agent(best_agent):.2f})"
        )
        return best_agent
    
    def _check_dependencies(self, task: Task) -> bool:
        """Check if all task dependencies are satisfied."""
        for dep_id in task.depends_on:
            dep_task = self._tasks.get(dep_id)
            if not dep_task:
                log.warning(f"Dependency {dep_id} not found for task {task.task_id}")
                return False
            
            if dep_task.status != TaskStatus.COMPLETED:
                log.debug(
                    f"Task {task.task_id} waiting for dependency {dep_id} "
                    f"(status: {dep_task.status.value})"
                )
                return False
        
        return True
    
    async def _assign_task(self, task: Task, agent: AgentInfo) -> None:
        """Assign task to agent."""
        task.status = TaskStatus.ASSIGNED
        task.assigned_agent_id = agent.agent_id
        task.assigned_at = time.time()
        
        # Update agent status
        self._registry.update_status(agent.agent_id, AgentStatus.BUSY)
        
        log.info(
            f"Task {task.task_id} assigned to agent {agent.agent_id} "
            f"(name={agent.name})"
        )
    
    async def _execute_task(self, task: Task, agent: AgentInfo) -> None:
        """Execute task (placeholder - override or extend)."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()
        
        try:
            # Simulate task execution
            await asyncio.sleep(0.1)
            
            # Mark complete
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = {"success": True}
            
            # Update agent metrics
            agent.tasks_completed += 1
            
            # Update agent status back to idle
            self._registry.update_status(agent.agent_id, AgentStatus.IDLE)
            
            log.info(f"Task {task.task_id} completed by agent {agent.agent_id}")
            
            # Trigger callbacks
            for callback in self._on_task_complete:
                try:
                    callback(task)
                except Exception as e:
                    log.error(f"Task complete callback error: {e}")
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            
            # Update agent metrics
            agent.tasks_failed += 1
            
            # Update agent status
            self._registry.update_status(agent.agent_id, AgentStatus.IDLE)
            
            log.error(f"Task {task.task_id} failed: {e}")
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRY
                self._task_queue.put_nowait((-task.priority.value, task.task_id))
                log.info(
                    f"Task {task.task_id} will retry "
                    f"(attempt {task.retry_count}/{task.max_retries})"
                )
            else:
                # Trigger failure callbacks
                for callback in self._on_task_failed:
                    try:
                        callback(task)
                    except Exception as e:
                        log.error(f"Task failed callback error: {e}")
    
    async def start(self) -> None:
        """Start processing tasks."""
        if self._running:
            log.warning("TaskCoordinator already running")
            return
        
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        log.info("TaskCoordinator started")
    
    async def stop(self) -> None:
        """Stop processing tasks."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        log.info("TaskCoordinator stopped")
    
    async def _process_loop(self) -> None:
        """Main task processing loop."""
        while self._running:
            try:
                # Get next task from queue (with timeout)
                try:
                    _, task_id = await asyncio.wait_for(
                        self._task_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                task = self._tasks.get(task_id)
                if not task:
                    log.warning(f"Task {task_id} not found in registry")
                    continue
                
                # Skip if not pending/retry
                if task.status not in (TaskStatus.PENDING, TaskStatus.RETRY):
                    continue
                
                # Check dependencies
                if not self._check_dependencies(task):
                    # Re-queue for later
                    await asyncio.sleep(1.0)
                    self._task_queue.put_nowait((-task.priority.value, task_id))
                    continue
                
                # Find agent
                agent = self._find_best_agent(task)
                if not agent:
                    # Re-queue for later
                    await asyncio.sleep(2.0)
                    self._task_queue.put_nowait((-task.priority.value, task_id))
                    continue
                
                # Assign and execute
                await self._assign_task(task, agent)
                await self._execute_task(task, agent)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Process loop error: {e}")
                await asyncio.sleep(1.0)
    
    def on_task_complete(self, callback: Callable[[Task], None]) -> None:
        """Register callback for task completion."""
        self._on_task_complete.append(callback)
    
    def on_task_failed(self, callback: Callable[[Task], None]) -> None:
        """Register callback for task failure."""
        self._on_task_failed.append(callback)
