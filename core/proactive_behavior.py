"""Proactive Behavior Engine."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Dict, Any, List, Optional, Callable

if TYPE_CHECKING:
    from core.theory_of_mind import UserModel
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.proactive_behavior")


class ProactiveTrigger:
    """Trigger for proactive behavior."""
    
    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        action: str,
        cooldown: int = 3600,  # 1 hour
    ):
        self.name = name
        self.condition = condition
        self.action = action
        self.cooldown = cooldown
        self.last_triggered = 0.0
    
    def can_trigger(self, context: Dict[str, Any]) -> bool:
        """Check if trigger can fire."""
        # Check cooldown
        if time.time() - self.last_triggered < self.cooldown:
            return False
        
        # Check condition
        try:
            return self.condition(context)
        except Exception as e:
            log.error(f"Trigger condition error: {e}")
            return False
    
    def fire(self) -> str:
        """Fire trigger and return action."""
        self.last_triggered = time.time()
        return self.action


class ProactiveBehaviorEngine:
    """
    Engine for proactive actions.
    
    Triggers:
    - Temporal: time-based (daily summary, reminders)
    - Pattern-based: detected patterns (repeated questions)
    - Opportunity: new information relevant to user
    - Prevention: predicted problems
    """
    
    def __init__(
        self,
        user_model: "UserModel",
        memory: "EpisodicMemory",
    ):
        self._user = user_model
        self._memory = memory
        self._triggers: List[ProactiveTrigger] = []
        
        # Initialize default triggers
        self._init_default_triggers()
        
        self._stats = {
            "triggers_fired": 0,
            "suggestions_made": 0,
        }
    
    def _init_default_triggers(self) -> None:
        """Initialize default proactive triggers."""
        
        # Pattern detection: repeated questions
        self._triggers.append(ProactiveTrigger(
            name="repeated_question_automation",
            condition=lambda ctx: ctx.get("repeated_topic_count", 0) >= 3,
            action="suggest_automation",
            cooldown=24 * 3600,
        ))
        
        # Opportunity: related information
        self._triggers.append(ProactiveTrigger(
            name="related_info_suggestion",
            condition=lambda ctx: (
                ctx.get("working_on") and
                ctx.get("session_duration", 0) > 600  # 10 min
            ),
            action="suggest_related_info",
            cooldown=3600,
        ))
        
        # Daily summary
        self._triggers.append(ProactiveTrigger(
            name="daily_summary",
            condition=lambda ctx: ctx.get("time_of_day") == "end_of_day",
            action="provide_summary",
            cooldown=24 * 3600,
        ))
    
    def check_triggers(self) -> List[str]:
        """
        Check all triggers and return actions to take.
        
        Returns:
            List of action names to execute
        """
        # Build context
        context = self._build_context()
        
        actions = []
        for trigger in self._triggers:
            if trigger.can_trigger(context):
                action = trigger.fire()
                actions.append(action)
                self._stats["triggers_fired"] += 1
                log.info(f"Proactive trigger fired: {trigger.name} → {action}")
        
        return actions
    
    def _build_context(self) -> Dict[str, Any]:
        """Build context for trigger evaluation."""
        user_context = self._user.get_context()
        
        # Calculate session duration
        session_start = user_context.get("session_start", time.time())
        session_duration = time.time() - session_start
        
        # Check for repeated topics
        recent_topics = user_context.get("recent_topics", [])
        repeated_count = 0
        if recent_topics:
            most_common = max(set(recent_topics), key=recent_topics.count)
            repeated_count = recent_topics.count(most_common)
        
        # Time of day
        hour = time.localtime().tm_hour
        if hour >= 22 or hour < 6:
            time_of_day = "night"
        elif hour >= 18:
            time_of_day = "end_of_day"
        else:
            time_of_day = "day"
        
        return {
            **user_context,
            "session_duration": session_duration,
            "repeated_topic_count": repeated_count,
            "time_of_day": time_of_day,
        }
    
    def suggest(self, suggestion_type: str, content: str) -> None:
        """Record a proactive suggestion."""
        self._stats["suggestions_made"] += 1
        log.info(f"Proactive suggestion ({suggestion_type}): {content[:50]}")
        
        # In practice, would queue this for delivery
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get proactive behavior statistics."""
        return self._stats.copy()