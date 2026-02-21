"""Success Pattern - Successful goal decomposition strategies."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class SuccessPattern:
    """A successful pattern for goal decomposition."""
    
    id: str
    goal_type: str  # Type/category of goal
    goal_keywords: List[str]  # Key terms in goal description
    
    # Strategy
    decomposition_strategy: str  # Description of the strategy
    subgoals: List[Dict[str, Any]]  # Template subgoals
    
    # Performance
    success_count: int = 0
    failure_count: int = 0
    total_ticks: int = 0
    avg_ticks: float = 0.0
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_used_at: Optional[float] = None
    confidence: float = 0.5  # 0.0 to 1.0
    
    # Examples
    examples: List[Dict[str, Any]] = field(default_factory=list)
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    def update_confidence(self) -> None:
        """Update confidence based on performance."""
        rate = self.success_rate()
        total = self.success_count + self.failure_count
        
        # Confidence increases with success rate and sample size
        sample_factor = min(total / 10.0, 1.0)  # Max at 10 samples
        self.confidence = rate * sample_factor
    
    def record_success(self, actual_ticks: int) -> None:
        """Record successful use of this pattern."""
        self.success_count += 1
        self.total_ticks += actual_ticks
        self.avg_ticks = self.total_ticks / self.success_count
        self.last_used_at = time.time()
        self.update_confidence()
    
    def record_failure(self) -> None:
        """Record failed use of this pattern."""
        self.failure_count += 1
        self.last_used_at = time.time()
        self.update_confidence()
    
    def add_example(self, goal: str, result: str, ticks: int) -> None:
        """Add example of successful use."""
        self.examples.append({
            "goal": goal,
            "result": result,
            "ticks": ticks,
            "timestamp": time.time(),
        })
        
        # Keep only recent examples
        if len(self.examples) > 5:
            self.examples = self.examples[-5:]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> "SuccessPattern":
        """Create from dictionary."""
        return SuccessPattern(**data)
    
    def matches(self, goal_description: str, threshold: float = 0.3) -> float:
        """
        Check if this pattern matches a goal.
        
        Args:
            goal_description: Goal to match
            threshold: Minimum match score
        
        Returns:
            Match score (0.0 to 1.0), or 0 if below threshold
        """
        goal_lower = goal_description.lower()
        
        # Count keyword matches
        matches = sum(
            1 for kw in self.goal_keywords
            if kw.lower() in goal_lower
        )
        
        if not self.goal_keywords:
            return 0.0
        
        match_score = matches / len(self.goal_keywords)
        
        # Weight by confidence
        weighted_score = match_score * self.confidence
        
        return weighted_score if weighted_score >= threshold else 0.0