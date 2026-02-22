"""
Prometheus Metrics

Полная телеметрия для production мониторинга.

Metrics:
- Counters: количество событий (не убывает)
- Gauges: текущее значение (может расти/убывать)
- Histograms: распределение значений (латенси, размеры)
- Summaries: статистика за период

Usage:
    from core.metrics import metrics
    
    # Track LLM call
    with metrics.llm_call_duration.labels(model="llama3.2").time():
        response = ollama.chat(prompt)
    
    metrics.llm_calls_total.labels(model="llama3.2", status="success").inc()
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Dummy classes for when prometheus_client is not installed
    class Counter:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def labels(self, **kwargs): return self
        def inc(self, *args, **kwargs): pass
    
    class Gauge:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def labels(self, **kwargs): return self
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
    
    class Histogram:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def labels(self, **kwargs): return self
        def observe(self, *args, **kwargs): pass
        def time(self): return _DummyTimer()
    
    class Summary:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def labels(self, **kwargs): return self
        def observe(self, *args, **kwargs): pass
    
    class _DummyTimer:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    def generate_latest(*args, **kwargs): return b""  # type: ignore
    CONTENT_TYPE_LATEST = "text/plain"  # type: ignore
    CollectorRegistry = None  # type: ignore

log = logging.getLogger("digital_being.metrics")


class MetricsCollector:
    """
    Централизованный сбор метрик.
    
    Интегрируется с Prometheus, Grafana, Datadog.
    """
    
    def __init__(self) -> None:
        if not PROMETHEUS_AVAILABLE:
            log.warning(
                "prometheus_client not installed. "
                "Metrics collection disabled. "
                "Install with: pip install prometheus-client"
            )
        
        # ============================================================
        # LLM Metrics
        # ============================================================
        
        # Call counts
        self.llm_calls_total = Counter(
            "llm_calls_total",
            "Total LLM calls",
            ["model", "operation", "status"]  # success | error | cached
        )
        
        # Latency
        self.llm_call_duration = Histogram(
            "llm_call_duration_seconds",
            "LLM call latency",
            ["model", "operation"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        # Token usage
        self.llm_tokens_used = Counter(
            "llm_tokens_used_total",
            "Total tokens processed",
            ["model", "type"]  # input | output
        )
        
        # ============================================================
        # Cache Metrics
        # ============================================================
        
        self.cache_hits_total = Counter(
            "cache_hits_total",
            "Cache hits",
            ["cache_type"]  # llm | vector | other
        )
        
        self.cache_misses_total = Counter(
            "cache_misses_total",
            "Cache misses",
            ["cache_type"]
        )
        
        self.cache_size = Gauge(
            "cache_size_entries",
            "Current cache size",
            ["cache_type"]
        )
        
        self.cache_evictions_total = Counter(
            "cache_evictions_total",
            "Cache evictions",
            ["cache_type", "reason"]  # lru | ttl | manual
        )
        
        # ============================================================
        # Circuit Breaker Metrics
        # ============================================================
        
        self.circuit_breaker_state = Gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half_open)",
            ["name"]
        )
        
        self.circuit_breaker_failures_total = Counter(
            "circuit_breaker_failures_total",
            "Circuit breaker failures",
            ["name"]
        )
        
        self.circuit_breaker_successes_total = Counter(
            "circuit_breaker_successes_total",
            "Circuit breaker successes",
            ["name"]
        )
        
        # ============================================================
        # Rate Limiter Metrics
        # ============================================================
        
        self.rate_limit_requests_total = Counter(
            "rate_limit_requests_total",
            "Rate limiter requests",
            ["limiter", "status"]  # accepted | rejected
        )
        
        self.rate_limit_available_tokens = Gauge(
            "rate_limit_available_tokens",
            "Available rate limiter tokens",
            ["limiter"]
        )
        
        # ============================================================
        # System Health Metrics
        # ============================================================
        
        self.health_check_status = Gauge(
            "health_check_status",
            "Component health (1=healthy, 0=unhealthy)",
            ["component"]
        )
        
        self.errors_total = Counter(
            "errors_total",
            "Total errors",
            ["component", "error_type"]
        )
        
        # ============================================================
        # Memory Metrics
        # ============================================================
        
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "Memory usage",
            ["type"]  # episodic | vector | cache
        )
        
        self.db_size_bytes = Gauge(
            "db_size_bytes",
            "Database file size",
            ["db_name"]
        )
        
        # ============================================================
        # Tick Metrics
        # ============================================================
        
        self.tick_duration = Histogram(
            "tick_duration_seconds",
            "Tick processing time",
            ["tick_type"],  # light | heavy
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.ticks_total = Counter(
            "ticks_total",
            "Total ticks processed",
            ["tick_type"]
        )
        
        log.info(
            f"MetricsCollector initialized. "
            f"Prometheus available: {PROMETHEUS_AVAILABLE}"
        )
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def record_llm_call(
        self,
        model: str,
        operation: str,  # chat | embed
        duration: float,
        success: bool,
        cached: bool = False
    ) -> None:
        """Записать LLM вызов."""
        status = "cached" if cached else ("success" if success else "error")
        
        self.llm_calls_total.labels(
            model=model,
            operation=operation,
            status=status
        ).inc()
        
        if not cached:
            self.llm_call_duration.labels(
                model=model,
                operation=operation
            ).observe(duration)
    
    def record_cache_hit(self, cache_type: str = "llm") -> None:
        """Записать cache hit."""
        self.cache_hits_total.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str = "llm") -> None:
        """Записать cache miss."""
        self.cache_misses_total.labels(cache_type=cache_type).inc()
    
    def update_circuit_breaker_state(
        self,
        name: str,
        state: str  # closed | open | half_open
    ) -> None:
        """Обновить состояние circuit breaker."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        self.circuit_breaker_state.labels(name=name).set(
            state_map.get(state, 0)
        )
    
    def update_health_status(self, component: str, healthy: bool) -> None:
        """Обновить здоровье компонента."""
        self.health_check_status.labels(component=component).set(
            1 if healthy else 0
        )
    
    def record_error(self, component: str, error_type: str) -> None:
        """Записать ошибку."""
        self.errors_total.labels(
            component=component,
            error_type=error_type
        ).inc()
    
    def is_available(self) -> bool:
        """Проверить доступны ли метрики."""
        return PROMETHEUS_AVAILABLE
    
    def generate_metrics(self) -> tuple[bytes, str]:
        """
        Сгенерировать Prometheus metrics.
        
        Returns:
            (metrics_bytes, content_type)
        """
        if not PROMETHEUS_AVAILABLE:
            return b"Prometheus not available", "text/plain"
        
        return generate_latest(), CONTENT_TYPE_LATEST


# Global metrics instance
metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Получить глобальный metrics collector."""
    return metrics
