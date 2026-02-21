"""Base Tool class for Tool Registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger("digital_being.tools.base_tool")


class ToolCategory(Enum):
    """Tool category for organization."""
    WEB = "web"
    FILE = "file"
    CODE = "code"
    API = "api"
    DATA = "data"
    SYSTEM = "system"
    COMMUNICATION = "communication"


@dataclass
class ToolParameter:
    """Tool parameter specification."""
    name: str
    type: str  # "string", "int", "float", "bool", "list", "dict"
    description: str
    required: bool = True
    default: Any = None
    validation: Optional[Dict[str, Any]] = None  # e.g. {"min": 0, "max": 100}


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    cost: int = 1  # Cost in arbitrary units (for budgeting)


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    def __init__(self):
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_cost = 0
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (unique identifier)."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass
    
    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """Tool category."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """List of parameters this tool accepts."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool.
        
        Args:
            **kwargs: Parameters for the tool
        
        Returns:
            ToolResult with success status and data
        """
        pass
    
    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parameters before execution.
        
        Returns:
            (is_valid, error_message)
        """
        param_specs = {p.name: p for p in self.parameters}
        
        # Check required parameters
        for param in self.parameters:
            if param.required and param.name not in params:
                if param.default is not None:
                    params[param.name] = param.default
                else:
                    return False, f"Missing required parameter: {param.name}"
        
        # Check types and validation
        for key, value in params.items():
            if key not in param_specs:
                return False, f"Unknown parameter: {key}"
            
            param_spec = param_specs[key]
            
            # Type checking
            if not self._check_type(value, param_spec.type):
                return False, (
                    f"Parameter '{key}' has wrong type. "
                    f"Expected {param_spec.type}, got {type(value).__name__}"
                )
            
            # Custom validation
            if param_spec.validation:
                valid, error = self._validate_value(value, param_spec.validation)
                if not valid:
                    return False, f"Parameter '{key}': {error}"
        
        return True, None
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "string": str,
            "int": int,
            "float": (int, float),
            "bool": bool,
            "list": list,
            "dict": dict,
            "any": object,
        }
        
        expected = type_map.get(expected_type, object)
        return isinstance(value, expected)
    
    def _validate_value(self, value: Any, rules: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate value against rules."""
        if "min" in rules and value < rules["min"]:
            return False, f"Value must be >= {rules['min']}"
        if "max" in rules and value > rules["max"]:
            return False, f"Value must be <= {rules['max']}"
        if "min_length" in rules and len(value) < rules["min_length"]:
            return False, f"Length must be >= {rules['min_length']}"
        if "max_length" in rules and len(value) > rules["max_length"]:
            return False, f"Length must be <= {rules['max_length']}"
        if "pattern" in rules:
            import re
            if not re.match(rules["pattern"], str(value)):
                return False, f"Value does not match pattern {rules['pattern']}"
        if "allowed_values" in rules and value not in rules["allowed_values"]:
            return False, f"Value must be one of {rules['allowed_values']}"
        
        return True, None
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get tool capabilities and metadata."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in self.parameters
            ],
            "stats": {
                "executions": self._execution_count,
                "successes": self._success_count,
                "failures": self._failure_count,
                "success_rate": (
                    self._success_count / self._execution_count
                    if self._execution_count > 0
                    else 0
                ),
                "total_cost": self._total_cost,
            },
        }
    
    def _record_execution(self, result: ToolResult) -> None:
        """Record execution statistics."""
        self._execution_count += 1
        if result.success:
            self._success_count += 1
        else:
            self._failure_count += 1
        self._total_cost += result.cost
    
    async def safe_execute(self, **kwargs) -> ToolResult:
        """
        Execute tool with validation and error handling.
        
        Returns:
            ToolResult
        """
        # Validate parameters
        valid, error = self.validate_parameters(kwargs)
        if not valid:
            result = ToolResult(
                success=False,
                data=None,
                error=f"Parameter validation failed: {error}",
                cost=0,
            )
            self._record_execution(result)
            return result
        
        # Execute
        try:
            result = await self.execute(**kwargs)
            self._record_execution(result)
            return result
        except Exception as e:
            log.error(f"Tool '{self.name}' execution error: {e}")
            result = ToolResult(
                success=False,
                data=None,
                error=f"Execution error: {str(e)}",
                cost=1,
            )
            self._record_execution(result)
            return result
    
    def to_prompt_description(self) -> str:
        """Generate description for LLM prompts."""
        params_str = ", ".join(
            f"{p.name}: {p.type}{'?' if not p.required else ''}"
            for p in self.parameters
        )
        return (
            f"{self.name}({params_str})\n"
            f"  {self.description}\n"
            f"  Category: {self.category.value}"
        )