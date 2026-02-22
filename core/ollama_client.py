"""
Digital Being — OllamaClient
Phase 7: Thin wrapper over the `ollama` library.

Features:
  - chat()  — single-turn generation via strategy model
  - embed() — text embedding via embed model
  - is_available() — lightweight availability ping
  - Per-tick LLM budget enforced via calls_this_tick counter
  - Retry logic with exponential backoff for transient failures
  - Circuit breaker pattern for cascading failure prevention
  - LLM response cache (5-10x speedup for repeated prompts)
  - Rate limiting (token bucket) to prevent overload
  - Prometheus metrics for full observability

Changelog:
  TD-006 fix — added retry logic with exponential backoff for reliability.
  TD-016 fix — integrated circuit breaker for fault tolerance.
  TD-021 fix — added LLM response cache for performance.
  TD-015 fix — added rate limiter to prevent overload.
  TD-013 fix — integrated Prometheus metrics for observability.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, get_registry
from core.llm_cache import LLMCache
from core.rate_limiter import MultiRateLimiter
from core.metrics import get_metrics

log = logging.getLogger("digital_being.ollama_client")


class OllamaClient:
    """
    Wraps the `ollama` Python library.
    All model names, URL and timeout come from config.yaml.

    Lifecycle:
        client = OllamaClient(cfg)
        ok = client.is_available()
        text = client.chat(prompt, system)
    """

    def __init__(self, cfg: dict) -> None:
        ollama_cfg = cfg.get("ollama", {})
        self._strategy_model: str  = ollama_cfg.get("strategy_model", "llama3.2")
        self._embed_model:    str  = ollama_cfg.get("embed_model", "nomic-embed-text")
        self._base_url:       str  = ollama_cfg.get("base_url", "http://localhost:11434")
        self._timeout:        int  = int(ollama_cfg.get("timeout_sec", 30))
        self._max_calls:      int  = int(
            cfg.get("resources", {}).get("budget", {}).get("max_llm_calls", 3)
        )
        self._max_retries:    int  = 3  # TD-006: retry transient failures
        self._base_delay:     float = 1.0  # TD-006: initial backoff delay

        self.calls_this_tick: int = 0

        # TD-016: Circuit breaker for Ollama
        self._circuit_breaker = CircuitBreaker(
            name="ollama",
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=2,
        )
        get_registry().register(self._circuit_breaker)

        # TD-021: LLM response cache
        cache_cfg = cfg.get("cache", {})
        self._cache = LLMCache(
            max_size=cache_cfg.get("max_size", 100),
            ttl_seconds=cache_cfg.get("ttl_seconds", 300.0),
        )

        # TD-015: Rate limiter
        rate_cfg = cfg.get("rate_limit", {})
        self._rate_limiters = MultiRateLimiter()
        self._rate_limiters.add(
            "chat",
            rate=rate_cfg.get("chat_rate", 5.0),  # 5 chat requests/sec
            burst=rate_cfg.get("chat_burst", 10),
        )
        self._rate_limiters.add(
            "embed",
            rate=rate_cfg.get("embed_rate", 20.0),  # 20 embed requests/sec
            burst=rate_cfg.get("embed_burst", 50),
        )

        # TD-013: Prometheus metrics
        self._metrics = get_metrics()

        # Lazy-import ollama so the rest of the system works even if
        # the package is not installed.
        try:
            import ollama as _ollama
            self._ollama = _ollama
            # Point the client at the configured host
            self._client = _ollama.Client(host=self._base_url)
            log.info(
                f"OllamaClient initialised. "
                f"strategy={self._strategy_model} "
                f"embed={self._embed_model} "
                f"host={self._base_url} "
                f"max_retries={self._max_retries} "
                f"circuit_breaker=enabled "
                f"cache=enabled "
                f"rate_limiter=enabled "
                f"metrics=enabled"
            )
        except ImportError:
            self._ollama = None  # type: ignore[assignment]
            self._client = None
            log.warning(
                "OllamaClient: `ollama` package not installed. "
                "All LLM calls will return empty results."
            )

    # ────────────────────────────────────────────────────────────
    # Budget
    # ────────────────────────────────────────────────────────────
    def reset_tick_counter(self) -> None:
        """Call at the start of each Heavy Tick."""
        self.calls_this_tick = 0

    def _check_budget(self) -> bool:
        """Return True if another call is allowed. Logs if exhausted."""
        if self.calls_this_tick >= self._max_calls:
            log.warning(
                f"LLM budget exhausted "
                f"({self.calls_this_tick}/{self._max_calls} calls this tick). "
                f"Request denied."
            )
            return False
        return True

    # ────────────────────────────────────────────────────────────
    # Retry helper
    # ────────────────────────────────────────────────────────────
    def _retry_with_backoff(self, operation, context: str):
        """
        Execute operation with retry logic and exponential backoff.
        
        Args:
            operation: Callable that returns result or raises exception
            context: Description for logging (e.g. "chat", "embed")
        
        Returns:
            Result from operation, or None if all retries fail
        """
        delay = self._base_delay
        last_exception = None
        
        for attempt in range(self._max_retries):
            try:
                return operation()
            except Exception as e:
                last_exception = e
                
                # Check if error is transient (network, timeout, connection)
                error_str = str(e).lower()
                is_transient = any(
                    keyword in error_str 
                    for keyword in ["connection", "timeout", "network", "refused"]
                )
                
                if not is_transient:
                    # Non-transient error - don't retry
                    log.error(f"{context}() failed with non-transient error: {e}")
                    raise
                
                if attempt < self._max_retries - 1:
                    log.warning(
                        f"{context}() attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= 2.0  # Exponential backoff
                else:
                    log.error(
                        f"{context}() failed after {self._max_retries} attempts: {last_exception}"
                    )
        
        return None

    # ────────────────────────────────────────────────────────────
    # Core methods
    # ────────────────────────────────────────────────────────────
    def chat(self, prompt: str, system: str = "") -> str:
        """
        Send a chat request to the strategy model.
        Returns the response text, or "" on any error.
        Counts against the per-tick budget.
        Protected by: rate limiter → cache → circuit breaker → retry logic.
        All operations tracked in Prometheus metrics.
        """
        if self._client is None:
            return ""
        if not self._check_budget():
            return ""

        start_time = time.time()
        cached = False
        success = False

        try:
            # TD-015: Check rate limit first
            if not self._rate_limiters.acquire("chat"):
                log.warning("Chat rate limit exceeded - request blocked")
                self._metrics.rate_limit_requests_total.labels(
                    limiter="chat",
                    status="rejected"
                ).inc()
                return ""
            
            self._metrics.rate_limit_requests_total.labels(
                limiter="chat",
                status="accepted"
            ).inc()

            # TD-021: Check cache
            cached_response = self._cache.get(prompt, system)
            if cached_response is not None:
                log.debug(f"Cache HIT for chat prompt (len={len(prompt)})")
                cached = True
                success = True
                self._metrics.record_cache_hit("llm")
                return cached_response
            
            self._metrics.record_cache_miss("llm")

            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            self.calls_this_tick += 1
            
            def _do_chat_with_retry():
                def _do_chat():
                    response = self._client.chat(
                        model=self._strategy_model,
                        messages=messages,
                        options={"num_predict": 512},
                    )
                    return response["message"]["content"]
                
                return self._retry_with_backoff(_do_chat, "chat")
            
            # TD-016: Wrap in circuit breaker
            text = self._circuit_breaker.call(_do_chat_with_retry)
            
            if text is None:
                self.calls_this_tick -= 1
                return ""
            
            # Cache the response
            self._cache.set(prompt, system, text)
            success = True
            
            log.debug(
                f"chat() call {self.calls_this_tick}/{self._max_calls}: "
                f"{len(text)} chars returned."
            )
            return text
            
        except CircuitBreakerOpen as e:
            log.warning(f"OllamaClient.chat() blocked by circuit breaker: {e}")
            self.calls_this_tick -= 1
            return ""
        except Exception as e:
            log.error(f"OllamaClient.chat() failed: {e}")
            self._metrics.record_error("ollama", type(e).__name__)
            self.calls_this_tick -= 1
            return ""
        finally:
            # TD-013: Record metrics
            duration = time.time() - start_time
            self._metrics.record_llm_call(
                model=self._strategy_model,
                operation="chat",
                duration=duration,
                success=success,
                cached=cached
            )

    def embed(self, text: str) -> list[float]:
        """
        Get text embedding via the embed model.
        Returns [] on any error (no budget check — embeddings are cheap).
        Protected by: rate limiter → circuit breaker → retry logic.
        All operations tracked in Prometheus metrics.
        """
        if self._client is None:
            return []
        
        start_time = time.time()
        success = False

        try:
            # TD-015: Check rate limit
            if not self._rate_limiters.acquire("embed"):
                log.warning("Embed rate limit exceeded - request blocked")
                self._metrics.rate_limit_requests_total.labels(
                    limiter="embed",
                    status="rejected"
                ).inc()
                return []
            
            self._metrics.rate_limit_requests_total.labels(
                limiter="embed",
                status="accepted"
            ).inc()
            
            def _do_embed_with_retry():
                def _do_embed():
                    response = self._client.embed(
                        model=self._embed_model,
                        input=text,
                    )
                    vectors: list[list[float]] = response.get("embeddings", [])
                    return vectors[0] if vectors else []
                
                return self._retry_with_backoff(_do_embed, "embed")
            
            # TD-016: Wrap in circuit breaker
            result = self._circuit_breaker.call(_do_embed_with_retry)
            success = result is not None and len(result) > 0
            return result if result is not None else []
            
        except CircuitBreakerOpen as e:
            log.warning(f"OllamaClient.embed() blocked by circuit breaker: {e}")
            return []
        except Exception as e:
            log.error(f"OllamaClient.embed() failed: {e}")
            self._metrics.record_error("ollama", type(e).__name__)
            return []
        finally:
            # TD-013: Record metrics
            duration = time.time() - start_time
            self._metrics.record_llm_call(
                model=self._embed_model,
                operation="embed",
                duration=duration,
                success=success,
                cached=False
            )

    def is_available(self) -> bool:
        """
        Quick health check — list local models.
        Returns False if Ollama is unreachable or package missing.
        Does NOT use circuit breaker (used BY circuit breaker for health checks).
        """
        if self._client is None:
            return False
        try:
            self._client.list()     # lightweight endpoint
            return True
        except Exception as e:
            log.warning(f"Ollama unavailable: {e}")
            return False
    
    # ────────────────────────────────────────────────────────────
    # Monitoring
    # ────────────────────────────────────────────────────────────
    
    def get_circuit_state(self) -> str:
        """Получить состояние circuit breaker."""
        return self._circuit_breaker.get_state()
    
    def get_circuit_stats(self) -> dict:
        """Получить статистику circuit breaker."""
        return self._circuit_breaker.get_stats()
    
    def get_cache_stats(self) -> dict:
        """Получить статистику cache."""
        return self._cache.get_stats()
    
    def get_rate_limiter_stats(self) -> dict:
        """Получить статистику rate limiters."""
        return self._rate_limiters.get_all_stats()
    
    def get_comprehensive_stats(self) -> dict:
        """Полная статистика всех компонентов."""
        return {
            "circuit_breaker": self.get_circuit_stats(),
            "cache": self.get_cache_stats(),
            "rate_limiters": self.get_rate_limiter_stats(),
            "budget": {
                "calls_this_tick": self.calls_this_tick,
                "max_calls": self._max_calls,
                "remaining": self._max_calls - self.calls_this_tick,
            },
        }
