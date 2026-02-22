"""
Health Check System

Мониторинг здоровья всех компонентов системы.

Пример использования:
    health = HealthChecker(
        ollama=ollama,
        episodic_mem=episodic_mem,
        vector_mem=vector_mem,
        event_bus=event_bus
    )
    
    report = health.check_all()
    if not report['healthy']:
        log.warning(f"System unhealthy: {report['issues']}")
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.ollama_client import OllamaClient
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.event_bus import EventBus
    from core.circuit_breaker import CircuitBreakerRegistry

log = logging.getLogger("digital_being.health")


class ComponentHealth:
    """Здоровье одного компонента."""
    
    def __init__(
        self,
        name: str,
        healthy: bool,
        message: str = "",
        details: dict[str, Any] | None = None
    ) -> None:
        self.name = name
        self.healthy = healthy
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Конвертировать в словарь."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class HealthChecker:
    """
    Система проверки здоровья всех компонентов.
    
    Проверяет:
    - Ollama доступность
    - Базы данных
    - Память
    - Circuit breakers
    - Event bus
    """
    
    def __init__(
        self,
        ollama: "OllamaClient | None" = None,
        episodic_mem: "EpisodicMemory | None" = None,
        vector_mem: "VectorMemory | None" = None,
        event_bus: "EventBus | None" = None,
        circuit_registry: "CircuitBreakerRegistry | None" = None,
    ) -> None:
        self._ollama = ollama
        self._episodic_mem = episodic_mem
        self._vector_mem = vector_mem
        self._event_bus = event_bus
        self._circuit_registry = circuit_registry
        
        self._last_check_time = 0.0
        self._last_report: dict | None = None
    
    def check_all(self, force: bool = False) -> dict:
        """
        Проверить здоровье всех компонентов.
        
        Args:
            force: Проверить даже если недавно проверяли (cache bypass)
            
        Returns:
            dict с полным репортом здоровья
        """
        # Cache for 10 seconds
        if not force and self._last_report:
            if time.time() - self._last_check_time < 10:
                return self._last_report
        
        components = []
        
        # Check Ollama
        if self._ollama:
            components.append(self._check_ollama())
        
        # Check Episodic Memory
        if self._episodic_mem:
            components.append(self._check_episodic_memory())
        
        # Check Vector Memory
        if self._vector_mem:
            components.append(self._check_vector_memory())
        
        # Check Event Bus
        if self._event_bus:
            components.append(self._check_event_bus())
        
        # Check Circuit Breakers
        if self._circuit_registry:
            components.append(self._check_circuit_breakers())
        
        # Aggregate
        all_healthy = all(c.healthy for c in components)
        issues = [c.message for c in components if not c.healthy]
        
        report = {
            "healthy": all_healthy,
            "timestamp": time.time(),
            "components": {c.name: c.to_dict() for c in components},
            "issues": issues,
            "summary": self._build_summary(components),
        }
        
        self._last_check_time = time.time()
        self._last_report = report
        
        if not all_healthy:
            log.warning(f"Health check FAILED: {len(issues)} issue(s)")
        
        return report
    
    def _check_ollama(self) -> ComponentHealth:
        """Проверить Ollama."""
        try:
            available = self._ollama.is_available()
            if not available:
                return ComponentHealth(
                    "ollama",
                    False,
                    "Ollama is not available"
                )
            
            # Get stats
            stats = {
                "available": True,
                "tick_count": getattr(self._ollama, "_tick_count", 0),
            }
            
            return ComponentHealth(
                "ollama",
                True,
                "Ollama is healthy",
                stats
            )
        except Exception as e:
            return ComponentHealth(
                "ollama",
                False,
                f"Ollama check failed: {e}"
            )
    
    def _check_episodic_memory(self) -> ComponentHealth:
        """Проверить episodic memory."""
        try:
            # Try to query
            recent = self._episodic_mem.get_recent_episodes(1)
            
            # Check DB size
            db_path = getattr(self._episodic_mem, "_db_path", None)
            db_size = 0
            if db_path and Path(db_path).exists():
                db_size = Path(db_path).stat().st_size
            
            stats = {
                "db_size_mb": round(db_size / 1024 / 1024, 2),
                "can_query": True,
            }
            
            return ComponentHealth(
                "episodic_memory",
                True,
                "Episodic memory is healthy",
                stats
            )
        except Exception as e:
            return ComponentHealth(
                "episodic_memory",
                False,
                f"Episodic memory check failed: {e}"
            )
    
    def _check_vector_memory(self) -> ComponentHealth:
        """Проверить vector memory."""
        try:
            # Try health check if available
            if hasattr(self._vector_mem, "health_check"):
                health = self._vector_mem.health_check()
                if not health["healthy"]:
                    return ComponentHealth(
                        "vector_memory",
                        False,
                        f"Vector memory unhealthy: {health.get('error', 'unknown')}",
                        health
                    )
            
            # Check DB size
            db_path = getattr(self._vector_mem, "_db_path", None)
            db_size = 0
            if db_path and Path(db_path).exists():
                db_size = Path(db_path).stat().st_size
            
            stats = {
                "db_size_mb": round(db_size / 1024 / 1024, 2),
            }
            
            return ComponentHealth(
                "vector_memory",
                True,
                "Vector memory is healthy",
                stats
            )
        except Exception as e:
            return ComponentHealth(
                "vector_memory",
                False,
                f"Vector memory check failed: {e}"
            )
    
    def _check_event_bus(self) -> ComponentHealth:
        """Проверить event bus."""
        try:
            # Get health report if available
            if hasattr(self._event_bus, "get_health_report"):
                health = self._event_bus.get_health_report()
                
                if not health["healthy"]:
                    return ComponentHealth(
                        "event_bus",
                        False,
                        f"Event bus has {health['total_errors']} errors",
                        health
                    )
                
                return ComponentHealth(
                    "event_bus",
                    True,
                    "Event bus is healthy",
                    health
                )
            
            # Basic check
            return ComponentHealth(
                "event_bus",
                True,
                "Event bus is operational"
            )
        except Exception as e:
            return ComponentHealth(
                "event_bus",
                False,
                f"Event bus check failed: {e}"
            )
    
    def _check_circuit_breakers(self) -> ComponentHealth:
        """Проверить circuit breakers."""
        try:
            stats = self._circuit_registry.get_all_stats()
            unhealthy = self._circuit_registry.get_unhealthy()
            
            if unhealthy:
                return ComponentHealth(
                    "circuit_breakers",
                    False,
                    f"Circuit breakers OPEN: {', '.join(unhealthy)}",
                    {"all_stats": stats, "unhealthy": unhealthy}
                )
            
            return ComponentHealth(
                "circuit_breakers",
                True,
                "All circuit breakers closed",
                {"all_stats": stats}
            )
        except Exception as e:
            return ComponentHealth(
                "circuit_breakers",
                False,
                f"Circuit breaker check failed: {e}"
            )
    
    def _build_summary(self, components: list[ComponentHealth]) -> str:
        """Построить текстовую сводку."""
        healthy_count = sum(1 for c in components if c.healthy)
        total = len(components)
        
        if healthy_count == total:
            return f"✅ All {total} components healthy"
        else:
            unhealthy = total - healthy_count
            return f"⚠️ {unhealthy}/{total} components unhealthy"
    
    def is_healthy(self) -> bool:
        """Быстрая проверка здоровья."""
        report = self.check_all()
        return report["healthy"]
    
    def get_issues(self) -> list[str]:
        """Получить список проблем."""
        report = self.check_all()
        return report["issues"]
