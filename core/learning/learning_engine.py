"""Learning Engine - Learn from experience."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from core.learning.success_pattern import SuccessPattern

if TYPE_CHECKING:
    from core.goal_hierarchy import GoalNode, GoalTree
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.learning_engine")


class LearningEngine:
    """Learn from goal execution experience."""
    
    def __init__(
        self,
        memory: "EpisodicMemory",
        storage_path: Optional[Path] = None,
    ):
        self._memory = memory
        self._storage_path = storage_path
        self._patterns: Dict[str, SuccessPattern] = {}
        
        if storage_path and storage_path.exists():
            self.load()
    
    def learn_from_goal(self, goal: "GoalNode", tree: "GoalTree") -> None:
        """
        Learn from completed goal.
        
        Args:
            goal: Completed goal node (ROOT or SUBGOAL)
            tree: Goal tree for context
        """
        if not goal.is_completed():
            return
        
        # Get subtree
        subtree = tree.get_subtree(goal.id)
        
        # Extract pattern
        pattern_data = self._extract_pattern(goal, subtree)
        
        if not pattern_data:
            return
        
        # Check if similar pattern exists
        existing = self._find_similar_pattern(
            pattern_data["goal_keywords"]
        )
        
        if existing:
            # Update existing pattern
            existing.record_success(goal.actual_ticks)
            existing.add_example(
                goal.description,
                "completed",
                goal.actual_ticks
            )
            log.info(
                f"Updated pattern '{existing.id}': "
                f"{existing.success_count} successes, "
                f"confidence={existing.confidence:.2f}"
            )
        else:
            # Create new pattern
            pattern = SuccessPattern(
                id=str(uuid.uuid4()),
                goal_type=pattern_data["goal_type"],
                goal_keywords=pattern_data["goal_keywords"],
                decomposition_strategy=pattern_data["strategy"],
                subgoals=pattern_data["subgoals"],
            )
            pattern.record_success(goal.actual_ticks)
            pattern.add_example(
                goal.description,
                "completed",
                goal.actual_ticks
            )
            
            self._patterns[pattern.id] = pattern
            log.info(f"Created new pattern '{pattern.id}' for goal type: {pattern.goal_type}")
        
        # Save
        self.save()
    
    def learn_from_failure(self, goal: "GoalNode", tree: "GoalTree") -> None:
        """
        Learn from failed goal.
        
        Args:
            goal: Failed goal node
            tree: Goal tree for context
        """
        if not goal.is_failed():
            return
        
        # Find patterns that might have been used
        matching_patterns = self.find_patterns(goal.description)
        
        # Record failure for all matching patterns
        for pattern in matching_patterns:
            pattern.record_failure()
            log.info(
                f"Pattern '{pattern.id}' failure recorded. "
                f"Success rate: {pattern.success_rate():.2f}"
            )
        
        self.save()
    
    def _extract_pattern(self, goal: "GoalNode", subtree: List["GoalNode"]) -> Optional[Dict[str, Any]]:
        """Extract pattern from goal execution."""
        # Get children (subgoals/actions)
        children = [n for n in subtree if n.parent_id == goal.id]
        
        if not children:
            return None
        
        # Extract keywords from goal description
        keywords = self._extract_keywords(goal.description)
        
        # Determine goal type
        goal_type = self._classify_goal(goal.description, keywords)
        
        # Extract subgoal templates
        subgoal_templates = []
        for child in children:
            template = {
                "type": child.type.value,
                "description_pattern": self._generalize_description(child.description),
                "action_type": child.action_type,
                "estimated_ticks": child.estimated_ticks,
            }
            subgoal_templates.append(template)
        
        # Describe strategy
        strategy = self._describe_strategy(children)
        
        return {
            "goal_type": goal_type,
            "goal_keywords": keywords,
            "strategy": strategy,
            "subgoals": subgoal_templates,
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text."""
        # Simple keyword extraction
        # TODO: More sophisticated NLP
        
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at",
            "to", "for", "of", "with", "by", "from", "as", "is", "was",
            "и", "в", "на", "с", "для", "из", "по", "о",
        }
        
        words = text.lower().split()
        keywords = [
            w.strip(".,!?;:") for w in words
            if len(w) > 2 and w not in stopwords
        ]
        
        return keywords[:10]  # Top 10 keywords
    
    def _classify_goal(self, description: str, keywords: List[str]) -> str:
        """Classify goal type."""
        # Simple classification based on keywords
        desc_lower = description.lower()
        
        if any(kw in desc_lower for kw in ["learn", "study", "изучить", "узнать"]):
            return "learning"
        elif any(kw in desc_lower for kw in ["analyze", "анализ", "исследовать"]):
            return "analysis"
        elif any(kw in desc_lower for kw in ["create", "write", "build", "создать", "написать"]):
            return "creation"
        elif any(kw in desc_lower for kw in ["find", "search", "найти", "искать"]):
            return "search"
        elif any(kw in desc_lower for kw in ["fix", "debug", "исправить"]):
            return "debugging"
        else:
            return "general"
    
    def _generalize_description(self, description: str) -> str:
        """Generalize description to pattern."""
        # Replace specific terms with placeholders
        # TODO: More sophisticated generalization
        return description
    
    def _describe_strategy(self, children: List["GoalNode"]) -> str:
        """Describe decomposition strategy."""
        steps = []
        for i, child in enumerate(children):
            if child.action_type:
                steps.append(f"{i+1}. {child.action_type}")
            else:
                steps.append(f"{i+1}. subgoal")
        
        return " → ".join(steps)
    
    def _find_similar_pattern(self, keywords: List[str]) -> Optional[SuccessPattern]:
        """Find existing similar pattern."""
        best_match = None
        best_score = 0.0
        
        for pattern in self._patterns.values():
            # Count common keywords
            common = set(keywords) & set(pattern.goal_keywords)
            if not pattern.goal_keywords:
                continue
            
            score = len(common) / len(pattern.goal_keywords)
            
            if score > best_score and score >= 0.5:  # 50% overlap
                best_score = score
                best_match = pattern
        
        return best_match
    
    def find_patterns(
        self,
        goal_description: str,
        min_confidence: float = 0.3,
        top_k: int = 3,
    ) -> List[SuccessPattern]:
        """
        Find patterns matching goal description.
        
        Args:
            goal_description: Goal to match
            min_confidence: Minimum confidence threshold
            top_k: Return top K patterns
        
        Returns:
            List of matching patterns, sorted by match score
        """
        matches = []
        
        for pattern in self._patterns.values():
            if pattern.confidence < min_confidence:
                continue
            
            score = pattern.matches(goal_description)
            if score > 0:
                matches.append((score, pattern))
        
        # Sort by score (descending)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        return [p for _, p in matches[:top_k]]
    
    def get_best_pattern(self, goal_description: str) -> Optional[SuccessPattern]:
        """Get best matching pattern."""
        patterns = self.find_patterns(goal_description, top_k=1)
        return patterns[0] if patterns else None
    
    def save(self) -> None:
        """Save patterns to storage."""
        if not self._storage_path:
            return
        
        data = {
            "patterns": [p.to_dict() for p in self._patterns.values()],
            "saved_at": time.time(),
        }
        
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log.info(f"Saved {len(self._patterns)} patterns")
    
    def load(self) -> None:
        """Load patterns from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return
        
        data = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._patterns = {
            p["id"]: SuccessPattern.from_dict(p)
            for p in data["patterns"]
        }
        log.info(f"Loaded {len(self._patterns)} patterns")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get learning statistics."""
        if not self._patterns:
            return {"total_patterns": 0}
        
        total_successes = sum(p.success_count for p in self._patterns.values())
        total_failures = sum(p.failure_count for p in self._patterns.values())
        avg_confidence = sum(p.confidence for p in self._patterns.values()) / len(self._patterns)
        
        by_type = {}
        for pattern in self._patterns.values():
            gt = pattern.goal_type
            if gt not in by_type:
                by_type[gt] = {"count": 0, "avg_confidence": 0.0}
            by_type[gt]["count"] += 1
            by_type[gt]["avg_confidence"] += pattern.confidence
        
        for gt in by_type:
            by_type[gt]["avg_confidence"] /= by_type[gt]["count"]
        
        return {
            "total_patterns": len(self._patterns),
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_success_rate": (
                total_successes / (total_successes + total_failures)
                if (total_successes + total_failures) > 0
                else 0
            ),
            "avg_confidence": avg_confidence,
            "by_type": by_type,
        }


import time