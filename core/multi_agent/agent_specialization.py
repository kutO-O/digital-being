"""Agent Specialization System.

Enables agents to learn and improve skills through experience:
- Skill learning from task execution
- Expertise tracking
- Role evolution
- Performance profiling
- Learning curves

Phase 3 - Multi-Agent System
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .agent_registry import AgentCapability, AgentInfo, AgentRole

log = logging.getLogger("digital_being.multi_agent.specialization")


@dataclass
class SkillExperience:
    """Tracks experience for a specific skill."""
    capability_name: str
    
    # Experience metrics
    tasks_attempted: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    total_time_spent: float = 0.0  # seconds
    
    # Learning
    initial_skill: float = 0.1
    current_skill: float = 0.1
    learning_rate: float = 0.05  # How fast to learn
    
    # Performance
    average_quality: float = 0.0  # 0.0 to 1.0
    best_performance: float = 0.0
    worst_performance: float = 1.0
    
    # Timestamps
    first_attempt: float = field(default_factory=time.time)
    last_attempt: float = field(default_factory=time.time)
    last_success: Optional[float] = None
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.tasks_attempted
        if total == 0:
            return 0.0
        return self.tasks_succeeded / total
    
    def average_time(self) -> float:
        """Calculate average time per task."""
        if self.tasks_attempted == 0:
            return 0.0
        return self.total_time_spent / self.tasks_attempted
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "capability_name": self.capability_name,
            "current_skill": self.current_skill,
            "tasks_attempted": self.tasks_attempted,
            "tasks_succeeded": self.tasks_succeeded,
            "success_rate": self.success_rate(),
            "average_quality": self.average_quality,
            "average_time": self.average_time(),
            "learning_progress": self.current_skill - self.initial_skill,
        }


@dataclass
class PerformanceProfile:
    """Performance profile for an agent."""
    agent_id: str
    
    # Skills
    skills: Dict[str, SkillExperience] = field(default_factory=dict)
    
    # Role progression
    current_role: AgentRole = AgentRole.GENERALIST
    role_history: List[tuple[AgentRole, float]] = field(default_factory=list)
    
    # Overall stats
    total_tasks: int = 0
    total_learning_time: float = 0.0  # Time spent learning
    
    # Configuration
    skill_decay_rate: float = 0.001  # Skill decay per day
    max_skill_level: float = 1.0
    min_skill_level: float = 0.1
    
    def get_skill(self, capability: str) -> Optional[SkillExperience]:
        """Get skill experience for capability."""
        return self.skills.get(capability)
    
    def get_skill_level(self, capability: str) -> float:
        """Get current skill level."""
        skill = self.skills.get(capability)
        return skill.current_skill if skill else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "current_role": self.current_role.value,
            "total_tasks": self.total_tasks,
            "skills": {
                name: exp.to_dict()
                for name, exp in self.skills.items()
            },
            "top_skills": self._get_top_skills(3),
        }
    
    def _get_top_skills(self, n: int) -> List[Dict[str, Any]]:
        """Get top N skills by level."""
        sorted_skills = sorted(
            self.skills.items(),
            key=lambda x: x[1].current_skill,
            reverse=True
        )
        return [
            {"name": name, "level": exp.current_skill}
            for name, exp in sorted_skills[:n]
        ]


class AgentSpecialization:
    """
    Manages agent skill learning and specialization.
    
    Features:
    - Track skill development over time
    - Learn from task execution
    - Dynamic skill level updates
    - Role evolution based on expertise
    - Performance profiling
    
    Example:
        specialization = AgentSpecialization()
        
        # Record task execution
        specialization.record_task(
            agent_id="agent_1",
            capability="web_search",
            success=True,
            duration=2.5,
            quality=0.9
        )
        
        # Get updated skill
        skill_level = specialization.get_skill_level("agent_1", "web_search")
        
        # Check for role evolution
        new_role = specialization.suggest_role("agent_1")
    """
    
    def __init__(
        self,
        learning_rate: float = 0.05,
        quality_weight: float = 0.7,
        speed_weight: float = 0.3
    ):
        """
        Args:
            learning_rate: Base learning rate (0.0-1.0)
            quality_weight: Weight for quality in learning
            speed_weight: Weight for speed in learning
        """
        self._learning_rate = learning_rate
        self._quality_weight = quality_weight
        self._speed_weight = speed_weight
        
        # Agent profiles
        self._profiles: Dict[str, PerformanceProfile] = {}
        
        log.info(
            f"AgentSpecialization initialized (learning_rate={learning_rate})"
        )
    
    def get_or_create_profile(self, agent_id: str) -> PerformanceProfile:
        """Get or create performance profile for agent."""
        if agent_id not in self._profiles:
            self._profiles[agent_id] = PerformanceProfile(agent_id=agent_id)
        return self._profiles[agent_id]
    
    def record_task(
        self,
        agent_id: str,
        capability: str,
        success: bool,
        duration: float,
        quality: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record task execution for learning."""
        profile = self.get_or_create_profile(agent_id)
        
        # Get or create skill experience
        if capability not in profile.skills:
            profile.skills[capability] = SkillExperience(
                capability_name=capability,
                learning_rate=self._learning_rate
            )
        
        skill = profile.skills[capability]
        
        # Update attempts
        skill.tasks_attempted += 1
        profile.total_tasks += 1
        
        if success:
            skill.tasks_succeeded += 1
            skill.last_success = time.time()
        else:
            skill.tasks_failed += 1
        
        # Update timing
        skill.total_time_spent += duration
        skill.last_attempt = time.time()
        
        # Update quality metrics
        if success:
            # Update average quality (moving average)
            alpha = 0.2  # Weight for new observation
            skill.average_quality = (
                alpha * quality + (1 - alpha) * skill.average_quality
            )
            
            skill.best_performance = max(skill.best_performance, quality)
            skill.worst_performance = min(skill.worst_performance, quality)
        
        # Learn from experience
        self._update_skill_level(skill, success, quality, duration)
        
        log.debug(
            f"Task recorded for {agent_id}/{capability}: "
            f"success={success}, quality={quality:.2f}, "
            f"new_skill={skill.current_skill:.3f}"
        )
    
    def _update_skill_level(
        self,
        skill: SkillExperience,
        success: bool,
        quality: float,
        duration: float
    ) -> None:
        """Update skill level based on task outcome."""
        # Calculate performance score
        performance_score = 0.0
        
        if success:
            # Combine quality and speed
            # Speed score: faster = better (normalized)
            expected_time = skill.average_time() or 10.0
            speed_score = min(1.0, expected_time / max(0.1, duration))
            
            performance_score = (
                self._quality_weight * quality +
                self._speed_weight * speed_score
            )
        else:
            # Failure gives negative performance
            performance_score = -0.2
        
        # Learning curve: diminishing returns as skill increases
        # Use sigmoid-like function
        current_skill = skill.current_skill
        learning_potential = 1.0 - current_skill  # Less to learn at high skill
        
        # Calculate skill change
        delta = skill.learning_rate * learning_potential * performance_score
        
        # Apply change with bounds
        new_skill = current_skill + delta
        skill.current_skill = max(
            0.1,  # Min skill
            min(1.0, new_skill)  # Max skill
        )
        
        log.debug(
            f"Skill update: {skill.capability_name} "
            f"{current_skill:.3f} -> {skill.current_skill:.3f} "
            f"(delta={delta:.4f}, performance={performance_score:.2f})"
        )
    
    def apply_skill_decay(
        self,
        agent_id: str,
        days_inactive: float = 1.0
    ) -> None:
        """Apply skill decay for inactive skills."""
        profile = self._profiles.get(agent_id)
        if not profile:
            return
        
        decay_amount = profile.skill_decay_rate * days_inactive
        
        for skill in profile.skills.values():
            days_since_use = (time.time() - skill.last_attempt) / 86400
            
            if days_since_use > 1.0:
                # Apply decay
                skill.current_skill = max(
                    skill.initial_skill,
                    skill.current_skill - (decay_amount * days_since_use)
                )
    
    def get_skill_level(self, agent_id: str, capability: str) -> float:
        """Get current skill level for capability."""
        profile = self._profiles.get(agent_id)
        if not profile:
            return 0.0
        
        return profile.get_skill_level(capability)
    
    def update_agent_capabilities(
        self,
        agent: AgentInfo
    ) -> List[AgentCapability]:
        """Update agent capabilities based on learned skills."""
        profile = self._profiles.get(agent.agent_id)
        if not profile:
            return agent.capabilities
        
        # Create updated capability list
        updated_caps = []
        
        # Update existing capabilities
        for cap in agent.capabilities:
            skill = profile.get_skill(cap.name)
            if skill:
                # Update skill level
                cap.skill_level = skill.current_skill
            updated_caps.append(cap)
        
        # Add new learned capabilities
        existing_names = {cap.name for cap in agent.capabilities}
        for skill_name, skill_exp in profile.skills.items():
            if skill_name not in existing_names:
                # Add as new capability
                updated_caps.append(
                    AgentCapability(
                        name=skill_name,
                        description=f"Learned through experience",
                        skill_level=skill_exp.current_skill
                    )
                )
        
        return updated_caps
    
    def suggest_role(self, agent_id: str) -> Optional[AgentRole]:
        """Suggest best role based on skill profile."""
        profile = self._profiles.get(agent_id)
        if not profile:
            return None
        
        # Map skills to roles
        role_scores = {
            AgentRole.RESEARCHER: 0.0,
            AgentRole.ANALYST: 0.0,
            AgentRole.CREATOR: 0.0,
            AgentRole.EXECUTOR: 0.0,
            AgentRole.COORDINATOR: 0.0,
            AgentRole.MONITOR: 0.0,
        }
        
        # Score each role based on relevant skills
        for skill_name, skill_exp in profile.skills.items():
            skill_level = skill_exp.current_skill
            
            # Map skills to roles (simplified)
            if "search" in skill_name.lower() or "research" in skill_name.lower():
                role_scores[AgentRole.RESEARCHER] += skill_level
            
            if "analysis" in skill_name.lower() or "data" in skill_name.lower():
                role_scores[AgentRole.ANALYST] += skill_level
            
            if "create" in skill_name.lower() or "generate" in skill_name.lower():
                role_scores[AgentRole.CREATOR] += skill_level
            
            if "execute" in skill_name.lower() or "command" in skill_name.lower():
                role_scores[AgentRole.EXECUTOR] += skill_level
            
            if "coordinate" in skill_name.lower() or "manage" in skill_name.lower():
                role_scores[AgentRole.COORDINATOR] += skill_level
            
            if "monitor" in skill_name.lower() or "health" in skill_name.lower():
                role_scores[AgentRole.MONITOR] += skill_level
        
        # Get best role
        if not any(role_scores.values()):
            return AgentRole.GENERALIST
        
        best_role = max(role_scores.items(), key=lambda x: x[1])[0]
        
        # Only suggest if significantly better
        if role_scores[best_role] > 2.0:  # Threshold
            return best_role
        
        return profile.current_role
    
    def get_profile(self, agent_id: str) -> Optional[PerformanceProfile]:
        """Get performance profile."""
        return self._profiles.get(agent_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get specialization statistics."""
        total_agents = len(self._profiles)
        total_skills = sum(len(p.skills) for p in self._profiles.values())
        total_tasks = sum(p.total_tasks for p in self._profiles.values())
        
        # Average skill levels
        all_skills = [
            skill.current_skill
            for profile in self._profiles.values()
            for skill in profile.skills.values()
        ]
        
        avg_skill = sum(all_skills) / len(all_skills) if all_skills else 0.0
        
        return {
            "total_agents": total_agents,
            "total_skills_tracked": total_skills,
            "total_tasks_recorded": total_tasks,
            "average_skill_level": avg_skill,
            "highly_skilled_count": sum(1 for s in all_skills if s > 0.8),
        }
