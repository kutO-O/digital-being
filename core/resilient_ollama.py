"""Resilient Ollama client with circuit breaker and health monitoring."""

import asyncio
import time
from typing import Optional, Any, Dict
import logging

from core.circuit_breaker import CircuitBreaker
from core.health_monitor import HealthMonitor, ComponentHealth

logger = logging.getLogger("digital_being.resilient_ollama")


class ResilientOllamaClient:
    """
    Wrapper around OllamaClient with fault tolerance.
    
    Features:
    - Circuit breaker protection
    - Health monitoring
    - Automatic retry
    - Latency tracking
    - Fallback on failures
    """
    
    def __init__(self, ollama_client, health_monitor: Optional[HealthMonitor] = None):
        self.ollama = ollama_client
        self.health_monitor = health_monitor
        
        # Circuit breakers for different operations
        self.chat_breaker = CircuitBreaker(
            name="ollama_chat",
            failure_threshold=3,
            timeout_duration=60,
        )
        self.embed_breaker = CircuitBreaker(
            name="ollama_embed",
            failure_threshold=3,
            timeout_duration=60,
        )
        
        # Register with health monitor
        if self.health_monitor:
            self.health_monitor.register_component("ollama")
        
        # Metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_latency_ms = 0
    
    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        timeout: int = 30,
        fallback: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Call Ollama chat with circuit breaker protection.
        
        Args:
            prompt: User prompt
            system: Optional system prompt
            timeout: Timeout in seconds
            fallback: Fallback value if call fails
            
        Returns:
            LLM response or fallback
        """
        start_time = time.time()
        self.total_calls += 1
        
        async def _call():
            return await asyncio.wait_for(
                self._ollama_chat(prompt, system),
                timeout=timeout
            )
        
        async def _fallback():
            return fallback
        
        try:
            result = await self.chat_breaker.call(
                _call,
                fallback=_fallback if fallback is not None else None
            )
            
            latency_ms = (time.time() - start_time) * 1000
            self.total_latency_ms += latency_ms
            self.successful_calls += 1
            
            # Update health monitor
            if self.health_monitor:
                health = self.health_monitor.components.get("ollama")
                if health:
                    health.mark_healthy(latency_ms)
            
            logger.debug(f"[ResilientOllama] Chat completed ({latency_ms:.0f}ms)")
            return result
            
        except Exception as e:
            self.failed_calls += 1
            
            # Update health monitor
            if self.health_monitor:
                health = self.health_monitor.components.get("ollama")
                if health:
                    health.mark_unhealthy(str(e))
            
            logger.error(f"[ResilientOllama] Chat failed: {e}")
            
            if fallback is not None:
                return fallback
            raise
    
    async def embed(
        self,
        text: str,
        timeout: int = 10,
        fallback: Optional[Any] = None,
    ) -> Optional[list]:
        """
        Call Ollama embed with circuit breaker protection.
        
        Args:
            text: Text to embed
            timeout: Timeout in seconds
            fallback: Fallback value if call fails
            
        Returns:
            Embedding vector or fallback
        """
        async def _call():
            return await asyncio.wait_for(
                self._ollama_embed(text),
                timeout=timeout
            )
        
        async def _fallback():
            return fallback
        
        try:
            result = await self.embed_breaker.call(
                _call,
                fallback=_fallback if fallback is not None else None
            )
            return result
            
        except Exception as e:
            logger.error(f"[ResilientOllama] Embed failed: {e}")
            if fallback is not None:
                return fallback
            raise
    
    async def _ollama_chat(self, prompt: str, system: Optional[str]) -> str:
        """
        Internal wrapper for ollama.chat() to make it async-compatible.
        """
        loop = asyncio.get_event_loop()
        
        # Run synchronous ollama.chat in thread pool
        result = await loop.run_in_executor(
            None,
            lambda: self.ollama.chat(prompt, system) if system else self.ollama.chat(prompt)
        )
        return result
    
    async def _ollama_embed(self, text: str) -> list:
        """
        Internal wrapper for ollama.embed() to make it async-compatible.
        """
        loop = asyncio.get_event_loop()
        
        # Run synchronous ollama.embed in thread pool
        result = await loop.run_in_executor(
            None,
            lambda: self.ollama.embed(text)
        )
        return result
    
    def is_available(self) -> bool:
        """
        Check if Ollama is available.
        
        Returns:
            True if available (circuit not OPEN)
        """
        from core.circuit_breaker import CircuitState
        return (
            self.chat_breaker.state != CircuitState.OPEN and
            self.ollama.is_available()
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get client statistics.
        """
        avg_latency = (
            self.total_latency_ms / self.successful_calls
            if self.successful_calls > 0
            else 0
        )
        
        success_rate = (
            (self.successful_calls / self.total_calls * 100)
            if self.total_calls > 0
            else 0
        )
        
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "chat_breaker": self.chat_breaker.get_stats(),
            "embed_breaker": self.embed_breaker.get_stats(),
        }
    
    def reset_breakers(self):
        """Manually reset circuit breakers."""
        self.chat_breaker.reset()
        self.embed_breaker.reset()
        logger.info("[ResilientOllama] Circuit breakers reset")