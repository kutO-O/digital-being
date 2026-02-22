"""
Circuit Breaker Pattern Implementation

Предотвращает каскадные сбои при отказе внешних сервисов (Ollama).

States:
- CLOSED: Нормальная работа, запросы проходят
- OPEN: Сервис недоступен, запросы блокируются
- HALF_OPEN: Тестирование восстановления

Переходы:
CLOSED -> OPEN: После N последовательных ошибок
OPEN -> HALF_OPEN: После timeout восстановления
HALF_OPEN -> CLOSED: После успешного теста
HALF_OPEN -> OPEN: Если тест провалился
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Callable, Any, TypeVar

log = logging.getLogger("digital_being.circuit_breaker")

T = TypeVar("T")


class CircuitState(Enum):
    """Состояния circuit breaker."""
    CLOSED = "closed"        # Нормальная работа
    OPEN = "open"            # Сервис недоступен
    HALF_OPEN = "half_open"  # Тестирование восстановления


class CircuitBreakerOpen(Exception):
    """Исключение когда circuit breaker открыт."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев.
    
    Пример:
        breaker = CircuitBreaker(
            name="ollama",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2
        )
        
        result = breaker.call(lambda: ollama.generate(prompt))
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
    ) -> None:
        """
        Args:
            name: Имя circuit breaker для логов
            failure_threshold: Сколько ошибок до OPEN
            recovery_timeout: Секунд до попытки восстановления
            success_threshold: Успехов в HALF_OPEN для CLOSED
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._last_state_change = time.time()
        
        log.info(
            f"CircuitBreaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s, "
            f"success_threshold={success_threshold}"
        )
    
    def call(self, operation: Callable[[], T]) -> T:
        """
        Выполнить операцию через circuit breaker.
        
        Args:
            operation: Функция для выполнения
            
        Returns:
            Результат операции
            
        Raises:
            CircuitBreakerOpen: Если circuit открыт
            Exception: Оригинальное исключение от operation
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self._name}' is OPEN. "
                    f"Will retry in {self._time_until_retry():.1f}s"
                )
        
        try:
            result = operation()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Проверить можно ли попробовать восстановление."""
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self._recovery_timeout
    
    def _time_until_retry(self) -> float:
        """Секунд до следующей попытки."""
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self._recovery_timeout - elapsed)
    
    def _on_success(self) -> None:
        """Обработать успешную операцию."""
        self._failure_count = 0
        
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                self._transition_to_closed()
    
    def _on_failure(self) -> None:
        """Обработать неудачную операцию."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self._failure_threshold:
                self._transition_to_open()
    
    def _transition_to_open(self) -> None:
        """Перейти в состояние OPEN."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._last_state_change = time.time()
        self._success_count = 0
        
        log.warning(
            f"CircuitBreaker '{self._name}': {old_state.value} -> OPEN. "
            f"Failures: {self._failure_count}. "
            f"Will retry in {self._recovery_timeout}s"
        )
    
    def _transition_to_half_open(self) -> None:
        """Перейти в состояние HALF_OPEN."""
        old_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._last_state_change = time.time()
        self._failure_count = 0
        self._success_count = 0
        
        log.info(
            f"CircuitBreaker '{self._name}': {old_state.value} -> HALF_OPEN. "
            f"Testing recovery..."
        )
    
    def _transition_to_closed(self) -> None:
        """Перейти в состояние CLOSED."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._last_state_change = time.time()
        self._failure_count = 0
        self._success_count = 0
        
        log.info(
            f"CircuitBreaker '{self._name}': {old_state.value} -> CLOSED. "
            f"Service recovered!"
        )
    
    def get_state(self) -> str:
        """Получить текущее состояние."""
        return self._state.value
    
    def get_stats(self) -> dict:
        """Получить статистику circuit breaker."""
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_state_change": self._last_state_change,
            "time_in_state": time.time() - self._last_state_change,
            "time_until_retry": self._time_until_retry() if self._state == CircuitState.OPEN else 0,
        }
    
    def reset(self) -> None:
        """Принудительно сбросить в CLOSED (для тестов или manual recovery)."""
        log.info(f"CircuitBreaker '{self._name}': Manual reset to CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_state_change = time.time()


class CircuitBreakerRegistry:
    """
    Реестр всех circuit breakers в системе.
    Позволяет мониторить здоровье всех сервисов.
    """
    
    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
    
    def register(self, breaker: CircuitBreaker) -> None:
        """Зарегистрировать circuit breaker."""
        self._breakers[breaker._name] = breaker
    
    def get(self, name: str) -> CircuitBreaker | None:
        """Получить breaker по имени."""
        return self._breakers.get(name)
    
    def get_all_stats(self) -> dict[str, dict]:
        """Получить статистику всех breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}
    
    def is_healthy(self) -> bool:
        """Проверить здоровы ли все сервисы."""
        return all(
            breaker.get_state() != CircuitState.OPEN.value
            for breaker in self._breakers.values()
        )
    
    def get_unhealthy(self) -> list[str]:
        """Получить список нездоровых сервисов."""
        return [
            name for name, breaker in self._breakers.items()
            if breaker.get_state() == CircuitState.OPEN.value
        ]


# Global registry
_registry = CircuitBreakerRegistry()


def get_registry() -> CircuitBreakerRegistry:
    """Получить глобальный реестр circuit breakers."""
    return _registry
