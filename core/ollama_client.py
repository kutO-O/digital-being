"""
Digital Being — OllamaClient
Phase 7: Thin wrapper over the `ollama` library.

Features:
  - chat()  — single-turn generation via strategy model
  - embed() — text embedding via embed model
  - is_available() — lightweight availability ping
  - Per-tick LLM budget enforced via calls_this_tick counter
  - Retry logic with exponential backoff for transient failures

Changelog:
  TD-006 fix — added retry logic with exponential backoff for reliability.
"""

from __future__ import annotations

import logging
import time
from typing import Any

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
                f"max_retries={self._max_retries}"
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
        Retries transient failures with exponential backoff.
        """
        if self._client is None:
            return ""
        if not self._check_budget():
            return ""

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        self.calls_this_tick += 1
        
        def _do_chat():
            response = self._client.chat(
                model=self._strategy_model,
                messages=messages,
                options={"num_predict": 512},
            )
            return response["message"]["content"]
        
        try:
            text = self._retry_with_backoff(_do_chat, "chat")
            if text is None:
                self.calls_this_tick -= 1
                return ""
            
            log.debug(
                f"chat() call {self.calls_this_tick}/{self._max_calls}: "
                f"{len(text)} chars returned."
            )
            return text
        except Exception as e:
            log.error(f"OllamaClient.chat() failed: {e}")
            self.calls_this_tick -= 1
            return ""

    def embed(self, text: str) -> list[float]:
        """
        Get text embedding via the embed model.
        Returns [] on any error (no budget check — embeddings are cheap).
        Retries transient failures with exponential backoff.
        """
        if self._client is None:
            return []
        
        def _do_embed():
            response = self._client.embed(
                model=self._embed_model,
                input=text,
            )
            vectors: list[list[float]] = response.get("embeddings", [])
            return vectors[0] if vectors else []
        
        try:
            result = self._retry_with_backoff(_do_embed, "embed")
            return result if result is not None else []
        except Exception as e:
            log.error(f"OllamaClient.embed() failed: {e}")
            return []

    def is_available(self) -> bool:
        """
        Quick health check — list local models.
        Returns False if Ollama is unreachable or package missing.
        """
        if self._client is None:
            return False
        try:
            self._client.list()     # lightweight endpoint
            return True
        except Exception as e:
            log.warning(f"Ollama unavailable: {e}")
            return False
