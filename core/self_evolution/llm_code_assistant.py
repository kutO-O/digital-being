"""
Digital Being — LLM Code Assistant
Stage 30.1: Intelligent code generation using Ollama LLM.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.ollama_client import OllamaClient

log = logging.getLogger("digital_being.llm_code_assistant")

class LLMCodeAssistant:
    """
    Uses LLM to generate intelligent code modifications.
    
    Features:
    - Context-aware code generation
    - Bug fix suggestions
    - Optimization recommendations
    - Code explanation and documentation
    """
    
    def __init__(self, ollama_client: OllamaClient) -> None:
        self._client = ollama_client
        self._generation_count = 0
        self._success_count = 0
        
        log.info("LLMCodeAssistant initialized")
    
    async def generate_module_code(
        self,
        module_name: str,
        description: str,
        existing_code: str | None = None,
        requirements: list[str] | None = None,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Generate module code using LLM.
        
        Args:
            module_name: Name of the module
            description: What the module should do
            existing_code: Existing code to modify (if any)
            requirements: Specific requirements
            context: Additional context (imports, dependencies, etc.)
        
        Returns:
            Generation result with code and metadata
        """
        self._generation_count += 1
        
        # Build prompt
        prompt = self._build_generation_prompt(
            module_name=module_name,
            description=description,
            existing_code=existing_code,
            requirements=requirements or [],
            context=context or {}
        )
        
        try:
            # Generate code using LLM
            response = await self._client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python developer. Generate clean, efficient, and well-documented code."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False
            )
            
            generated_code = response["message"]["content"]
            
            # Extract code from markdown if present
            code = self._extract_code_from_response(generated_code)
            
            # Validate basic syntax
            is_valid, error = self._validate_syntax(code)
            
            if is_valid:
                self._success_count += 1
                log.info(f"Successfully generated code for {module_name}")
                
                return {
                    "success": True,
                    "code": code,
                    "raw_response": generated_code,
                    "metadata": {
                        "module_name": module_name,
                        "description": description,
                        "generated_at": response.get("created_at"),
                        "model": self._client._strategy_model
                    }
                }
            else:
                log.warning(f"Generated code has syntax errors: {error}")
                return {
                    "success": False,
                    "error": f"Syntax validation failed: {error}",
                    "code": code,
                    "raw_response": generated_code
                }
        
        except Exception as e:
            log.error(f"Failed to generate code: {e}")
            return {
                "success": False,
                "error": str(e),
                "code": None
            }
    
    async def suggest_bug_fix(
        self,
        module_name: str,
        code: str,
        error_message: str,
        stack_trace: str | None = None
    ) -> dict[str, Any]:
        """
        Suggest a bug fix for existing code.
        
        Args:
            module_name: Module name
            code: Current code with bug
            error_message: Error message
            stack_trace: Optional stack trace
        
        Returns:
            Suggested fix with explanation
        """
        prompt = f"""Fix the following Python code that has an error.

Module: {module_name}

Current Code:
```python
{code}
```

Error: {error_message}

{f'Stack Trace:\n{stack_trace}\n' if stack_trace else ''}
Provide the corrected code with explanation of the fix.
"""
        
        try:
            response = await self._client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python debugger. Provide clear, working fixes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False
            )
            
            result = response["message"]["content"]
            fixed_code = self._extract_code_from_response(result)
            
            return {
                "success": True,
                "fixed_code": fixed_code,
                "explanation": result,
                "original_error": error_message
            }
        
        except Exception as e:
            log.error(f"Failed to suggest bug fix: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def suggest_optimization(
        self,
        module_name: str,
        code: str,
        performance_metrics: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Suggest code optimizations.
        
        Args:
            module_name: Module name
            code: Current code
            performance_metrics: Optional performance data
        
        Returns:
            Optimized code with explanation
        """
        metrics_text = ""
        if performance_metrics:
            metrics_text = f"\n\nCurrent Performance:\n{json.dumps(performance_metrics, indent=2)}"
        
        prompt = f"""Optimize the following Python code for better performance and maintainability.

Module: {module_name}

Current Code:
```python
{code}
```{metrics_text}

Provide optimized code with explanation of improvements.
"""
        
        try:
            response = await self._client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python performance optimizer. Focus on efficiency and readability."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False
            )
            
            result = response["message"]["content"]
            optimized_code = self._extract_code_from_response(result)
            
            return {
                "success": True,
                "optimized_code": optimized_code,
                "explanation": result,
                "original_metrics": performance_metrics
            }
        
        except Exception as e:
            log.error(f"Failed to suggest optimization: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_generation_prompt(
        self,
        module_name: str,
        description: str,
        existing_code: str | None,
        requirements: list[str],
        context: dict[str, Any]
    ) -> str:
        """Build LLM prompt for code generation."""
        prompt_parts = []
        
        if existing_code:
            prompt_parts.append(f"Modify the following Python module:\n\n```python\n{existing_code}\n```\n")
        else:
            prompt_parts.append(f"Create a new Python module named '{module_name}'.\n")
        
        prompt_parts.append(f"\nDescription: {description}\n")
        
        if requirements:
            prompt_parts.append("\nRequirements:")
            for req in requirements:
                prompt_parts.append(f"- {req}")
            prompt_parts.append("")
        
        if context:
            if "imports" in context:
                prompt_parts.append(f"\nRequired imports: {', '.join(context['imports'])}")
            if "base_class" in context:
                prompt_parts.append(f"Base class: {context['base_class']}")
            if "interfaces" in context:
                prompt_parts.append(f"Interfaces: {', '.join(context['interfaces'])}")
        
        prompt_parts.append("\nProvide complete, production-ready Python code with:")
        prompt_parts.append("- Type hints")
        prompt_parts.append("- Docstrings")
        prompt_parts.append("- Error handling")
        prompt_parts.append("- Logging")
        prompt_parts.append("- Clean, efficient implementation")
        
        return "\n".join(prompt_parts)
    
    def _extract_code_from_response(self, response: str) -> str:
        """Extract Python code from LLM response (removing markdown)."""
        # Look for code blocks
        if "```python" in response:
            start = response.find("```python") + len("```python")
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()
        
        # No code blocks found, return as-is
        return response.strip()
    
    def _validate_syntax(self, code: str) -> tuple[bool, str | None]:
        """Validate Python syntax."""
        try:
            compile(code, "<string>", "exec")
            return True, None
        except SyntaxError as e:
            return False, str(e)
    
    def get_stats(self) -> dict[str, Any]:
        """Get assistant statistics."""
        success_rate = 0.0
        if self._generation_count > 0:
            success_rate = self._success_count / self._generation_count
        
        return {
            "generations": self._generation_count,
            "successful": self._success_count,
            "success_rate": success_rate
        }
