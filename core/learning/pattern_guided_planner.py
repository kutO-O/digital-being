"""Pattern-Guided Goal Planner."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, List, Dict, Any, Optional

from core.goal_hierarchy import GoalNode, GoalTree, GoalType
from core.learning.learning_engine import LearningEngine

if TYPE_CHECKING:
    from core.goal_planner import GoalPlanner

log = logging.getLogger("digital_being.pattern_guided_planner")


class PatternGuidedPlanner:
    """
    Wrapper around GoalPlanner that uses learned patterns.
    
    Tries to use patterns first, falls back to LLM if no pattern matches.
    """
    
    def __init__(
        self,
        base_planner: "GoalPlanner",
        learning_engine: LearningEngine,
        pattern_threshold: float = 0.4,
    ):
        self._base_planner = base_planner
        self._learning = learning_engine
        self._pattern_threshold = pattern_threshold
        
        # Statistics
        self._pattern_uses = 0
        self._llm_uses = 0
    
    def decompose_goal(
        self,
        goal_node: GoalNode,
        tree: GoalTree,
        context: Optional[Dict[str, Any]] = None
    ) -> List[GoalNode]:
        """
        Decompose goal using patterns or LLM.
        
        Args:
            goal_node: Goal to decompose
            tree: Goal tree
            context: Optional context
        
        Returns:
            List of subgoal nodes
        """
        # Try to find matching pattern
        pattern = self._learning.get_best_pattern(goal_node.description)
        
        if pattern and pattern.confidence >= self._pattern_threshold:
            log.info(
                f"Using pattern '{pattern.id}' "
                f"(confidence={pattern.confidence:.2f}) "
                f"for goal: '{goal_node.description[:50]}'"
            )
            
            subgoals = self._apply_pattern(pattern, goal_node, tree)
            
            if subgoals:
                self._pattern_uses += 1
                return subgoals
            else:
                log.warning(f"Pattern application failed, falling back to LLM")
        
        # Fallback to LLM decomposition
        log.info(
            f"No suitable pattern found, using LLM for: "
            f"'{goal_node.description[:50]}'"
        )
        self._llm_uses += 1
        return self._base_planner.decompose_goal(goal_node, tree, context)
    
    def _apply_pattern(
        self,
        pattern,
        goal_node: GoalNode,
        tree: GoalTree
    ) -> List[GoalNode]:
        """
        Apply pattern to create subgoals.
        
        Args:
            pattern: SuccessPattern to apply
            goal_node: Goal to decompose
            tree: Goal tree
        
        Returns:
            List of subgoals or empty list on failure
        """
        try:
            subgoals = []
            
            for i, template in enumerate(pattern.subgoals):
                subgoal = GoalNode(
                    id=str(uuid.uuid4()),
                    type=GoalType(template["type"]),
                    description=self._adapt_description(
                        template["description_pattern"],
                        goal_node.description
                    ),
                    estimated_ticks=template["estimated_ticks"],
                    priority=10 - i,
                )
                
                if template["action_type"]:
                    subgoal.action_type = template["action_type"]
                    subgoal.action_params = {}
                
                subgoals.append(subgoal)
                tree.add_child(goal_node.id, subgoal)
            
            return subgoals
        
        except Exception as e:
            log.error(f"Failed to apply pattern: {e}")
            return []
    
    def _adapt_description(self, template: str, goal_description: str) -> str:
        """
        Adapt template description to specific goal.
        
        TODO: More sophisticated adaptation
        """
        # For now, just use template as-is
        return template
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics."""
        total = self._pattern_uses + self._llm_uses
        return {
            "pattern_uses": self._pattern_uses,
            "llm_uses": self._llm_uses,
            "total_decompositions": total,
            "pattern_rate": (
                self._pattern_uses / total if total > 0 else 0
            ),
        }