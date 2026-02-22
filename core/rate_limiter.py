"""
Rate Limiter

Защита от перегрузки LLM с помощью Token Bucket algorithm.

Algorithm:
- Tokens regenerate at fixed rate
- Each request consumes 1 token
- Burst capacity for temporary spikes
- Block when no tokens available

Пример:
    limiter = RateLimiter(rate=5.0, burst=10)  # 5 req/s, burst 10
    
    if limiter.acquire():
        response = ollama.chat(prompt)
    else:
        log.warning("Rate limit exceeded")
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

log = logging.getLogger("digital_being.rate_limiter")


class RateLimiter:
    """
    Token Bucket rate limiter.
    
    Features:
    - Configurable rate (tokens/second)
    - Burst capacity
    - Non-blocking check
    - Async sleep until available
    - Statistics tracking
    """
    
    def __init__(
        self,
        rate: float,
        burst: int | None = None,
        name: str = "default"
    ) -> None:
        """
        Args:
            rate: Tokens per second (e.g. 5.0 = 5 requests/second)
            burst: Max burst capacity (default = rate * 2)
            name: Name for logging
        """
        self._rate = rate
        self._burst = burst if burst is not None else int(rate * 2)
        self._name = name
        
        self._tokens = float(self._burst)
        self._last_update = time.monotonic()
        
        # Statistics
        self._total_requests = 0
        self._accepted = 0
        self._rejected = 0
        
        log.info(
            f"RateLimiter '{name}' initialized: "
            f"rate={rate} req/s, burst={self._burst}"
        )
    
    def _refill(self) -> None:
        """Пополнить токены по времени."""
        now = time.monotonic()
        elapsed = now - self._last_update
        
        # Generate tokens based on elapsed time
        new_tokens = elapsed * self._rate
        self._tokens = min(self._burst, self._tokens + new_tokens)
        self._last_update = now
    
    def acquire(self, tokens: float = 1.0) -> bool:
        """
        Попытаться получить токены (non-blocking).
        
        Args:
            tokens: Количество токенов (default 1.0)
            
        Returns:
            True если токены получены, False если лимит превышен
        """
        self._total_requests += 1
        self._refill()
        
        if self._tokens >= tokens:
            self._tokens -= tokens
            self._accepted += 1
            return True
        else:
            self._rejected += 1
            log.warning(
                f"RateLimiter '{self._name}': Rate limit exceeded. "
                f"Available tokens: {self._tokens:.2f}/{self._burst}"
            )
            return False
    
    async def acquire_async(self, tokens: float = 1.0) -> bool:
        """
        Получить токены с ожиданием (blocking async).
        
        Если токенов нет - ждёт пока не появятся.
        
        Returns:
            Always True (ждёт до успеха)
        """
        while not self.acquire(tokens):
            # Calculate wait time
            wait_time = tokens / self._rate
            log.debug(
                f"RateLimiter '{self._name}': Waiting {wait_time:.2f}s for tokens"
            )
            await asyncio.sleep(wait_time)
        
        return True
    
    def time_until_available(self, tokens: float = 1.0) -> float:
        """
        Сколько секунд до доступности токенов.
        
        Returns:
            Секунд до доступности (или 0 если уже доступны)
        """
        self._refill()
        
        if self._tokens >= tokens:
            return 0.0
        
        missing_tokens = tokens - self._tokens
        return missing_tokens / self._rate
    
    def reset(self) -> None:
        """Сбросить limiter (заполнить токены)."""
        self._tokens = float(self._burst)
        self._last_update = time.monotonic()
        log.info(f"RateLimiter '{self._name}' reset")
    
    def get_stats(self) -> dict[str, Any]:
        """Получить статистику rate limiter."""
        self._refill()
        
        acceptance_rate = (
            (self._accepted / self._total_requests * 100)
            if self._total_requests > 0 else 100.0
        )
        
        return {
            "name": self._name,
            "rate": self._rate,
            "burst": self._burst,
            "available_tokens": round(self._tokens, 2),
            "total_requests": self._total_requests,
            "accepted": self._accepted,
            "rejected": self._rejected,
            "acceptance_rate": round(acceptance_rate, 2),
        }


class MultiRateLimiter:
    """
    Менеджер нескольких rate limiters.
    
    Позволяет устанавливать разные лимиты для разных операций.
    
    Пример:
        limiters = MultiRateLimiter()
        limiters.add("chat", rate=5.0, burst=10)
        limiters.add("embed", rate=20.0, burst=50)
        
        if limiters.acquire("chat"):
            response = ollama.chat(prompt)
    """
    
    def __init__(self) -> None:
        self._limiters: dict[str, RateLimiter] = {}
    
    def add(
        self,
        name: str,
        rate: float,
        burst: int | None = None
    ) -> RateLimiter:
        """Добавить rate limiter."""
        limiter = RateLimiter(rate, burst, name)
        self._limiters[name] = limiter
        return limiter
    
    def get(self, name: str) -> RateLimiter | None:
        """Получить limiter по имени."""
        return self._limiters.get(name)
    
    def acquire(self, name: str, tokens: float = 1.0) -> bool:
        """Получить токены из конкретного limiter."""
        limiter = self._limiters.get(name)
        if limiter is None:
            log.warning(f"RateLimiter '{name}' not found - allowing request")
            return True
        return limiter.acquire(tokens)
    
    async def acquire_async(self, name: str, tokens: float = 1.0) -> bool:
        """Получить токены async."""
        limiter = self._limiters.get(name)
        if limiter is None:
            log.warning(f"RateLimiter '{name}' not found - allowing request")
            return True
        return await limiter.acquire_async(tokens)
    
    def get_all_stats(self) -> dict[str, dict]:
        """Получить статистику всех limiters."""
        return {
            name: limiter.get_stats()
            for name, limiter in self._limiters.items()
        }
    
    def reset_all(self) -> None:
        """Сбросить все limiters."""
        for limiter in self._limiters.values():
            limiter.reset()
        log.info(f"All {len(self._limiters)} rate limiters reset")
