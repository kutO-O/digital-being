"""Tool Registry System."""

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)
from core.tools.registry import ToolRegistry
from core.tools.builtin_tools import (
    WebSearchTool,
    ReadUrlTool,
    FileReadTool,
    FileWriteTool,
    PythonExecuteTool,
    JSONParseTool,
)

__all__ = [
    "BaseTool",
    "ToolCategory",
    "ToolParameter",
    "ToolResult",
    "ToolRegistry",
    "WebSearchTool",
    "ReadUrlTool",
    "FileReadTool",
    "FileWriteTool",
    "PythonExecuteTool",
    "JSONParseTool",
    "initialize_default_tools",
]


def initialize_default_tools(
    registry: ToolRegistry,
    allowed_dirs: list = None,
) -> None:
    """
    Initialize and register default tools.
    
    Args:
        registry: ToolRegistry instance
        allowed_dirs: List of allowed directories for file operations
    """
    from pathlib import Path
    
    if allowed_dirs is None:
        # Default: data directory
        allowed_dirs = [
            Path("data"),
            Path("data/sandbox"),
            Path("data/goals"),
        ]
    
    # Web tools
    registry.register(WebSearchTool())
    registry.register(ReadUrlTool())
    
    # File tools
    registry.register(FileReadTool(allowed_dirs))
    registry.register(FileWriteTool(allowed_dirs))
    
    # Code tools
    registry.register(PythonExecuteTool())
    
    # Data tools
    registry.register(JSONParseTool())