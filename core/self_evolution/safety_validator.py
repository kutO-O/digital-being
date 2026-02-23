"""
Digital Being — Safety Validator
Stage 30.2: Validates code safety before execution.
"""

from __future__ import annotations

import ast
import logging
from typing import Any

log = logging.getLogger("digital_being.safety_validator")

class SafetyValidator:
    """
    Validates code safety before execution.
    
    Features:
    - AST-based security analysis
    - Dangerous pattern detection
    - Import restrictions
    - Resource usage limits
    - Risk scoring
    """
    
    # Dangerous modules that should be restricted
    DANGEROUS_MODULES = {
        "os.system", "subprocess", "eval", "exec", "compile",
        "__import__", "open", "file", "input", "raw_input",
        "socket", "urllib", "requests", "http", "ftplib",
        "shutil.rmtree", "os.remove", "os.rmdir", "pathlib.Path.unlink"
    }
    
    # Allowed safe modules
    SAFE_MODULES = {
        "json", "time", "datetime", "math", "random", "re",
        "collections", "itertools", "functools", "typing",
        "dataclasses", "enum", "pathlib", "logging"
    }
    
    # Dangerous AST node types
    DANGEROUS_NODES = {
        ast.Import,
        ast.ImportFrom,
        ast.Exec,  # Python 2
    }
    
    def __init__(self) -> None:
        self._validations = 0
        self._passed = 0
        self._failed = 0
        
        log.info("SafetyValidator initialized")
    
    def validate_code(self, code: str, module_name: str) -> dict[str, Any]:
        """
        Validate code safety.
        
        Args:
            code: Python code to validate
            module_name: Module name for context
        
        Returns:
            Validation result with risk score and issues
        """
        self._validations += 1
        
        issues = []
        warnings = []
        risk_score = 0.0
        
        try:
            # Parse code to AST
            tree = ast.parse(code)
            
            # Check for dangerous patterns
            issues.extend(self._check_dangerous_imports(tree))
            issues.extend(self._check_dangerous_calls(tree))
            issues.extend(self._check_file_operations(tree))
            issues.extend(self._check_network_operations(tree))
            
            warnings.extend(self._check_resource_usage(tree))
            warnings.extend(self._check_code_complexity(tree))
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(issues, warnings)
            
            # Determine if code is safe
            is_safe = risk_score < 0.5 and len(issues) == 0
            
            if is_safe:
                self._passed += 1
            else:
                self._failed += 1
            
            result = {
                "safe": is_safe,
                "risk_score": risk_score,
                "risk_level": self._get_risk_level(risk_score),
                "issues": issues,
                "warnings": warnings,
                "module_name": module_name
            }
            
            if not is_safe:
                log.warning(
                    f"Code validation failed for {module_name}: "
                    f"risk={risk_score:.2f}, issues={len(issues)}"
                )
            else:
                log.info(f"Code validation passed for {module_name}")
            
            return result
        
        except SyntaxError as e:
            self._failed += 1
            return {
                "safe": False,
                "risk_score": 1.0,
                "risk_level": "critical",
                "issues": [{"type": "syntax_error", "message": str(e)}],
                "warnings": [],
                "module_name": module_name
            }
        except Exception as e:
            self._failed += 1
            log.error(f"Validation error: {e}")
            return {
                "safe": False,
                "risk_score": 1.0,
                "risk_level": "critical",
                "issues": [{"type": "validation_error", "message": str(e)}],
                "warnings": [],
                "module_name": module_name
            }
    
    def _check_dangerous_imports(self, tree: ast.AST) -> list[dict[str, str]]:
        """Check for dangerous imports."""
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(danger in alias.name for danger in self.DANGEROUS_MODULES):
                        issues.append({
                            "type": "dangerous_import",
                            "message": f"Dangerous import detected: {alias.name}",
                            "line": node.lineno
                        })
            
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(danger in node.module for danger in self.DANGEROUS_MODULES):
                    issues.append({
                        "type": "dangerous_import",
                        "message": f"Dangerous import detected: {node.module}",
                        "line": node.lineno
                    })
        
        return issues
    
    def _check_dangerous_calls(self, tree: ast.AST) -> list[dict[str, str]]:
        """Check for dangerous function calls."""
        issues = []
        dangerous_funcs = {"eval", "exec", "compile", "__import__"}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in dangerous_funcs:
                    issues.append({
                        "type": "dangerous_call",
                        "message": f"Dangerous function call: {func_name}()",
                        "line": node.lineno
                    })
        
        return issues
    
    def _check_file_operations(self, tree: ast.AST) -> list[dict[str, str]]:
        """Check for file operations."""
        issues = []
        file_funcs = {"open", "file", "remove", "rmdir", "unlink", "rmtree"}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in file_funcs:
                    issues.append({
                        "type": "file_operation",
                        "message": f"File operation detected: {func_name}() - requires review",
                        "line": node.lineno
                    })
        
        return issues
    
    def _check_network_operations(self, tree: ast.AST) -> list[dict[str, str]]:
        """Check for network operations."""
        issues = []
        network_modules = {"socket", "urllib", "requests", "http", "ftplib"}
        
        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module] if node.module else []
                
                for name in names:
                    if any(net in name for net in network_modules):
                        issues.append({
                            "type": "network_operation",
                            "message": f"Network module detected: {name} - requires review",
                            "line": node.lineno
                        })
        
        return issues
    
    def _check_resource_usage(self, tree: ast.AST) -> list[dict[str, str]]:
        """Check for potential resource usage issues."""
        warnings = []
        
        # Check for infinite loops
        for node in ast.walk(tree):
            if isinstance(node, ast.While):
                # Simple check for 'while True:'
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    warnings.append({
                        "type": "infinite_loop",
                        "message": "Potential infinite loop detected",
                        "line": node.lineno
                    })
        
        return warnings
    
    def _check_code_complexity(self, tree: ast.AST) -> list[dict[str, str]]:
        """Check code complexity."""
        warnings = []
        
        # Count functions
        func_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        
        # Count classes
        class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        
        # Warn if too complex
        if func_count > 20:
            warnings.append({
                "type": "complexity",
                "message": f"High function count: {func_count} functions"
            })
        
        if class_count > 10:
            warnings.append({
                "type": "complexity",
                "message": f"High class count: {class_count} classes"
            })
        
        return warnings
    
    def _get_call_name(self, call_node: ast.Call) -> str:
        """Extract function name from call node."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return ""
    
    def _calculate_risk_score(self, issues: list[dict], warnings: list[dict]) -> float:
        """Calculate overall risk score (0.0 - 1.0)."""
        # Base score
        score = 0.0
        
        # Add score for each issue type
        for issue in issues:
            if issue["type"] == "dangerous_import":
                score += 0.3
            elif issue["type"] == "dangerous_call":
                score += 0.4
            elif issue["type"] == "file_operation":
                score += 0.2
            elif issue["type"] == "network_operation":
                score += 0.2
            elif issue["type"] == "syntax_error":
                score += 0.5
        
        # Add smaller score for warnings
        for warning in warnings:
            score += 0.05
        
        # Cap at 1.0
        return min(score, 1.0)
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to level."""
        if risk_score >= 0.7:
            return "critical"
        elif risk_score >= 0.5:
            return "high"
        elif risk_score >= 0.3:
            return "medium"
        else:
            return "low"
    
    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics."""
        pass_rate = 0.0
        if self._validations > 0:
            pass_rate = self._passed / self._validations
        
        return {
            "validations": self._validations,
            "passed": self._passed,
            "failed": self._failed,
            "pass_rate": pass_rate
        }
