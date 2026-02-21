"""Tool-aware Goal Executor."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Tuple, Any, Optional

from core.tools.registry import ToolRegistry
from core.tools.base_tool import ToolResult

if TYPE_CHECKING:
    from core.goal_hierarchy import GoalNode

log = logging.getLogger("digital_being.tools.executor")


class ToolAwareExecutor:
    """
    Extension for GoalExecutor that uses ToolRegistry.
    
    This can be mixed into GoalExecutor to add tool execution capabilities.
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
    
    async def execute_tool_action(
        self, action: "GoalNode"
    ) -> Tuple[bool, Any]:
        """
        Execute action using Tool Registry.
        
        Args:
            action: GoalNode with action_type and action_params
        
        Returns:
            (success, result)
        """
        action_type = action.action_type
        params = action.action_params or {}
        
        # Map action_type to tool name
        tool_name = self._map_action_to_tool(action_type)
        
        if not tool_name:
            log.warning(f"No tool mapping for action_type: {action_type}")
            return False, f"Unknown action_type: {action_type}"
        
        # Execute tool
        log.info(
            f"Executing tool '{tool_name}' with params: "
            f"{list(params.keys())}"
        )
        
        result: ToolResult = await self._tool_registry.execute(
            tool_name, **params
        )
        
        if result.success:
            log.info(
                f"Tool '{tool_name}' succeeded. "
                f"Cost: {result.cost}"
            )
            return True, result.data
        else:
            log.warning(
                f"Tool '{tool_name}' failed: {result.error}"
            )
            return False, result.error
    
    def _map_action_to_tool(self, action_type: str) -> Optional[str]:
        """Map action_type to tool name."""
        # Direct mapping
        mapping = {
            "web_search": "web_search",
            "read_url": "read_url",
            "read_file": "file_read",
            "write_file": "file_write",
            "python_execute": "python_execute",
            "json_parse": "json_parse",
        }
        
        return mapping.get(action_type)
    
    def get_tool_capabilities_prompt(self) -> str:
        """
        Get prompt description of available tools.
        
        Returns:
            Formatted string for LLM prompts
        """
        return self._tool_registry.to_prompt_description()