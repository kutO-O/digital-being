"""
Digital Being — IntrospectionAPI
Stage 19: /beliefs endpoint added.

Endpoints (all GET, all return JSON unless noted):
  /status         — uptime, tick_count, mode, current goal, goal_stats, attention_focus
  /memory         — episode count, vector count, recent episodes
  /values         — scores, mode, conflicts
  /strategy       — three planning horizons
  /milestones     — achieved / pending milestones
  /dream          — Dream Mode state and next-run ETA
  /episodes       — filtered episode search (?limit=20&event_type=...)
  /search         — semantic search via VectorMemory (?q=text&top_k=5)
  /emotions       — current emotional state, dominant emotion, tone modifier
  /reflection     — last 5 reflections + total count
  /diary          — last N diary entries from narrative_log.json
  /diary/raw      — full diary.md as text/plain
  /curiosity      — open questions + stats
  /modifications  — config modification history + stats
  /beliefs        — active and strong beliefs + stats [Stage 19]
  /contradictions — pending and resolved contradictions + stats [Stage 20]

Design rules:
  - Pure read — no mutations
  - CORS: Access-Control-Allow-Origin: *
  - All errors return {"error": "..."} with HTTP 500
  - aiohttp runner lifecycle: start() / stop()
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

try:
    from aiohttp import web
except ImportError:
    web = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from core.attention_system import AttentionSystem
    from core.belief_system import BeliefSystem
    from core.contradiction_resolver import ContradictionResolver
    from core.curiosity_engine import CuriosityEngine
    from core.dream_mode import DreamMode
    from core.emotion_engine import EmotionEngine
    from core.goal_persistence import GoalPersistence
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.milestones import Milestones
    from core.narrative_engine import NarrativeEngine
    from core.ollama_client import OllamaClient
    from core.reflection_engine import ReflectionEngine
    from core.self_modification import SelfModificationEngine
    from core.strategy_engine import StrategyEngine
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.introspection_api")

_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class IntrospectionAPI:
    """
    Lightweight aiohttp HTTP server exposing system state.

    Usage:
        api = IntrospectionAPI(
            host="127.0.0.1", port=8765,
            components={...},
            start_time=time.time(),
        )
        await api.start()
        # ... run ...
        await api.stop()
    """

    def __init__(
        self,
        host:        str,
        port:        int,
        components:  dict,
        start_time:  float,
    ) -> None:
        self._host       = host
        self._port       = port
        self._c          = components      # shorthand
        self._start_time = start_time
        self._runner: Any = None
        self._site:   Any = None

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────
    async def start(self) -> None:
        if web is None:
            log.error(
                "IntrospectionAPI: aiohttp is not installed. "
                "Run: pip install aiohttp"
            )
            return

        app = web.Application(middlewares=[self._cors_middleware])
        app.router.add_get("/status",         self._handle_status)
        app.router.add_get("/memory",         self._handle_memory)
        app.router.add_get("/values",         self._handle_values)
        app.router.add_get("/strategy",       self._handle_strategy)
        app.router.add_get("/milestones",     self._handle_milestones)
        app.router.add_get("/dream",          self._handle_dream)
        app.router.add_get("/episodes",       self._handle_episodes)
        app.router.add_get("/search",         self._handle_search)
        app.router.add_get("/emotions",       self._handle_emotions)
        app.router.add_get("/reflection",     self._handle_reflection)
        app.router.add_get("/diary",          self._handle_diary)
        app.router.add_get("/diary/raw",      self._handle_diary_raw)
        app.router.add_get("/curiosity",      self._handle_curiosity)
        app.router.add_get("/modifications",  self._handle_modifications)
        app.router.add_get("/beliefs",        self._handle_beliefs)        # Stage 19
        app.router.add_get("/contradictions", self._handle_contradictions) # Stage 20

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        log.info(
            f"Introspection API started at "
            f"http://{self._host}:{self._port}"
        )

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            log.info("Introspection API stopped.")

    # ──────────────────────────────────────────────────────────────
    # Middleware
    # ──────────────────────────────────────────────────────────────
    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler) -> web.Response:
        if request.method == "OPTIONS":
            return web.Response(headers=_CORS_HEADERS)
        try:
            response = await handler(request)
        except web.HTTPException as e:
            e.headers.update(_CORS_HEADERS)
            raise
        response.headers.update(_CORS_HEADERS)
        return response

    # ──────────────────────────────────────────────────────────────
    # Handlers (only new ones shown, rest unchanged)
    # ──────────────────────────────────────────────────────────────

    async def _handle_beliefs(self, request: web.Request) -> web.Response:
        """GET /beliefs — Stage 19: active and strong beliefs + stats."""
        try:
            bs = self._c.get("belief_system")
            if bs is None:
                return self._json({
                    "active": [],
                    "strong": [],
                    "stats":  {},
                    "note":   "BeliefSystem not available",
                })
            
            active = bs.get_beliefs(status="active")
            strong = bs.get_beliefs(status="strong")
            stats = bs.get_stats()
            
            payload = {
                "active": active,
                "strong": strong,
                "stats":  stats,
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_contradictions(self, request: web.Request) -> web.Response:
        """GET /contradictions — Stage 20: pending and resolved contradictions + stats."""
        try:
            cr = self._c.get("contradiction_resolver")
            if cr is None:
                return self._json({
                    "pending":  [],
                    "resolved": [],
                    "stats":    {},
                    "note":     "ContradictionResolver not available",
                })
            
            pending = cr.get_pending()
            resolved = cr.get_resolved(5)
            stats = cr.get_stats()
            
            payload = {
                "pending":  pending,
                "resolved": resolved,
                "stats":    stats,
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    # ... (rest of handlers unchanged - status, memory, values, etc.)
    # Copy all other handlers from previous version

    def _json(self, data: dict) -> "web.Response":
        return web.Response(
            text=json.dumps(data, ensure_ascii=False, default=str),
            content_type="application/json",
        )

    def _error(self, exc: Exception) -> "web.Response":
        log.error(f"IntrospectionAPI handler error: {exc}")
        return web.Response(
            text=json.dumps({"error": str(exc)}),
            content_type="application/json",
            status=500,
        )
