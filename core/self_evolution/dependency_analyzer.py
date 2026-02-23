"""
Digital Being — Dependency Analyzer
Stage 30.5: Analyzes code dependencies to assess change impact.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.dependency_analyzer")

class DependencyAnalyzer:
    """
    Analyzes dependencies between modules to predict change impact.
    
    Features:
    - Import dependency mapping
    - Impact assessment (what will break)
    - Circular dependency detection
    - Dependency graph visualization
    - Risk scoring based on dependents
    """
    
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._dependency_graph: dict[str, set[str]] = {}  # module -> imports
        self._reverse_graph: dict[str, set[str]] = {}     # module -> imported_by
        self._analysis_count = 0
        
        log.info("DependencyAnalyzer initialized")
    
    def analyze_module_dependencies(
        self,
        module_name: str,
        code: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze dependencies for a module.
        
        Args:
            module_name: Module to analyze
            code: Module code (if not provided, reads from file)
        
        Returns:
            Dependency information
        """
        self._analysis_count += 1
        
        # Get code
        if code is None:
            module_path = self._get_module_path(module_name)
            if not module_path.exists():
                return {
                    "success": False,
                    "error": f"Module file not found: {module_path}"
                }
            code = module_path.read_text(encoding="utf-8")
        
        try:
            # Parse AST
            tree = ast.parse(code)
            
            # Extract imports
            imports = self._extract_imports(tree)
            
            # Build dependency graph
            self._dependency_graph[module_name] = set(imports)
            
            # Update reverse graph
            for imported in imports:
                if imported not in self._reverse_graph:
                    self._reverse_graph[imported] = set()
                self._reverse_graph[imported].add(module_name)
            
            log.info(f"Analyzed {module_name}: {len(imports)} dependencies")
            
            return {
                "success": True,
                "module_name": module_name,
                "dependencies": list(imports),
                "dependency_count": len(imports)
            }
        
        except Exception as e:
            log.error(f"Failed to analyze dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def assess_change_impact(
        self,
        module_name: str,
        change_type: str = "update"
    ) -> dict[str, Any]:
        """
        Assess the impact of changing a module.
        
        Args:
            module_name: Module being changed
            change_type: Type of change (create, update, delete)
        
        Returns:
            Impact assessment with affected modules
        """
        # Find all modules that depend on this one
        affected_modules = self._reverse_graph.get(module_name, set())
        
        # Calculate impact depth (how many levels affected)
        impact_tree = self._build_impact_tree(module_name)
        max_depth = self._get_tree_depth(impact_tree)
        
        # Calculate risk score
        risk_score = self._calculate_impact_risk(
            direct_dependents=len(affected_modules),
            max_depth=max_depth,
            change_type=change_type
        )
        
        result = {
            "module_name": module_name,
            "change_type": change_type,
            "direct_dependents": list(affected_modules),
            "dependent_count": len(affected_modules),
            "impact_depth": max_depth,
            "impact_tree": impact_tree,
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "recommendation": self._get_recommendation(risk_score, change_type)
        }
        
        log.info(
            f"Impact assessment for {module_name}: "
            f"{len(affected_modules)} dependents, "
            f"depth={max_depth}, risk={risk_score:.2f}"
        )
        
        return result
    
    def detect_circular_dependencies(self) -> list[list[str]]:
        """
        Detect circular dependencies in the project.
        
        Returns:
            List of circular dependency chains
        """
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(module: str, path: list[str]) -> None:
            visited.add(module)
            rec_stack.add(module)
            path.append(module)
            
            for dep in self._dependency_graph.get(module, set()):
                if dep not in visited:
                    dfs(dep, path.copy())
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    cycles.append(cycle)
            
            rec_stack.remove(module)
        
        # Check all modules
        for module in self._dependency_graph:
            if module not in visited:
                dfs(module, [])
        
        if cycles:
            log.warning(f"Found {len(cycles)} circular dependencies")
        
        return cycles
    
    def get_module_importance(self, module_name: str) -> dict[str, Any]:
        """
        Calculate how important a module is based on dependents.
        
        Args:
            module_name: Module to assess
        
        Returns:
            Importance metrics
        """
        # Direct dependents
        direct = len(self._reverse_graph.get(module_name, set()))
        
        # Transitive dependents (all modules affected)
        transitive = len(self._get_all_dependents(module_name))
        
        # Importance score (0-1)
        total_modules = len(self._dependency_graph)
        importance = transitive / max(total_modules, 1)
        
        return {
            "module_name": module_name,
            "direct_dependents": direct,
            "transitive_dependents": transitive,
            "importance_score": importance,
            "importance_level": self._get_importance_level(importance)
        }
    
    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        # Filter to only project modules (starting with 'core.')
        project_imports = [
            imp for imp in imports
            if imp.startswith('core.')
        ]
        
        return project_imports
    
    def _build_impact_tree(
        self,
        module: str,
        visited: set[str] | None = None
    ) -> dict[str, Any]:
        """Build tree of modules affected by changes."""
        if visited is None:
            visited = set()
        
        if module in visited:
            return {"module": module, "circular": True}
        
        visited.add(module)
        
        dependents = self._reverse_graph.get(module, set())
        children = []
        
        for dep in dependents:
            child_tree = self._build_impact_tree(dep, visited.copy())
            children.append(child_tree)
        
        return {
            "module": module,
            "children": children
        }
    
    def _get_tree_depth(self, tree: dict[str, Any]) -> int:
        """Get maximum depth of impact tree."""
        if not tree.get("children"):
            return 1
        
        max_child_depth = max(
            self._get_tree_depth(child)
            for child in tree["children"]
        )
        
        return 1 + max_child_depth
    
    def _get_all_dependents(self, module: str) -> set[str]:
        """Get all modules that transitively depend on this module."""
        result = set()
        queue = [module]
        
        while queue:
            current = queue.pop(0)
            dependents = self._reverse_graph.get(current, set())
            
            for dep in dependents:
                if dep not in result:
                    result.add(dep)
                    queue.append(dep)
        
        return result
    
    def _calculate_impact_risk(
        self,
        direct_dependents: int,
        max_depth: int,
        change_type: str
    ) -> float:
        """Calculate risk score for change impact (0.0 - 1.0)."""
        # Base risk from dependents
        dependent_risk = min(direct_dependents / 10.0, 0.5)
        
        # Add risk from depth
        depth_risk = min(max_depth / 5.0, 0.3)
        
        # Add risk from change type
        type_risk = {
            "create": 0.0,
            "update": 0.1,
            "delete": 0.2
        }.get(change_type, 0.1)
        
        return min(dependent_risk + depth_risk + type_risk, 1.0)
    
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
    
    def _get_importance_level(self, importance: float) -> str:
        """Convert importance score to level."""
        if importance >= 0.5:
            return "critical"
        elif importance >= 0.3:
            return "high"
        elif importance >= 0.1:
            return "medium"
        else:
            return "low"
    
    def _get_recommendation(self, risk_score: float, change_type: str) -> str:
        """Get recommendation based on risk."""
        if risk_score >= 0.7:
            return "High risk change. Require manual approval and extensive testing."
        elif risk_score >= 0.5:
            return "Moderate risk. Test all dependent modules before deployment."
        elif risk_score >= 0.3:
            return "Low-moderate risk. Standard testing recommended."
        else:
            return "Low risk. Safe to proceed with normal validation."
    
    def _get_module_path(self, module_name: str) -> Path:
        """Get file path for a module."""
        # Convert module name to path
        # e.g., 'core.vector_memory' -> 'core/vector_memory.py'
        parts = module_name.split('.')
        return self._project_root / Path(*parts[:-1]) / f"{parts[-1]}.py"
    
    def rebuild_full_graph(self) -> dict[str, Any]:
        """Rebuild complete dependency graph for entire project."""
        log.info("Rebuilding full dependency graph...")
        
        self._dependency_graph.clear()
        self._reverse_graph.clear()
        
        module_count = 0
        core_path = self._project_root / "core"
        
        if not core_path.exists():
            return {
                "success": False,
                "error": "Core directory not found"
            }
        
        # Scan all Python files
        for py_file in core_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            # Convert path to module name
            rel_path = py_file.relative_to(self._project_root)
            module_name = str(rel_path.with_suffix("")).replace("/", ".")
            
            self.analyze_module_dependencies(module_name)
            module_count += 1
        
        log.info(f"Rebuilt graph with {module_count} modules")
        
        return {
            "success": True,
            "modules_analyzed": module_count,
            "total_dependencies": sum(
                len(deps) for deps in self._dependency_graph.values()
            )
        }
    
    def get_stats(self) -> dict[str, Any]:
        """Get analyzer statistics."""
        circular = len(self.detect_circular_dependencies())
        
        return {
            "analyses_performed": self._analysis_count,
            "modules_tracked": len(self._dependency_graph),
            "circular_dependencies": circular,
            "avg_dependencies": sum(
                len(deps) for deps in self._dependency_graph.values()
            ) / max(len(self._dependency_graph), 1)
        }
