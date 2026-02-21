"""Goal Planner - LLM-powered goal decomposition."""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, List, Dict, Any, Optional

from core.goal_hierarchy import GoalNode, GoalTree, GoalType, GoalStatus

if TYPE_CHECKING:
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel
    from core.memory.episodic import EpisodicMemory

log = logging.getLogger("digital_being.goal_planner")


class GoalPlanner:
    """LLM-powered goal decomposition and planning."""
    
    def __init__(
        self,
        ollama: "OllamaClient",
        world: "WorldModel",
        memory: "EpisodicMemory",
        max_depth: int = 4,
        max_children: int = 7,
    ):
        self._ollama = ollama
        self._world = world
        self._memory = memory
        self._max_depth = max_depth
        self._max_children = max_children
    
    def decompose_goal(
        self,
        goal_node: GoalNode,
        tree: GoalTree,
        context: Optional[Dict[str, Any]] = None
    ) -> List[GoalNode]:
        """
        Decompose goal into subgoals.
        
        Args:
            goal_node: Goal to decompose
            tree: Goal tree for context
            context: Additional context
        
        Returns:
            List of subgoal nodes
        """
        # Check depth limit
        path = tree.get_path_to_root(goal_node.id)
        if len(path) >= self._max_depth:
            log.warning(
                f"Goal {goal_node.id} reached max depth {self._max_depth}, "
                "creating action node"
            )
            return [self._create_action_from_goal(goal_node)]
        
        # Check if already decomposed
        if goal_node.children_ids:
            log.debug(f"Goal {goal_node.id} already has children, skipping")
            return []
        
        log.info(f"Decomposing goal: '{goal_node.description[:60]}'")
        
        # Build context
        ctx = context or {}
        world_summary = self._world.summary()
        recent_episodes = self._memory.get_recent_episodes(5)
        
        # Build prompt
        prompt = self._build_decomposition_prompt(
            goal_node, world_summary, recent_episodes, ctx
        )
        
        system = (
            "Ты — Goal Planner для автономной AI системы. "
            "Декомпозируй сложные цели на конкретные шаги. "
            "Отвечай ТОЛЬКО валидным JSON."
        )
        
        # Call LLM
        try:
            raw = self._ollama.chat(prompt, system, timeout=60)
            if not raw:
                log.warning("LLM returned empty response for decomposition")
                return [self._create_action_from_goal(goal_node)]
            
            # Parse response
            subgoals_data = self._parse_decomposition_response(raw)
            
            if not subgoals_data:
                log.warning("Could not parse LLM decomposition, creating action")
                return [self._create_action_from_goal(goal_node)]
            
            # Create subgoal nodes
            subgoals = []
            for i, sg_data in enumerate(subgoals_data[:self._max_children]):
                subgoal = self._create_subgoal_node(sg_data, i)
                subgoals.append(subgoal)
                tree.add_child(goal_node.id, subgoal)
            
            log.info(
                f"Goal '{goal_node.description[:40]}' decomposed into "
                f"{len(subgoals)} subgoals"
            )
            return subgoals
        
        except Exception as e:
            log.error(f"Goal decomposition failed: {e}")
            return [self._create_action_from_goal(goal_node)]
    
    def _build_decomposition_prompt(
        self,
        goal: GoalNode,
        world_summary: str,
        episodes: List[dict],
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for goal decomposition."""
        episodes_str = "; ".join(
            f"{e.get('event_type', '?')}: {e.get('description', '')[:50]}"
            for e in episodes
        ) if episodes else "нет"
        
        ctx_str = ""
        if context:
            ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        
        prompt = f"""
Цель: "{goal.description}"

Текущее состояние системы:
{world_summary}

Последние действия:
{episodes_str}

{f'Дополнительный контекст:\n{ctx_str}\n' if ctx_str else ''}
Разбей эту цель на 3-7 конкретных шагов (subgoals).
Каждый шаг должен быть:
- Конкретным и достижимым
- Иметь чёткий критерий успеха
- Иметь оценку времени (в тиках, 1 tick ≈ 1 минута)

Ответь ТОЛЬКО в формате JSON:
{{
  "subgoals": [
    {{
      "description": "конкретное описание шага",
      "success_criteria": {{"condition": "что проверить", "expected": "ожидаемый результат"}},
      "estimated_ticks": 2,
      "is_action": false,
      "action_type": null,
      "action_params": {{}}
    }}
  ],
  "reasoning": "почему выбрана такая декомпозиция"
}}

Если шаг — это конкретное действие (выполнить команду, прочитать файл и т.п.),
поставь "is_action": true и укажи "action_type" ("shell", "read_file", "write_file", "llm_query").
"""
        return prompt
    
    def _parse_decomposition_response(self, raw: str) -> List[Dict[str, Any]]:
        """Parse LLM response for decomposition."""
        if not raw:
            return []
        
        try:
            data = json.loads(raw)
            return data.get("subgoals", [])
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from text
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start:end+1])
                return data.get("subgoals", [])
            except json.JSONDecodeError:
                pass
        
        log.warning("Could not parse decomposition JSON")
        return []
    
    def _create_subgoal_node(
        self, data: Dict[str, Any], index: int
    ) -> GoalNode:
        """Create subgoal node from decomposition data."""
        is_action = data.get("is_action", False)
        node_type = GoalType.ACTION if is_action else GoalType.SUBGOAL
        
        node = GoalNode(
            id=str(uuid.uuid4()),
            type=node_type,
            description=data.get("description", f"Subgoal {index + 1}"),
            success_criteria=data.get("success_criteria", {}),
            estimated_ticks=int(data.get("estimated_ticks", 1)),
            priority=10 - index,  # Higher priority for earlier steps
        )
        
        if is_action:
            node.action_type = data.get("action_type", "llm_query")
            node.action_params = data.get("action_params", {})
        
        return node
    
    def _create_action_from_goal(self, goal: GoalNode) -> GoalNode:
        """Create action node from goal (fallback)."""
        return GoalNode(
            id=str(uuid.uuid4()),
            type=GoalType.ACTION,
            description=goal.description,
            action_type="llm_query",
            action_params={"query": goal.description},
            estimated_ticks=1,
            priority=goal.priority,
        )
    
    def estimate_goal_complexity(
        self, goal_description: str
    ) -> Dict[str, Any]:
        """
        Estimate goal complexity without full decomposition.
        
        Returns:
            Dict with estimated_ticks, estimated_depth, complexity_level
        """
        prompt = f"""
Цель: "{goal_description}"

Оцени сложность этой цели:
- Сколько шагов потребуется (грубая оценка)
- Сколько уровней вложенности (depth)
- Общая сложность: "simple" | "moderate" | "complex"

Ответь ТОЛЬКО JSON:
{{
  "estimated_steps": 3,
  "estimated_depth": 2,
  "complexity": "moderate",
  "reasoning": "короткое объяснение"
}}
"""
        
        system = "Ты — Goal Estimator. Оценивай сложность целей. Отвечай JSON."
        
        try:
            raw = self._ollama.chat(prompt, system, timeout=30)
            if raw:
                data = json.loads(raw)
                return {
                    "estimated_ticks": data.get("estimated_steps", 1),
                    "estimated_depth": data.get("estimated_depth", 1),
                    "complexity": data.get("complexity", "moderate"),
                    "reasoning": data.get("reasoning", ""),
                }
        except Exception as e:
            log.debug(f"Goal estimation failed: {e}")
        
        # Fallback: simple heuristic
        words = len(goal_description.split())
        if words < 5:
            complexity = "simple"
            ticks = 1
        elif words < 15:
            complexity = "moderate"
            ticks = 3
        else:
            complexity = "complex"
            ticks = 5
        
        return {
            "estimated_ticks": ticks,
            "estimated_depth": 2,
            "complexity": complexity,
            "reasoning": "fallback heuristic",
        }