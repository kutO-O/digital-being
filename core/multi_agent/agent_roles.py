"""
Digital Being — Agent Roles System
Stage 28: Specialized agent roles with unique capabilities.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

log = logging.getLogger("digital_being.agent_roles")

class AgentRole(Enum):
    """Predefined agent roles"""
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    ANALYST = "analyst"
    PLANNER = "planner"
    COORDINATOR = "coordinator"
    TESTER = "tester"
    DOCUMENTER = "documenter"
    SPECIALIST = "specialist"  # Generic specialist role

ROLE_DEFINITIONS = {
    AgentRole.RESEARCHER: {
        "name": "Исследователь",
        "description": "Специализируется на поиске и анализе информации",
        "capabilities": ["web_search", "data_analysis", "information_gathering"],
        "preferred_tasks": ["research", "analysis", "investigation"],
        "expertise_domains": ["knowledge", "data", "research"]
    },
    AgentRole.EXECUTOR: {
        "name": "Исполнитель",
        "description": "Выполняет конкретные задачи и команды",
        "capabilities": ["python_execute", "file_write", "shell_execute"],
        "preferred_tasks": ["execution", "implementation", "action"],
        "expertise_domains": ["coding", "automation", "execution"]
    },
    AgentRole.ANALYST: {
        "name": "Аналитик",
        "description": "Анализирует данные и выявляет паттерны",
        "capabilities": ["data_analysis", "pattern_recognition", "reporting"],
        "preferred_tasks": ["analysis", "evaluation", "assessment"],
        "expertise_domains": ["analytics", "patterns", "insights"]
    },
    AgentRole.PLANNER: {
        "name": "Планировщик",
        "description": "Создаёт планы и стратегии",
        "capabilities": ["strategic_planning", "goal_setting", "task_breakdown"],
        "preferred_tasks": ["planning", "strategy", "coordination"],
        "expertise_domains": ["strategy", "planning", "organization"]
    },
    AgentRole.COORDINATOR: {
        "name": "Координатор",
        "description": "Координирует работу других агентов",
        "capabilities": ["task_delegation", "consensus_building", "monitoring"],
        "preferred_tasks": ["coordination", "management", "oversight"],
        "expertise_domains": ["management", "coordination", "communication"]
    },
    AgentRole.TESTER: {
        "name": "Тестировщик",
        "description": "Тестирует код и проверяет качество",
        "capabilities": ["testing", "validation", "quality_assurance"],
        "preferred_tasks": ["testing", "verification", "validation"],
        "expertise_domains": ["testing", "quality", "verification"]
    },
    AgentRole.DOCUMENTER: {
        "name": "Документатор",
        "description": "Создаёт документацию",
        "capabilities": ["documentation", "writing", "knowledge_capture"],
        "preferred_tasks": ["documentation", "writing", "recording"],
        "expertise_domains": ["documentation", "writing", "knowledge"]
    },
    AgentRole.SPECIALIST: {
        "name": "Специалист",
        "description": "Специализируется в конкретной области",
        "capabilities": ["specialized_knowledge", "domain_expertise", "consultation"],
        "preferred_tasks": ["specialized_work", "consultation", "expertise"],
        "expertise_domains": ["specialization", "expertise", "consulting"]
    }
}

class AgentRoleManager:
    """
    Manages agent roles and role-based behavior.
    
    Features:
    - Assign roles to agents
    - Get role-specific capabilities
    - Track role performance
    - Dynamic role switching
    """
    
    def __init__(self, agent_id: str, state_path: Path) -> None:
        self._agent_id = agent_id
        self._state_path = state_path / f"roles_{agent_id}.json"
        
        self._state = {
            "current_role": None,
            "role_history": [],
            "role_performance": {},
            "tasks_by_role": {}
        }
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load role state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info(f"AgentRoleManager: loaded state for {self._agent_id}")
            except Exception as e:
                log.error(f"AgentRoleManager: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save role state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"AgentRoleManager: failed to save state: {e}")
    
    def assign_role(self, role: AgentRole) -> bool:
        """
        Assign a role to the agent.
        
        Args:
            role: AgentRole to assign
        
        Returns:
            True if successful
        """
        try:
            role_value = role.value if isinstance(role, AgentRole) else role
            
            # Record role change
            if self._state["current_role"]:
                self._state["role_history"].append({
                    "from": self._state["current_role"],
                    "to": role_value,
                    "timestamp": None  # Would use time.time() in production
                })
            
            self._state["current_role"] = role_value
            
            # Initialize performance tracking
            if role_value not in self._state["role_performance"]:
                self._state["role_performance"][role_value] = {
                    "tasks_completed": 0,
                    "success_rate": 0.0,
                    "avg_quality": 0.0
                }
            
            self._save_state()
            
            log.info(f"AgentRoleManager: assigned role {role_value} to {self._agent_id}")
            
            return True
        except Exception as e:
            log.error(f"AgentRoleManager: failed to assign role: {e}")
            return False
    
    def get_current_role(self) -> dict | None:
        """Get current role information"""
        if not self._state["current_role"]:
            return None
        
        role_key = AgentRole(self._state["current_role"])
        return ROLE_DEFINITIONS.get(role_key)
    
    def get_capabilities(self) -> list[str]:
        """Get capabilities for current role"""
        role_info = self.get_current_role()
        return role_info["capabilities"] if role_info else []
    
    def get_preferred_tasks(self) -> list[str]:
        """Get preferred task types for current role"""
        role_info = self.get_current_role()
        return role_info["preferred_tasks"] if role_info else []
    
    def is_suitable_for_task(self, task_type: str) -> bool:
        """
        Check if current role is suitable for task type.
        
        Args:
            task_type: Type of task
        
        Returns:
            True if suitable
        """
        preferred = self.get_preferred_tasks()
        return task_type in preferred
    
    def record_task_completion(self, task_type: str, success: bool, quality: float = 0.0) -> None:
        """
        Record task completion for role performance.
        
        Args:
            task_type: Type of task
            success: Whether task was successful
            quality: Quality score (0-1)
        """
        role = self._state["current_role"]
        if not role:
            return
        
        # Update performance
        perf = self._state["role_performance"][role]
        perf["tasks_completed"] += 1
        
        # Update success rate
        total = perf["tasks_completed"]
        current_successes = perf["success_rate"] * (total - 1)
        new_successes = current_successes + (1 if success else 0)
        perf["success_rate"] = new_successes / total
        
        # Update average quality
        current_quality = perf["avg_quality"] * (total - 1)
        perf["avg_quality"] = (current_quality + quality) / total
        
        # Track tasks by role
        if role not in self._state["tasks_by_role"]:
            self._state["tasks_by_role"][role] = []
        
        self._state["tasks_by_role"][role].append({
            "type": task_type,
            "success": success,
            "quality": quality
        })
        
        self._save_state()
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics for current role"""
        role = self._state["current_role"]
        if not role:
            return {}
        
        return self._state["role_performance"].get(role, {})
    
    def get_all_stats(self) -> dict:
        """Get all role statistics"""
        return {
            "current_role": self._state["current_role"],
            "role_changes": len(self._state["role_history"]),
            "roles_used": list(self._state["role_performance"].keys()),
            "performance": self._state["role_performance"]
        }
