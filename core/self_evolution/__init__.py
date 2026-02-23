"""
Digital Being — Self-Evolution Module
Stage 30 Enhanced: Complete self-improvement and code evolution system.
"""

# Core components
from core.self_evolution.self_evolution_manager import (
    SelfEvolutionManager,
    EvolutionMode,
    ChangeType
)

# Priority 1: Critical safety and intelligence
from core.self_evolution.llm_code_assistant import LLMCodeAssistant
from core.self_evolution.safety_validator import SafetyValidator
from core.self_evolution.performance_monitor import PerformanceMonitor
from core.self_evolution.auto_rollback import AutoRollbackHandler

# Priority 2: Advanced features
from core.self_evolution.dependency_analyzer import DependencyAnalyzer
from core.self_evolution.priority_queue import PriorityQueue, ChangeRequest
from core.self_evolution.evolution_rate_limiter import EvolutionRateLimiter
from core.self_evolution.canary_deployment import CanaryDeployment, DeploymentStage

__all__ = [
    # Core
    "SelfEvolutionManager",
    "EvolutionMode",
    "ChangeType",
    # Priority 1
    "LLMCodeAssistant",
    "SafetyValidator",
    "PerformanceMonitor",
    "AutoRollbackHandler",
    # Priority 2
    "DependencyAnalyzer",
    "PriorityQueue",
    "ChangeRequest",
    "EvolutionRateLimiter",
    "CanaryDeployment",
    "DeploymentStage",
]
