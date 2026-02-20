"""
Digital Being — IntrospectionAPI
Stage 16: /status now includes attention_focus; attention_system added to components.

Endpoints (all GET, all return JSON unless noted):
  /status      — uptime, tick_count, mode, current goal, goal_stats, attention_focus [Stage 16]
  /memory      — episode count, vector count, recent episodes
  /values      — scores, mode, conflicts
  /strategy    — three planning horizons
  /milestones  — achieved / pending milestones
  /dream       — Dream Mode state and next-run ETA
  /episodes    — filtered episode search (?limit=20&event_type=...)
  /search      — semantic search via VectorMemory (?q=text&top_k=5)
  /emotions    — current emotional state, dominant emotion, tone modifier [Stage 12]
  /reflection  — last 5 reflections + total count [Stage 13]
  /diary       — last N diary entries from narrative_log.json [Stage 14]
  /diary/raw   — full diary.md as text/plain [Stage 14]

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
    from core.dream_mode import DreamMode
    from core.emotion_engine import EmotionEngine
    from core.goal_persistence import GoalPersistence
    from core.memory.episodic import EpisodicMemory
    from core.memory.vector_memory import VectorMemory
    from core.milestones import Milestones
    from core.narrative_engine import NarrativeEngine
    from core.ollama_client import OllamaClient
    from core.reflection_engine import ReflectionEngine
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
        app.router.add_get("/status",     self._handle_status)
        app.router.add_get("/memory",     self._handle_memory)
        app.router.add_get("/values",     self._handle_values)
        app.router.add_get("/strategy",   self._handle_strategy)
        app.router.add_get("/milestones", self._handle_milestones)
        app.router.add_get("/dream",      self._handle_dream)
        app.router.add_get("/episodes",   self._handle_episodes)
        app.router.add_get("/search",     self._handle_search)
        app.router.add_get("/emotions",   self._handle_emotions)   # Stage 12
        app.router.add_get("/reflection", self._handle_reflection) # Stage 13
        app.router.add_get("/diary",      self._handle_diary)      # Stage 14
        app.router.add_get("/diary/raw",  self._handle_diary_raw)  # Stage 14

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
            # Propagate aiohttp HTTP errors (400, 404, etc.) with CORS headers
            e.headers.update(_CORS_HEADERS)
            raise
        response.headers.update(_CORS_HEADERS)
        return response

    # ──────────────────────────────────────────────────────────────
    # Handlers
    # ──────────────────────────────────────────────────────────────
    async def _handle_status(self, request: web.Request) -> web.Response:
        try:
            heavy    = self._c.get("heavy_tick")
            values   = self._c["value_engine"]
            strategy = self._c["strategy_engine"]
            now_goal = strategy.get_now()

            # Stage 15: goal persistence stats
            gp = self._c.get("goal_persistence")
            goal_stats = gp.get_stats() if gp is not None else {
                "total_completed": 0,
                "resume_count":    0,
                "interrupted":     False,
            }

            # Stage 16: attention focus summary
            attn = self._c.get("attention_system")
            attention_focus = attn.get_focus_summary() if attn is not None else ""

            payload = {
                "uptime_seconds":  int(time.time() - self._start_time),
                "tick_count":      heavy._tick_count if heavy else 0,
                "current_mode":    values.get_mode(),
                "current_goal":    now_goal.get("goal", ""),
                "action_type":     now_goal.get("action_type", ""),
                "last_tick_at":    now_goal.get("created_at", ""),
                "goal_stats":      goal_stats,      # Stage 15
                "attention_focus": attention_focus, # Stage 16
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_memory(self, request: web.Request) -> web.Response:
        try:
            episodic = self._c["episodic"]
            vm       = self._c["vector_memory"]
            recent   = episodic.get_recent_episodes(5)
            # Sanitise: drop heavy 'data' JSON blobs
            for ep in recent:
                ep.pop("data", None)
            payload = {
                "episodic_count": episodic.count(),
                "vector_count":   vm.count(),
                "recent_episodes": recent,
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_values(self, request: web.Request) -> web.Response:
        try:
            ve = self._c["value_engine"]
            payload = {
                "scores":    ve.snapshot(),
                "mode":      ve.get_mode(),
                "conflicts": ve.get_conflicts(),
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_strategy(self, request: web.Request) -> web.Response:
        try:
            se = self._c["strategy_engine"]
            payload = {
                "now":      se.get_now(),
                "weekly":   se.get_weekly(),
                "longterm": se.get_longterm(),
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_milestones(self, request: web.Request) -> web.Response:
        try:
            ms = self._c["milestones"]
            payload = {
                "achieved": ms.get_achieved(),
                "pending":  ms.get_pending(),
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_dream(self, request: web.Request) -> web.Response:
        try:
            dm    = self._c["dream_mode"]
            state = dm.get_state()
            # Calculate next run ETA
            last  = state.get("last_run", "")
            interval_h = dm._interval_h
            next_in_h  = 0.0
            if last:
                try:
                    import time as _time
                    t = _time.mktime(_time.strptime(last, "%Y-%m-%dT%H:%M:%S"))
                    elapsed = (time.time() - t) / 3600
                    next_in_h = max(0.0, round(interval_h - elapsed, 2))
                except (ValueError, OverflowError):
                    pass
            payload = {
                "last_run":          state.get("last_run", ""),
                "run_count":         state.get("run_count", 0),
                "last_insights":     state.get("last_insights", []),
                "next_run_in_hours": next_in_h,
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_episodes(self, request: web.Request) -> web.Response:
        try:
            episodic   = self._c["episodic"]
            limit      = min(int(request.rel_url.query.get("limit", 20)), 100)
            event_type = request.rel_url.query.get("event_type", None)

            if event_type:
                rows = episodic.get_episodes_by_type(event_type, limit=limit)
            else:
                rows = episodic.get_recent_episodes(limit)

            for row in rows:
                row.pop("data", None)

            return self._json({"episodes": rows, "count": len(rows)})
        except Exception as e:
            return self._error(e)

    async def _handle_search(self, request: web.Request) -> web.Response:
        try:
            q = request.rel_url.query.get("q", "").strip()
            if not q:
                raise web.HTTPBadRequest(
                    reason="Missing required parameter: q",
                    content_type="application/json",
                    text=json.dumps({"error": "Missing required parameter: q"}),
                )

            top_k  = min(int(request.rel_url.query.get("top_k", 5)), 20)
            ollama = self._c["ollama"]
            vm     = self._c["vector_memory"]

            import asyncio
            loop      = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: ollama.embed(q[:1000])
            )
            if not embedding:
                return self._json({"results": [], "note": "embed returned empty"})

            results = vm.search(embedding, top_k=top_k)
            return self._json({"query": q, "top_k": top_k, "results": results})
        except web.HTTPException:
            raise
        except Exception as e:
            return self._error(e)

    async def _handle_emotions(self, request: web.Request) -> web.Response:
        """GET /emotions — Stage 12: return current emotional state."""
        try:
            ee = self._c.get("emotion_engine")
            if ee is None:
                return self._json({
                    "state":         {},
                    "dominant":      [None, 0.0],
                    "tone_modifier": "",
                    "note":          "EmotionEngine not available",
                })
            dominant_name, dominant_val = ee.get_dominant()
            payload = {
                "state":         ee.get_state(),
                "dominant":      [dominant_name, dominant_val],
                "tone_modifier": ee.get_tone_modifier(),
            }
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_reflection(self, request: web.Request) -> web.Response:
        """GET /reflection — Stage 13: return last reflections from log."""
        try:
            re_engine = self._c.get("reflection_engine")
            if re_engine is None:
                return self._json({
                    "last_reflections": [],
                    "total_count":      0,
                    "note":             "ReflectionEngine not available",
                })
            all_reflections = re_engine.load_log()
            total = len(all_reflections)
            last_5 = all_reflections[-5:] if total > 0 else []
            return self._json({
                "last_reflections": last_5,
                "total_count":      total,
            })
        except Exception as e:
            return self._error(e)

    async def _handle_diary(self, request: web.Request) -> web.Response:
        """GET /diary?limit=10 — Stage 14: last N diary entries."""
        try:
            ne = self._c.get("narrative_engine")
            if ne is None:
                return self._json({
                    "entries": [],
                    "total":   0,
                    "note":    "NarrativeEngine not available",
                })
            limit   = min(int(request.rel_url.query.get("limit", 10)), 100)
            records = ne.load_log()
            total   = len(records)
            entries = records[-limit:] if total > 0 else []
            return self._json({"entries": entries, "total": total})
        except Exception as e:
            return self._error(e)

    async def _handle_diary_raw(self, request: web.Request) -> web.Response:
        """GET /diary/raw — Stage 14: return diary.md as text/plain."""
        try:
            ne = self._c.get("narrative_engine")
            if ne is None:
                return web.Response(
                    text=json.dumps({"error": "NarrativeEngine not available"}),
                    content_type="application/json",
                    status=404,
                    headers=_CORS_HEADERS,
                )
            diary_path = ne._diary_path
            if not diary_path.exists():
                return web.Response(
                    text=json.dumps({"error": "diary not found"}),
                    content_type="application/json",
                    status=404,
                    headers=_CORS_HEADERS,
                )
            content = diary_path.read_text(encoding="utf-8")
            return web.Response(
                text=content,
                content_type="text/plain",
                charset="utf-8",
                headers=_CORS_HEADERS,
            )
        except Exception as e:
            return self._error(e)

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────
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
