"""Core components for fault-tolerant architecture."""

from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from core.health_monitor import HealthMonitor, HealthStatus
from core.fallback_cache import FallbackCache, FallbackStrategy, CacheEntry
from core.priority_budget import PriorityBudgetSystem, Priority, BudgetConfig, BudgetUsage
from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick