"""
Digital Being — Memory Consolidation System
Stage 29: Intelligent memory consolidation and forgetting.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.memory_consolidation")

class MemoryConsolidation:
    """
    Manages memory consolidation and forgetting.
    
    Features:
    - Importance scoring
    - Automatic consolidation
    - Forgetting mechanism
    - Memory strength decay
    - Consolidation history
    """
    
    # Importance thresholds
    CRITICAL_THRESHOLD = 0.9
    IMPORTANT_THRESHOLD = 0.7
    NORMAL_THRESHOLD = 0.4
    LOW_THRESHOLD = 0.2
    
    # Decay rates (per day)
    CRITICAL_DECAY = 0.01  # 1% per day
    IMPORTANT_DECAY = 0.05  # 5% per day
    NORMAL_DECAY = 0.10  # 10% per day
    LOW_DECAY = 0.20  # 20% per day
    
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path / "memory_consolidation.json"
        
        self._state = {
            "consolidated_memories": [],
            "forgotten_count": 0,
            "consolidation_runs": 0,
            "total_importance_score": 0.0,
            "last_consolidation": None,
        }
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load consolidation state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info("MemoryConsolidation: loaded state")
            except Exception as e:
                log.error(f"MemoryConsolidation: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save consolidation state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"MemoryConsolidation: failed to save state: {e}")
    
    def calculate_importance(self, episode: dict) -> float:
        """
        Calculate importance score for an episode.
        
        Factors:
        - Event type (some types more important)
        - Emotional intensity
        - Recency
        - Uniqueness
        - Connection to goals
        
        Args:
            episode: Episode dict
        
        Returns:
            Importance score (0-1)
        """
        score = 0.0
        
        # Base score by event type
        event_type = episode.get("event_type", "unknown")
        type_scores = {
            "goal_achieved": 0.9,
            "goal_set": 0.8,
            "skill_learned": 0.8,
            "error": 0.7,
            "insight": 0.9,
            "social_interaction": 0.6,
            "routine": 0.2,
            "observation": 0.3,
        }
        score += type_scores.get(event_type, 0.5)
        
        # Emotional intensity
        emotions = episode.get("emotions", {})
        if emotions:
            max_emotion = max(emotions.values()) if emotions else 0
            score += max_emotion * 0.3
        
        # Recency bonus (newer = slightly more important)
        timestamp = episode.get("timestamp", time.time())
        age_hours = (time.time() - timestamp) / 3600
        recency_factor = max(0, 1 - (age_hours / 168))  # Decay over 1 week
        score += recency_factor * 0.1
        
        # Context richness (more detail = more important)
        description = episode.get("description", "")
        if len(description) > 100:
            score += 0.1
        
        # Normalize to 0-1
        return min(1.0, score)
    
    def should_consolidate(self, importance: float) -> bool:
        """
        Determine if memory should be consolidated.
        
        Args:
            importance: Importance score
        
        Returns:
            True if should consolidate
        """
        return importance >= self.IMPORTANT_THRESHOLD
    
    def should_forget(self, episode: dict, current_strength: float) -> bool:
        """
        Determine if memory should be forgotten.
        
        Args:
            episode: Episode dict
            current_strength: Current memory strength
        
        Returns:
            True if should forget
        """
        importance = episode.get("importance", 0.5)
        
        # Never forget critical memories
        if importance >= self.CRITICAL_THRESHOLD:
            return False
        
        # Forget if strength decayed below threshold
        if current_strength < 0.1:
            return True
        
        # Forget if importance is low and old
        if importance < self.LOW_THRESHOLD:
            timestamp = episode.get("timestamp", time.time())
            age_days = (time.time() - timestamp) / 86400
            if age_days > 7:  # Older than 1 week
                return True
        
        return False
    
    def decay_memory_strength(self, episode: dict, days_passed: float) -> float:
        """
        Calculate memory strength after decay.
        
        Args:
            episode: Episode dict
            days_passed: Days since last access
        
        Returns:
            New strength value
        """
        importance = episode.get("importance", 0.5)
        current_strength = episode.get("strength", 1.0)
        
        # Determine decay rate
        if importance >= self.CRITICAL_THRESHOLD:
            decay_rate = self.CRITICAL_DECAY
        elif importance >= self.IMPORTANT_THRESHOLD:
            decay_rate = self.IMPORTANT_DECAY
        elif importance >= self.NORMAL_THRESHOLD:
            decay_rate = self.NORMAL_DECAY
        else:
            decay_rate = self.LOW_DECAY
        
        # Apply exponential decay
        new_strength = current_strength * ((1 - decay_rate) ** days_passed)
        
        return max(0.0, new_strength)
    
    def consolidate_memory(self, episode: dict) -> dict:
        """
        Consolidate a memory for long-term storage.
        
        Args:
            episode: Episode to consolidate
        
        Returns:
            Consolidated memory dict
        """
        importance = self.calculate_importance(episode)
        
        consolidated = {
            "id": episode.get("id", str(int(time.time() * 1000))),
            "event_type": episode.get("event_type"),
            "description": episode.get("description"),
            "timestamp": episode.get("timestamp", time.time()),
            "importance": importance,
            "strength": 1.0,
            "access_count": 0,
            "last_accessed": time.time(),
            "consolidated_at": time.time(),
            "summary": self._generate_summary(episode),
            "tags": self._extract_tags(episode),
        }
        
        self._state["consolidated_memories"].append(consolidated)
        self._state["total_importance_score"] += importance
        self._save_state()
        
        log.info(
            f"MemoryConsolidation: consolidated '{episode.get('event_type')}' "
            f"with importance {importance:.2f}"
        )
        
        return consolidated
    
    def _generate_summary(self, episode: dict) -> str:
        """
        Generate summary of episode.
        
        Args:
            episode: Episode dict
        
        Returns:
            Summary string
        """
        # Simple extraction for now
        # TODO: Use LLM for better summarization
        event_type = episode.get("event_type", "unknown")
        description = episode.get("description", "")
        
        # Truncate description to first sentence or 100 chars
        if "." in description:
            summary = description.split(".")[0] + "."
        else:
            summary = description[:100]
        
        return f"[{event_type}] {summary}"
    
    def _extract_tags(self, episode: dict) -> list[str]:
        """
        Extract tags from episode.
        
        Args:
            episode: Episode dict
        
        Returns:
            List of tags
        """
        tags = []
        
        # Event type as tag
        event_type = episode.get("event_type")
        if event_type:
            tags.append(event_type)
        
        # Extract keywords from description
        description = episode.get("description", "").lower()
        keywords = ["goal", "skill", "error", "success", "failure", "learn", "question"]
        
        for keyword in keywords:
            if keyword in description:
                tags.append(keyword)
        
        return list(set(tags))
    
    def run_consolidation_cycle(self, episodes: list[dict]) -> dict:
        """
        Run consolidation cycle on episodes.
        
        Args:
            episodes: List of episodes to process
        
        Returns:
            Consolidation results
        """
        consolidated_count = 0
        forgotten_count = 0
        updated_count = 0
        
        current_time = time.time()
        
        for episode in episodes:
            importance = self.calculate_importance(episode)
            episode["importance"] = importance
            
            # Check if should consolidate
            if self.should_consolidate(importance):
                if episode.get("id") not in [m["id"] for m in self._state["consolidated_memories"]]:
                    self.consolidate_memory(episode)
                    consolidated_count += 1
            
            # Update existing consolidated memories
            for memory in self._state["consolidated_memories"]:
                if memory["id"] == episode.get("id"):
                    # Calculate decay
                    last_accessed = memory.get("last_accessed", current_time)
                    days_passed = (current_time - last_accessed) / 86400
                    
                    new_strength = self.decay_memory_strength(memory, days_passed)
                    memory["strength"] = new_strength
                    
                    # Check if should forget
                    if self.should_forget(memory, new_strength):
                        self._state["consolidated_memories"].remove(memory)
                        forgotten_count += 1
                    else:
                        updated_count += 1
        
        self._state["consolidation_runs"] += 1
        self._state["forgotten_count"] += forgotten_count
        self._state["last_consolidation"] = current_time
        self._save_state()
        
        results = {
            "consolidated": consolidated_count,
            "forgotten": forgotten_count,
            "updated": updated_count,
            "total_memories": len(self._state["consolidated_memories"])
        }
        
        log.info(
            f"MemoryConsolidation: cycle complete - "
            f"{consolidated_count} consolidated, {forgotten_count} forgotten, "
            f"{updated_count} updated"
        )
        
        return results
    
    def get_important_memories(self, limit: int = 10) -> list[dict]:
        """Get most important consolidated memories."""
        sorted_memories = sorted(
            self._state["consolidated_memories"],
            key=lambda m: m["importance"] * m["strength"],
            reverse=True
        )
        return sorted_memories[:limit]
    
    def search_by_tag(self, tag: str) -> list[dict]:
        """Search consolidated memories by tag."""
        return [
            m for m in self._state["consolidated_memories"]
            if tag in m.get("tags", [])
        ]
    
    def get_stats(self) -> dict:
        """Get consolidation statistics."""
        total_memories = len(self._state["consolidated_memories"])
        
        # Count by importance level
        critical = sum(1 for m in self._state["consolidated_memories"] if m["importance"] >= self.CRITICAL_THRESHOLD)
        important = sum(1 for m in self._state["consolidated_memories"] if self.IMPORTANT_THRESHOLD <= m["importance"] < self.CRITICAL_THRESHOLD)
        normal = sum(1 for m in self._state["consolidated_memories"] if self.NORMAL_THRESHOLD <= m["importance"] < self.IMPORTANT_THRESHOLD)
        low = sum(1 for m in self._state["consolidated_memories"] if m["importance"] < self.NORMAL_THRESHOLD)
        
        avg_importance = 0.0
        if total_memories > 0:
            avg_importance = self._state["total_importance_score"] / total_memories
        
        return {
            "total_memories": total_memories,
            "forgotten_count": self._state["forgotten_count"],
            "consolidation_runs": self._state["consolidation_runs"],
            "avg_importance": avg_importance,
            "by_level": {
                "critical": critical,
                "important": important,
                "normal": normal,
                "low": low
            },
            "last_consolidation": self._state["last_consolidation"]
        }
