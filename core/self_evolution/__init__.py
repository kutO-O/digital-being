"""
Digital Being — Self-Evolution Module
Stage 30: Self-improvement and code evolution system.
"""

from core.self_evolution.self_evolution_manager import (
    SelfEvolutionManager,
    EvolutionMode,
    ChangeType
)

from core.self_evolution.llm_code_assistant import LLMCodeAssistant
from core.self_evolution.safety_validator import SafetyValidator
from core.self_evolution.performance_monitor import PerformanceMonitor
from core.self_evolution.auto_rollback import AutoRollbackHandler

__all__ = [
    "SelfEvolutionManager",
    "EvolutionMode",
    "ChangeType",
    "LLMCodeAssistant",
    "SafetyValidator",
    "PerformanceMonitor",
    "AutoRollbackHandler",
]
