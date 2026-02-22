"""Tool Registry - Discovery and management of tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from core.tools.base_tool import BaseTool, ToolCategory, ToolResult

log = logging.getLogger("digital_being.tools.registry")


class ToolRegistry:
    """Registry for tool discovery and management."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tools_by_category: Dict[ToolCategory, List[BaseTool]] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            log.warning(f"Tool '{tool.name}' already registered, replacing")

        self._tools[tool.name] = tool

        if tool.category not in self._tools_by_category:
            self._tools_by_category[tool.category] = []
        if tool not in self._tools_by_category[tool.category]:
            self._tools_by_category[tool.category].append(tool)

        log.info(f"Registered tool: {tool.name} ({tool.category.value})")

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool."""
        if tool_name not in self._tools:
            return

        tool = self._tools[tool_name]
        del self._tools[tool_name]

        if tool.category in self._tools_by_category:
            self._tools_by_category[tool.category].remove(tool)

        log.info(f"Unregistered tool: {tool_name}")

    def get(self, tool_name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(tool_name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[BaseTool]:
        """List all tools or tools in specific category."""
        if category:
            return self._tools_by_category.get(category, [])
        return list(self._tools.values())

    def search(self, query: str, category: Optional[ToolCategory] = None) -> List[BaseTool]:
        """
        Search tools by query string.

        Args:
            query: Search query (matches name or description)
            category: Optional category filter

        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        tools = self.list_tools(category)

        matches = []
        for tool in tools:
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                matches.append(tool)

        return matches

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute tool by name.

        Args:
            tool_name: Name of tool to execute
            **kwargs: Parameters for the tool

        Returns:
            ToolResult
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' not found",
                cost=0,
            )

        return await tool.safe_execute(**kwargs)

    def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities of all registered tools."""
        return {
            "total_tools": len(self._tools),
            "by_category": {
                cat.value: len(tools)
                for cat, tools in self._tools_by_category.items()
            },
            "tools": [
                tool.get_capabilities()
                for tool in self._tools.values()
            ],
        }

    def to_prompt_description(self, category: Optional[ToolCategory] = None) -> str:
        """
        Generate description for LLM prompts.

        Args:
            category: Optional category filter

        Returns:
            Formatted tool descriptions
        """
        tools = self.list_tools(category)

        if not tools:
            return "No tools available."

        lines = ["Available tools:"]
        for tool in tools:
            lines.append(f"- {tool.to_prompt_description()}")

        return "\n".join(lines)

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for all tools."""
        total_executions = sum(
            t._execution_count for t in self._tools.values()
        )
        total_successes = sum(
            t._success_count for t in self._tools.values()
        )
        total_cost = sum(
            t._total_cost for t in self._tools.values()
        )

        return {
            "total_tools": len(self._tools),
            "total_executions": total_executions,
            "total_successes": total_successes,
            "total_failures": total_executions - total_successes,
            "success_rate": (
                total_successes / total_executions
                if total_executions > 0
                else 0
            ),
            "total_cost": total_cost,
            "by_tool": {
                name: tool.get_capabilities()["stats"]
                for name, tool in self._tools.items()
            },
        }
