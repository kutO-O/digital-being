"""
Digital Being - Skill Exchange
Stage 27: Share and import skills between agents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from core.message_protocol import MessageBuilder, Message, MessageType

if TYPE_CHECKING:
    from core.skill_library import SkillLibrary
    from core.message_broker import MessageBroker

log = logging.getLogger("digital_being.skill_exchange")


class SkillExchange:
    """Manages skill sharing between agents."""
    
    def __init__(
        self,
        agent_id: str,
        skill_library: "SkillLibrary",
        message_broker: "MessageBroker"
    ):
        self._agent_id = agent_id
        self._skill_library = skill_library
        self._broker = message_broker
        
        # Track skill sources (skill_id -> agent_id)
        self._skill_sources: dict[str, str] = {}
        
        # Trust scores per agent (agent_id -> score 0-1)
        self._trust_scores: dict[str, float] = {}
        
        # Register handler for skill share messages
        self._broker.register_handler(MessageType.SKILL_SHARE, self._handle_skill_share)
        
        log.info(f"SkillExchange initialized for agent {agent_id}")
    
    def share_skill(self, skill_id: str, to_agent: str = "*") -> Optional[str]:
        """Share a skill with other agent(s)."""
        # Get skill from library
        skill = self._get_skill(skill_id)
        if not skill:
            log.warning(f"Skill {skill_id} not found in library")
            return None
        
        # Create skill share message
        message = MessageBuilder.share_skill(
            from_agent=self._agent_id,
            skill_data=skill,
            to_agent=to_agent
        )
        
        msg_id = self._broker.send(message)
        log.info(
            f"Shared skill '{skill.get('name')}' (confidence={skill.get('confidence', 0):.2f}) "
            f"to {to_agent}"
        )
        
        return msg_id
    
    def import_skill(self, skill_data: dict, from_agent: str) -> bool:
        """Import a skill from another agent."""
        # Extract skill info
        skill_id = skill_data.get("id")
        name = skill_data.get("name", "unknown")
        confidence = skill_data.get("confidence", 0.5)
        
        if not skill_id:
            log.warning("Received skill without ID")
            return False
        
        # Check if already have this skill
        existing = self._get_skill(skill_id)
        if existing:
            # Update if imported version has higher confidence
            if confidence > existing.get("confidence", 0):
                log.info(f"Updating existing skill '{name}' with higher confidence version")
            else:
                log.debug(f"Skill '{name}' already exists with equal/higher confidence")
                return False
        
        # Apply trust adjustment
        trust = self._get_trust(from_agent)
        adjusted_confidence = confidence * trust
        skill_data["confidence"] = adjusted_confidence
        skill_data["imported_from"] = from_agent
        
        # Add to library
        success = self._add_skill_to_library(skill_data)
        
        if success:
            self._skill_sources[skill_id] = from_agent
            log.info(
                f"Imported skill '{name}' from {from_agent} "
                f"(confidence: {confidence:.2f} -> {adjusted_confidence:.2f} after trust)"
            )
        
        return success
    
    def get_shared_skills(self) -> list[dict]:
        """Get all skills that were imported from other agents."""
        skills = []
        for skill_id, source in self._skill_sources.items():
            skill = self._get_skill(skill_id)
            if skill:
                skill["source_agent"] = source
                skills.append(skill)
        return skills
    
    def update_trust(self, agent_id: str, delta: float):
        """Update trust score for an agent based on skill performance."""
        current = self._trust_scores.get(agent_id, 0.5)  # Start at neutral 0.5
        new_trust = max(0.0, min(1.0, current + delta))
        self._trust_scores[agent_id] = new_trust
        log.debug(f"Trust for {agent_id}: {current:.2f} -> {new_trust:.2f}")
    
    def _get_trust(self, agent_id: str) -> float:
        """Get trust score for agent."""
        return self._trust_scores.get(agent_id, 0.5)  # Default 0.5 (neutral)
    
    def _handle_skill_share(self, message: Message):
        """Handle incoming skill share message."""
        from_agent = message.from_agent
        skill_data = message.payload
        
        # Import the skill
        self.import_skill(skill_data, from_agent)
    
    def _get_skill(self, skill_id: str) -> Optional[dict]:
        """Get skill from library."""
        # Find skill by ID in library
        for skill in self._skill_library._skills:
            if skill.get("id") == skill_id:
                return skill
        return None
    
    def _add_skill_to_library(self, skill_data: dict) -> bool:
        """Add skill to library."""
        try:
            # Add to skills list
            self._skill_library._skills.append(skill_data)
            self._skill_library._save()
            return True
        except Exception as e:
            log.error(f"Failed to add skill to library: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get exchange statistics."""
        shared_count = len(self._skill_sources)
        return {
            "shared_skills": shared_count,
            "trusted_agents": len(self._trust_scores),
            "avg_trust": (
                sum(self._trust_scores.values()) / len(self._trust_scores)
                if self._trust_scores else 0.5
            )
        }
