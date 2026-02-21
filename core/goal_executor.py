"""Goal Executor - Execute goals and track progress."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple

from core.goal_hierarchy import GoalNode, GoalTree, GoalType, GoalStatus

if TYPE_CHECKING:
    from core.goal_planner import GoalPlanner
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel
    from core.memory.episodic import EpisodicMemory
    from core.shell_executor import ShellExecutor

log = logging.getLogger("digital_being.goal_executor")


class GoalExecutor:
    """Execute goals and track progress."""
    
    def __init__(
        self,
        tree: GoalTree,
        planner: "GoalPlanner",
        ollama: "OllamaClient",
        world: "WorldModel",
        memory: "EpisodicMemory",
        shell_executor: Optional["ShellExecutor"] = None,
    ):
        self._tree = tree
        self._planner = planner
        self._ollama = ollama
        self._world = world
        self._memory = memory
        self._shell = shell_executor
        
        self._current_tick = 0
        self._execution_stats = {
            "total_executed": 0,
            "successful": 0,
            "failed": 0,
            "replanned": 0,
        }
    
    async def execute_tick(self, tick_number: int) -> Dict[str, Any]:
        """
        Execute one tick of goal-oriented behavior.
        
        Returns:
            Dict with execution results and statistics
        """
        self._current_tick = tick_number
        
        # Get active goals
        active_goals = self._tree.get_active_goals()
        
        # If no active goals, check pending root goals
        if not active_goals:
            roots = self._tree.get_root_nodes()
            pending_roots = [
                r for r in roots
                if r.status == GoalStatus.PENDING
            ]
            
            if pending_roots:
                # Activate first pending root
                root = pending_roots[0]
                root.status = GoalStatus.ACTIVE
                root.started_at = time.time()
                log.info(
                    f"Activated root goal: '{root.description[:60]}'"
                )
                active_goals = [root]
            else:
                log.debug("No active or pending goals")
                return {"status": "idle", "reason": "no_goals"}
        
        results = []
        
        for goal in active_goals:
            result = await self._execute_goal(goal)
            results.append(result)
        
        # Save tree
        self._tree.save()
        
        return {
            "status": "executed",
            "goals_processed": len(results),
            "results": results,
            "stats": self._execution_stats,
        }
    
    async def _execute_goal(self, goal: GoalNode) -> Dict[str, Any]:
        """Execute single goal."""
        log.info(f"Executing goal: '{goal.description[:60]}'")
        
        # Increment tick counter
        goal.actual_ticks += 1
        
        # Check if goal needs decomposition
        if goal.type == GoalType.ROOT or goal.type == GoalType.SUBGOAL:
            if not goal.children_ids:
                # Decompose
                log.info(f"Decomposing goal: {goal.id}")
                children = self._planner.decompose_goal(goal, self._tree)
                
                if not children:
                    # Failed to decompose
                    goal.status = GoalStatus.FAILED
                    goal.failure_reason = "decomposition_failed"
                    goal.completed_at = time.time()
                    self._execution_stats["failed"] += 1
                    
                    self._memory.add_episode(
                        "goal.failed",
                        f"Failed to decompose: {goal.description[:200]}",
                        outcome="error",
                    )
                    
                    return {
                        "goal_id": goal.id,
                        "status": "failed",
                        "reason": "decomposition_failed",
                    }
                
                log.info(
                    f"Goal decomposed into {len(children)} children"
                )
            
            # Check children progress
            children = self._tree.get_children(goal.id)
            
            if not children:
                goal.status = GoalStatus.FAILED
                goal.failure_reason = "no_children"
                return {"goal_id": goal.id, "status": "failed"}
            
            # Activate first pending child
            pending = [c for c in children if c.status == GoalStatus.PENDING]
            if pending:
                child = pending[0]
                child.status = GoalStatus.ACTIVE
                child.started_at = time.time()
                log.info(f"Activated child goal: '{child.description[:60]}'")
                
                # Execute child
                return await self._execute_goal(child)
            
            # Check if all children completed
            all_completed = all(
                c.status == GoalStatus.COMPLETED for c in children
            )
            
            if all_completed:
                # Goal completed!
                goal.status = GoalStatus.COMPLETED
                goal.completed_at = time.time()
                self._execution_stats["successful"] += 1
                
                self._memory.add_episode(
                    "goal.completed",
                    f"Completed goal: {goal.description[:200]}",
                    outcome="success",
                    data={
                        "estimated_ticks": goal.estimated_ticks,
                        "actual_ticks": goal.actual_ticks,
                    },
                )
                
                log.info(
                    f"Goal completed: '{goal.description[:60]}' "
                    f"({goal.actual_ticks}/{goal.estimated_ticks} ticks)"
                )
                
                # If this is root, we're done
                if goal.type == GoalType.ROOT:
                    return {
                        "goal_id": goal.id,
                        "status": "completed",
                        "root_completed": True,
                    }
                
                # Continue with parent
                parent = self._tree.get_parent(goal.id)
                if parent and parent.status == GoalStatus.ACTIVE:
                    return await self._execute_goal(parent)
                
                return {"goal_id": goal.id, "status": "completed"}
            
            # Check for failures
            any_failed = any(c.status == GoalStatus.FAILED for c in children)
            if any_failed:
                # Adaptive replanning
                log.warning(f"Child goal failed, replanning: {goal.id}")
                replanned = await self._replan_goal(goal)
                
                if replanned:
                    self._execution_stats["replanned"] += 1
                    return {"goal_id": goal.id, "status": "replanned"}
                else:
                    goal.status = GoalStatus.FAILED
                    goal.failure_reason = "child_failed_no_replan"
                    goal.completed_at = time.time()
                    self._execution_stats["failed"] += 1
                    return {"goal_id": goal.id, "status": "failed"}
            
            # Still in progress
            return {"goal_id": goal.id, "status": "in_progress"}
        
        elif goal.type == GoalType.ACTION:
            # Execute action
            success, result = await self._execute_action(goal)
            
            if success:
                # Validate success criteria
                if await self._validate_success(goal, result):
                    goal.status = GoalStatus.COMPLETED
                    goal.completed_at = time.time()
                    goal.action_result = result
                    self._execution_stats["successful"] += 1
                    
                    log.info(
                        f"Action completed: '{goal.description[:60]}'"
                    )
                    
                    self._memory.add_episode(
                        "goal.action_completed",
                        f"Action: {goal.description[:200]}",
                        outcome="success",
                        data={"action_type": goal.action_type},
                    )
                    
                    # Continue with parent
                    parent = self._tree.get_parent(goal.id)
                    if parent and parent.status == GoalStatus.ACTIVE:
                        return await self._execute_goal(parent)
                    
                    return {
                        "goal_id": goal.id,
                        "status": "completed",
                        "result": result,
                    }
                else:
                    # Success criteria not met
                    goal.status = GoalStatus.FAILED
                    goal.failure_reason = "criteria_not_met"
                    goal.completed_at = time.time()
                    self._execution_stats["failed"] += 1
                    
                    return {
                        "goal_id": goal.id,
                        "status": "failed",
                        "reason": "criteria_not_met",
                    }
            else:
                # Action failed
                goal.status = GoalStatus.FAILED
                goal.failure_reason = "action_failed"
                goal.completed_at = time.time()
                self._execution_stats["failed"] += 1
                
                self._memory.add_episode(
                    "goal.action_failed",
                    f"Failed action: {goal.description[:200]}",
                    outcome="error",
                    data={"action_type": goal.action_type},
                )
                
                return {
                    "goal_id": goal.id,
                    "status": "failed",
                    "reason": "action_failed",
                }
        
        return {"goal_id": goal.id, "status": "unknown"}
    
    async def _execute_action(
        self, action: GoalNode
    ) -> Tuple[bool, Any]:
        """Execute action node."""
        action_type = action.action_type or "llm_query"
        params = action.action_params
        
        log.info(
            f"Executing action: type={action_type}, "
            f"desc='{action.description[:40]}'"
        )
        
        self._execution_stats["total_executed"] += 1
        
        try:
            if action_type == "shell":
                return await self._execute_shell(action, params)
            elif action_type == "llm_query":
                return await self._execute_llm_query(action, params)
            elif action_type == "read_file":
                return await self._execute_read_file(params)
            elif action_type == "write_file":
                return await self._execute_write_file(params)
            else:
                log.warning(f"Unknown action type: {action_type}")
                return False, f"unknown_action_type: {action_type}"
        except Exception as e:
            log.error(f"Action execution error: {e}")
            return False, str(e)
    
    async def _execute_shell(
        self, action: GoalNode, params: dict
    ) -> Tuple[bool, Any]:
        """Execute shell command."""
        if not self._shell:
            return False, "shell_executor_unavailable"
        
        command = params.get("command", action.description)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._shell.execute_safe(command, self._memory)
        )
        
        return result["success"], result
    
    async def _execute_llm_query(
        self, action: GoalNode, params: dict
    ) -> Tuple[bool, Any]:
        """Execute LLM query."""
        query = params.get("query", action.description)
        system = params.get("system", "Ты — Digital Being. Отвечай кратко.")
        
        try:
            response = self._ollama.chat(query, system, timeout=45)
            if response:
                return True, response
            else:
                return False, "llm_no_response"
        except Exception as e:
            return False, str(e)
    
    async def _execute_read_file(self, params: dict) -> Tuple[bool, Any]:
        """Read file content."""
        from pathlib import Path
        
        path = params.get("path")
        if not path:
            return False, "no_path_specified"
        
        try:
            content = Path(path).read_text(encoding="utf-8")
            return True, content
        except Exception as e:
            return False, str(e)
    
    async def _execute_write_file(self, params: dict) -> Tuple[bool, Any]:
        """Write content to file."""
        from pathlib import Path
        
        path = params.get("path")
        content = params.get("content", "")
        
        if not path:
            return False, "no_path_specified"
        
        try:
            Path(path).write_text(content, encoding="utf-8")
            return True, f"written: {path}"
        except Exception as e:
            return False, str(e)
    
    async def _validate_success(
        self, action: GoalNode, result: Any
    ) -> bool:
        """Validate if action met success criteria."""
        if not action.success_criteria:
            # No criteria = always success
            return True
        
        # Simple validation for now
        # TODO: More sophisticated validation with LLM
        condition = action.success_criteria.get("condition", "")
        expected = action.success_criteria.get("expected", "")
        
        if not condition:
            return True
        
        # Basic checks
        if "exists" in condition.lower():
            return result is not None and result != ""
        elif "contains" in condition.lower():
            return expected.lower() in str(result).lower()
        elif "success" in condition.lower():
            return isinstance(result, dict) and result.get("success", False)
        
        # Default: assume success
        return True
    
    async def _replan_goal(self, goal: GoalNode) -> bool:
        """
        Replan goal after child failure.
        
        Returns:
            True if replanned successfully
        """
        log.info(f"Replanning goal: '{goal.description[:60]}'")
        
        # Remove failed children
        children = self._tree.get_children(goal.id)
        for child in children:
            if child.status == GoalStatus.FAILED:
                self._tree.remove_node(child.id)
        
        # Clear children list
        goal.children_ids.clear()
        
        # Try decompose again with failure context
        context = {
            "previous_attempt_failed": True,
            "failure_reason": "child goal failed",
        }
        
        children = self._planner.decompose_goal(goal, self._tree, context)
        
        if children:
            log.info(f"Goal replanned with {len(children)} new children")
            return True
        else:
            log.warning("Replanning failed")
            return False
    
    def get_progress_report(self, root_id: str) -> Dict[str, Any]:
        """Get progress report for goal tree."""
        root = self._tree.get_node(root_id)
        if not root:
            return {"error": "root_not_found"}
        
        subtree = self._tree.get_subtree(root_id)
        
        total = len(subtree)
        completed = sum(1 for n in subtree if n.is_completed())
        failed = sum(1 for n in subtree if n.is_failed())
        active = sum(1 for n in subtree if n.status == GoalStatus.ACTIVE)
        pending = sum(1 for n in subtree if n.status == GoalStatus.PENDING)
        
        estimated_total = sum(n.estimated_ticks for n in subtree)
        actual_total = sum(n.actual_ticks for n in subtree)
        
        progress_pct = (completed / total * 100) if total > 0 else 0
        
        return {
            "root_id": root_id,
            "description": root.description,
            "status": root.status.value,
            "total_nodes": total,
            "completed": completed,
            "failed": failed,
            "active": active,
            "pending": pending,
            "progress_percent": round(progress_pct, 1),
            "estimated_ticks": estimated_total,
            "actual_ticks": actual_total,
            "time_started": root.started_at,
            "time_completed": root.completed_at,
        }