"""Theory of Mind - User Modeling."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

log = logging.getLogger("digital_being.theory_of_mind")


class UserModel:
    """
    Model of the user's knowledge, preferences, and context.
    
    Tracks:
    - Knowledge levels by topic
    - Preferences and patterns
    - Current context and goals
    - Interaction history
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path
        
        # Knowledge base: topic -> level
        self._knowledge: Dict[str, str] = {}  # "beginner", "intermediate", "expert"
        
        # Current context
        self._context: Dict[str, Any] = {
            "working_on": None,
            "recent_topics": [],
            "mood": "neutral",
            "session_start": time.time(),
        }
        
        # Preferences
        self._preferences: Dict[str, Any] = {
            "explanation_style": "detailed",  # "brief", "detailed", "step-by-step"
            "code_examples": True,
            "proactive_suggestions": True,
        }
        
        # Goals
        self._user_goals: List[str] = []
        
        # Interaction history (simplified)
        self._interaction_count = 0
        self._topics_discussed: Dict[str, int] = {}  # topic -> count
        
        if storage_path and storage_path.exists():
            self.load()
    
    def update_knowledge(self, topic: str, level: str) -> None:
        """Update user's knowledge level for a topic."""
        self._knowledge[topic] = level
        log.info(f"Updated knowledge: {topic} = {level}")
    
    def get_knowledge_level(self, topic: str) -> str:
        """Get user's knowledge level for topic."""
        return self._knowledge.get(topic, "beginner")
    
    def update_context(self, key: str, value: Any) -> None:
        """Update current context."""
        self._context[key] = value
        
        # Track recent topics
        if key == "topic":
            recent = self._context.get("recent_topics", [])
            if value not in recent:
                recent.append(value)
                if len(recent) > 5:
                    recent = recent[-5:]
                self._context["recent_topics"] = recent
    
    def get_context(self) -> Dict[str, Any]:
        """Get current context."""
        return self._context.copy()
    
    def set_preference(self, key: str, value: Any) -> None:
        """Set user preference."""
        self._preferences[key] = value
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference."""
        return self._preferences.get(key, default)
    
    def add_goal(self, goal: str) -> None:
        """Add user goal."""
        if goal not in self._user_goals:
            self._user_goals.append(goal)
    
    def remove_goal(self, goal: str) -> None:
        """Remove user goal."""
        if goal in self._user_goals:
            self._user_goals.remove(goal)
    
    def get_goals(self) -> List[str]:
        """Get user goals."""
        return self._user_goals.copy()
    
    def record_interaction(self, topic: Optional[str] = None) -> None:
        """Record an interaction."""
        self._interaction_count += 1
        
        if topic:
            self._topics_discussed[topic] = (
                self._topics_discussed.get(topic, 0) + 1
            )
    
    def get_profile_summary(self) -> str:
        """Get human-readable profile summary."""
        lines = []
        
        if self._knowledge:
            lines.append("Knowledge:")
            for topic, level in list(self._knowledge.items())[:5]:
                lines.append(f"  - {topic}: {level}")
        
        if self._context.get("working_on"):
            lines.append(f"Currently: {self._context['working_on']}")
        
        if self._user_goals:
            lines.append(f"Goals: {', '.join(self._user_goals[:3])}")
        
        return "\n".join(lines) if lines else "No profile data"
    
    def save(self) -> None:
        """Save to storage."""
        if not self._storage_path:
            return
        
        data = {
            "knowledge": self._knowledge,
            "context": self._context,
            "preferences": self._preferences,
            "goals": self._user_goals,
            "interaction_count": self._interaction_count,
            "topics_discussed": self._topics_discussed,
        }
        
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    def load(self) -> None:
        """Load from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return
        
        data = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._knowledge = data.get("knowledge", {})
        self._context = data.get("context", self._context)
        self._preferences = data.get("preferences", self._preferences)
        self._user_goals = data.get("goals", [])
        self._interaction_count = data.get("interaction_count", 0)
        self._topics_discussed = data.get("topics_discussed", {})