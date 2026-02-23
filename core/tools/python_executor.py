"""Python code execution tool with sandboxed environment."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.base_tool import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
)

log = logging.getLogger("digital_being.tools.python_executor")


class PythonExecutorTool(BaseTool):
    """Execute Python code in a sandboxed environment."""
    
    def __init__(self, allowed_dir: Path, memory_dir: Path):
        super().__init__()
        self._allowed_dir = allowed_dir.resolve()
        self._memory_dir = memory_dir
        self._stats_path = memory_dir / "python_executor_stats.json"
        self._stats = self._load_stats()
        
        # Persistent namespace for REPL-like behavior
        self._namespace: Dict[str, Any] = {
            "__builtins__": __builtins__,
        }
        
        # Whitelist of safe modules
        self._safe_modules = {
            "math", "random", "datetime", "json", "re", "itertools",
            "collections", "functools", "operator", "string", "textwrap",
            "pathlib", "csv", "base64", "hashlib", "uuid",
        }
        
        log.info(f"PythonExecutor initialized. allowed_dir={self._allowed_dir}")
    
    @property
    def name(self) -> str:
        return "python_execute"
    
    @property
    def description(self) -> str:
        return "Execute Python code in sandboxed environment with persistent namespace"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMPUTE
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="Python code to execute",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="int",
                description="Execution timeout in seconds",
                required=False,
                default=5,
            ),
            ToolParameter(
                name="reset_namespace",
                type="bool",
                description="Reset namespace before execution",
                required=False,
                default=False,
            ),
        ]
    
    def _load_stats(self) -> dict:
        """Load execution statistics."""
        if not self._stats_path.exists():
            return {"total_executed": 0, "total_errors": 0, "total_timeouts": 0}
        try:
            return json.loads(self._stats_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._stats_path}: {e}")
            return {"total_executed": 0, "total_errors": 0, "total_timeouts": 0}
    
    def _save_stats(self) -> None:
        """Save execution statistics."""
        try:
            self._memory_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._stats_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._stats, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._stats_path)
        except OSError as e:
            log.error(f"Failed to save {self._stats_path}: {e}")
    
    def _validate_code(self, code: str) -> tuple[bool, str]:
        """Basic validation of Python code."""
        if not code or not code.strip():
            return False, "empty code"
        
        # Blacklist dangerous operations
        dangerous_patterns = [
            "__import__",
            "eval(",
            "exec(",
            "compile(",
            "open(",  # File access restricted
            "subprocess",
            "os.system",
            "os.popen",
            "os.exec",
            "os.spawn",
            "shutil",
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                return False, f"dangerous operation '{pattern}' detected"
        
        return True, ""
    
    def _execute_code(self, code: str, timeout: int, reset_namespace: bool) -> dict:
        """Execute Python code synchronously."""
        if reset_namespace:
            self._namespace = {"__builtins__": __builtins__}
        
        # Prepare I/O capture
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        start_time = time.monotonic()
        result_value = None
        
        try:
            # Compile code
            compiled = compile(code, "<sandbox>", "exec")
            
            # Execute with I/O redirection
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(compiled, self._namespace)
            
            # Try to get result if last line is expression
            try:
                lines = code.strip().split('\n')
                last_line = lines[-1].strip()
                if last_line and not last_line.startswith(("import", "from", "def", "class", "if", "for", "while", "with", "try")):
                    result_value = eval(last_line, self._namespace)
            except:
                pass
            
            execution_time_ms = int((time.monotonic() - start_time) * 1000)
            
            return {
                "success": True,
                "stdout": stdout_capture.getvalue()[:5000],
                "stderr": stderr_capture.getvalue()[:1000],
                "result": str(result_value) if result_value is not None else None,
                "execution_time_ms": execution_time_ms,
                "namespace_vars": list(k for k in self._namespace.keys() if not k.startswith("_")),
            }
        
        except Exception as e:
            execution_time_ms = int((time.monotonic() - start_time) * 1000)
            
            # Get traceback
            tb = traceback.format_exc()
            
            return {
                "success": False,
                "stdout": stdout_capture.getvalue()[:5000],
                "stderr": tb[:2000],
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "namespace_vars": list(k for k in self._namespace.keys() if not k.startswith("_")),
            }
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute Python code asynchronously."""
        code = kwargs["code"]
        timeout = kwargs.get("timeout", 5)
        reset_namespace = kwargs.get("reset_namespace", False)
        
        # Validate code
        valid, reason = self._validate_code(code)
        if not valid:
            self._stats["total_errors"] += 1
            self._save_stats()
            
            log.warning(f"Python code rejected: {reason}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Rejected: {reason}",
                cost=0,
            )
        
        try:
            loop = asyncio.get_event_loop()
            
            # Execute with timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._execute_code, code, timeout, reset_namespace),
                timeout=timeout + 1,  # Add 1 sec buffer
            )
            
            if result["success"]:
                self._stats["total_executed"] += 1
                log.info(f"Python code executed successfully in {result['execution_time_ms']}ms")
            else:
                self._stats["total_errors"] += 1
                log.error(f"Python code error: {result.get('error', 'Unknown')}")
            
            self._save_stats()
            
            return ToolResult(
                success=result["success"],
                data=result,
                metadata={"source": "python_executor"},
                cost=2,
            )
        
        except asyncio.TimeoutError:
            self._stats["total_timeouts"] += 1
            self._save_stats()
            
            log.error(f"Python code timeout after {timeout}s")
            return ToolResult(
                success=False,
                data=None,
                error=f"Execution timeout ({timeout}s)",
                cost=1,
            )
        
        except Exception as e:
            self._stats["total_errors"] += 1
            self._save_stats()
            
            log.error(f"Python execution failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error: {str(e)}",
                cost=1,
            )
    
    def get_stats(self) -> dict:
        """Get execution statistics."""
        return dict(self._stats)
    
    def reset_namespace(self) -> None:
        """Reset the execution namespace."""
        self._namespace = {"__builtins__": __builtins__}
        log.info("Python executor namespace reset")
    
    def get_namespace_vars(self) -> list[str]:
        """Get list of variables in namespace."""
        return [k for k in self._namespace.keys() if not k.startswith("_")]
