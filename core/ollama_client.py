"""
Digital Being — OllamaClient
Phase 7: Thin wrapper over the `ollama` library.

Features:
  - chat()  — single-turn generation via strategy model
  - embed() — text embedding via embed model
  - is_available() — lightweight availability ping
  - Per-tick LLM budget enforced via calls_this_tick counter
"""

from __future__ import annotations

import logging
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
                f"host={self._base_url}"
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
    # Core methods
    # ────────────────────────────────────────────────────────────
    def chat(self, prompt: str, system: str = "") -> str:
        """
        Send a chat request to the strategy model.
        Returns the response text, or "" on any error.
        Counts against the per-tick budget.
        """
        if self._client is None:
            return ""
        if not self._check_budget():
            return ""

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            self.calls_this_tick += 1
            response = self._client.chat(
                model=self._strategy_model,
                messages=messages,
                options={"num_predict": 512},
            )
            text: str = response["message"]["content"]
            log.debug(
                f"chat() call {self.calls_this_tick}/{self._max_calls}: "
                f"{len(text)} chars returned."
            )
            return text
        except Exception as e:
            log.error(f"OllamaClient.chat() failed: {e}")
            self.calls_this_tick -= 1   # don’t penalise budget for failed call
            return ""

    def embed(self, text: str) -> list[float]:
        """
        Get text embedding via the embed model.
        Returns [] on any error (no budget check — embeddings are cheap).
        """
        if self._client is None:
            return []
        try:
            response = self._client.embed(
                model=self._embed_model,
                input=text,
            )
            vectors: list[list[float]] = response.get("embeddings", [])
            return vectors[0] if vectors else []
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
