"""Integration of Goal Hierarchy with FaultTolerantHeavyTick."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Any, Optional

from core.goal_hierarchy import GoalNode, GoalTree, GoalType, GoalStatus
from core.goal_planner import GoalPlanner
from core.goal_executor import GoalExecutor

if TYPE_CHECKING:
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel
    from core.memory.episodic import EpisodicMemory
    from core.shell_executor import ShellExecutor

log = logging.getLogger("digital_being.goal_integration")


class GoalOrientedBehavior:
    """
    Goal-oriented behavior integration for FaultTolerantHeavyTick.
    
    This provides automatic switching between:
    - Reactive mode: respond to environment changes (original behavior)
    - Goal-oriented mode: pursue multi-step goals
    """
    
    def __init__(
        self,
        ollama: "OllamaClient",
        world: "WorldModel",
        memory: "EpisodicMemory",
        storage_dir: Path,
        shell_executor: Optional["ShellExecutor"] = None,
        max_depth: int = 4,
        max_children: int = 7,
    ):
        # Initialize components
        tree_path = storage_dir / "goal_tree.json"
        self._tree = GoalTree(storage_path=tree_path)
        
        self._planner = GoalPlanner(
            ollama=ollama,
            world=world,
            memory=memory,
            max_depth=max_depth,
            max_children=max_children,
        )
        
        self._executor = GoalExecutor(
            tree=self._tree,
            planner=self._planner,
            ollama=ollama,
            world=world,
            memory=memory,
            shell_executor=shell_executor,
        )
        
        self._memory = memory
        self._enabled = True
        self._mode = "reactive"  # "reactive" or "goal_oriented"
    
    def is_enabled(self) -> bool:
        """Check if goal-oriented behavior is enabled."""
        return self._enabled
    
    def enable(self) -> None:
        """Enable goal-oriented behavior."""
        self._enabled = True
        log.info("Goal-oriented behavior enabled")
    
    def disable(self) -> None:
        """Disable goal-oriented behavior."""
        self._enabled = False
        log.info("Goal-oriented behavior disabled")
    
    def get_mode(self) -> str:
        """Get current mode."""
        return self._mode
    
    def should_use_goal_mode(self) -> bool:
        """
        Decide if should use goal-oriented mode for this tick.
        
        Returns:
            True if should pursue goals, False for reactive mode
        """
        if not self._enabled:
            return False
        
        # If we have active goals, continue with them
        active = self._tree.get_active_goals()
        if active:
            return True
        
        # If we have pending root goals, activate them
        roots = self._tree.get_root_nodes()
        pending = [r for r in roots if r.status == GoalStatus.PENDING]
        if pending:
            return True
        
        # Otherwise, use reactive mode
        return False
    
    async def execute_tick(self, tick_number: int) -> Dict[str, Any]:
        """
        Execute one tick of goal-oriented behavior.
        
        Returns:
            Dict with execution results
        """
        if not self._enabled:
            return {"status": "disabled"}
        
        # Check mode
        if self.should_use_goal_mode():
            self._mode = "goal_oriented"
            log.info(f"[Tick #{tick_number}] Goal-oriented mode")
            
            result = await self._executor.execute_tick(tick_number)
            
            # Add episode
            if result.get("status") == "executed":
                self._memory.add_episode(
                    "goal.tick_executed",
                    f"Goal tick: {result.get('goals_processed', 0)} goals processed",
                    outcome="success",
                    data=result.get("stats", {}),
                )
            
            return result
        else:
            self._mode = "reactive"
            log.debug(f"[Tick #{tick_number}] Reactive mode (no active goals)")
            return {"status": "reactive", "reason": "no_active_goals"}
    
    def add_user_goal(self, description: str, context: Optional[Dict] = None) -> str:
        """
        Add new user goal.
        
        Args:
            description: Goal description
            context: Optional context
        
        Returns:
            Goal ID
        """
        import uuid
        
        # Estimate complexity
        complexity = self._planner.estimate_goal_complexity(description)
        
        # Create root goal
        goal = GoalNode(
            id=str(uuid.uuid4()),
            type=GoalType.ROOT,
            description=description,
            estimated_ticks=complexity.get("estimated_ticks", 1),
            context=context or {},
            priority=10,  # User goals have highest priority
        )
        
        self._tree.add_node(goal)
        self._tree.save()
        
        log.info(
            f"Added user goal: '{description[:60]}' "
            f"(complexity: {complexity.get('complexity', 'unknown')})"
        )
        
        self._memory.add_episode(
            "goal.user_added",
            f"User goal: {description[:200]}",
            outcome="pending",
            data={"goal_id": goal.id, "complexity": complexity},
        )
        
        return goal.id
    
    def get_active_goal_description(self) -> Optional[str]:
        """
        Get description of current active goal.
        
        Returns:
            Description or None
        """
        active = self._tree.get_active_goals()
        if not active:
            return None
        
        # Find root
        for goal in active:
            if goal.type == GoalType.ROOT:
                return goal.description
            path = self._tree.get_path_to_root(goal.id)
            if path:
                return path[0].description
        
        return active[0].description
    
    def get_progress_summary(self) -> str:
        """
        Get human-readable progress summary.
        
        Returns:
            Progress summary string
        """
        roots = self._tree.get_root_nodes()
        if not roots:
            return "Нет активных целей."
        
        lines = []
        for root in roots:
            if root.is_terminal():
                continue
            
            report = self._executor.get_progress_report(root.id)
            progress = report.get("progress_percent", 0)
            completed = report.get("completed", 0)
            total = report.get("total_nodes", 0)
            
            lines.append(
                f"\u2022 {root.description[:50]}: {progress:.0f}% "
                f"({completed}/{total})"
            )
        
        return "\n".join(lines) if lines else "Все цели завершены."
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        tree_stats = self._tree.get_statistics()
        exec_stats = self._executor._execution_stats
        
        return {
            "mode": self._mode,
            "enabled": self._enabled,
            "tree": tree_stats,
            "execution": exec_stats,
        }
    
    def clear_completed_goals(self) -> int:
        """Clear completed goal trees.
        
        Returns:
            Number of goals cleared
        """
        roots = self._tree.get_root_nodes()
        cleared = 0
        
        for root in roots:
            if root.status == GoalStatus.COMPLETED:
                self._tree.remove_node(root.id)
                cleared += 1
        
        if cleared > 0:
            self._tree.save()
            log.info(f"Cleared {cleared} completed goal tree(s)")
        
        return cleared