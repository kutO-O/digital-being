"""
Digital Being — Task Delegation System
Stage 28: Agents can delegate tasks to each other based on capabilities.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.multi_agent.message_broker import MessageBroker

log = logging.getLogger("digital_being.task_delegation")

class TaskDelegation:
    """
    Manages task delegation between agents.
    
    Features:
    - Task creation with requirements
    - Capability-based assignment
    - Status tracking
    - Performance metrics
    """
    
    def __init__(self, agent_id: str, message_broker: MessageBroker, state_path: Path) -> None:
        self._agent_id = agent_id
        self._broker = message_broker
        self._state_path = state_path / f"task_delegation_{agent_id}.json"
        
        self._state = {
            "tasks_created": [],
            "tasks_received": [],
            "tasks_completed": 0,
            "tasks_delegated": 0,
            "delegation_success_rate": 0.0,
        }
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load task delegation state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info(f"TaskDelegation: loaded state for {self._agent_id}")
            except Exception as e:
                log.error(f"TaskDelegation: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save task delegation state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"TaskDelegation: failed to save state: {e}")
    
    def create_task(
        self,
        title: str,
        description: str,
        required_capabilities: list[str],
        priority: str = "medium",
        deadline: float | None = None
    ) -> dict:
        """
        Create a new task for delegation.
        
        Args:
            title: Task title
            description: Task description
            required_capabilities: Required agent capabilities
            priority: Task priority (low, medium, high, critical)
            deadline: Optional deadline timestamp
        
        Returns:
            Task dict
        """
        task = {
            "id": f"task_{int(time.time() * 1000)}",
            "creator": self._agent_id,
            "title": title,
            "description": description,
            "required_capabilities": required_capabilities,
            "priority": priority,
            "status": "pending",
            "created_at": time.time(),
            "deadline": deadline,
            "assigned_to": None,
            "completed_at": None,
        }
        
        self._state["tasks_created"].append(task)
        self._state["tasks_delegated"] += 1
        self._save_state()
        
        log.info(f"TaskDelegation: created task '{title}' with priority {priority}")
        
        return task
    
    def delegate_task(self, task: dict, target_agent: str) -> bool:
        """
        Delegate task to specific agent.
        
        Args:
            task: Task dict
            target_agent: Target agent ID
        
        Returns:
            True if delegation successful
        """
        try:
            # Send task delegation message
            message = {
                "type": "task_delegation",
                "task": task,
                "from": self._agent_id,
                "priority": task["priority"]
            }
            
            self._broker.send_message(target_agent, message)
            
            # Update task status
            task["status"] = "delegated"
            task["assigned_to"] = target_agent
            task["delegated_at"] = time.time()
            
            self._save_state()
            
            log.info(f"TaskDelegation: delegated task '{task['title']}' to {target_agent}")
            
            return True
        except Exception as e:
            log.error(f"TaskDelegation: failed to delegate task: {e}")
            return False
    
    def accept_task(self, task: dict) -> bool:
        """
        Accept a delegated task.
        
        Args:
            task: Task dict
        
        Returns:
            True if accepted
        """
        try:
            task["status"] = "accepted"
            task["accepted_at"] = time.time()
            
            self._state["tasks_received"].append(task)
            self._save_state()
            
            # Notify creator
            self._broker.send_message(
                task["creator"],
                {
                    "type": "task_accepted",
                    "task_id": task["id"],
                    "agent": self._agent_id
                }
            )
            
            log.info(f"TaskDelegation: accepted task '{task['title']}'")
            
            return True
        except Exception as e:
            log.error(f"TaskDelegation: failed to accept task: {e}")
            return False
    
    def complete_task(self, task_id: str, result: dict) -> bool:
        """
        Mark task as completed.
        
        Args:
            task_id: Task ID
            result: Task result data
        
        Returns:
            True if marked complete
        """
        try:
            # Find task in received list
            task = None
            for t in self._state["tasks_received"]:
                if t["id"] == task_id:
                    task = t
                    break
            
            if not task:
                log.warning(f"TaskDelegation: task {task_id} not found")
                return False
            
            task["status"] = "completed"
            task["completed_at"] = time.time()
            task["result"] = result
            
            self._state["tasks_completed"] += 1
            self._save_state()
            
            # Notify creator
            self._broker.send_message(
                task["creator"],
                {
                    "type": "task_completed",
                    "task_id": task_id,
                    "agent": self._agent_id,
                    "result": result
                }
            )
            
            log.info(f"TaskDelegation: completed task '{task['title']}'")
            
            return True
        except Exception as e:
            log.error(f"TaskDelegation: failed to complete task: {e}")
            return False
    
    def get_pending_tasks(self) -> list[dict]:
        """Get list of pending tasks"""
        return [t for t in self._state["tasks_received"] if t["status"] == "accepted"]
    
    def get_stats(self) -> dict:
        """Get task delegation statistics"""
        total_created = len(self._state["tasks_created"])
        total_received = len(self._state["tasks_received"])
        completed_created = len([t for t in self._state["tasks_created"] if t["status"] == "completed"])
        
        success_rate = 0.0
        if total_created > 0:
            success_rate = completed_created / total_created
        
        return {
            "tasks_created": total_created,
            "tasks_received": total_received,
            "tasks_completed": self._state["tasks_completed"],
            "tasks_delegated": self._state["tasks_delegated"],
            "delegation_success_rate": success_rate,
            "pending_tasks": len(self.get_pending_tasks())
        }
