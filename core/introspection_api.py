"""
Digital Being — IntrospectionAPI
Stage 24: Added /meta-cognition endpoint for MetaCognition.
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
    from core.meta_cognition import MetaCognition  # Stage 24
    from core.milestones import Milestones
    from core.narrative_engine import NarrativeEngine
    from core.ollama_client import OllamaClient
    from core.reflection_engine import ReflectionEngine
    from core.self_modification import SelfModificationEngine
    from core.shell_executor import ShellExecutor
    from core.strategy_engine import StrategyEngine
    from core.time_perception import TimePerception  # Stage 22
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.introspection_api")

_CORS_HEADERS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"}

class IntrospectionAPI:
    def __init__(self, host: str, port: int, components: dict, start_time: float) -> None:
        self._host, self._port, self._c, self._start_time = host, port, components, start_time
        self._runner, self._site = None, None

    async def start(self) -> None:
        if web is None:
            log.error("IntrospectionAPI: aiohttp is not installed. Run: pip install aiohttp")
            return
        app = web.Application(middlewares=[self._cors_middleware])
        app.router.add_get("/status", self._handle_status)
        app.router.add_get("/memory", self._handle_memory)
        app.router.add_get("/values", self._handle_values)
        app.router.add_get("/strategy", self._handle_strategy)
        app.router.add_get("/milestones", self._handle_milestones)
        app.router.add_get("/dream", self._handle_dream)
        app.router.add_get("/episodes", self._handle_episodes)
        app.router.add_get("/search", self._handle_search)
        app.router.add_get("/emotions", self._handle_emotions)
        app.router.add_get("/reflection", self._handle_reflection)
        app.router.add_get("/diary", self._handle_diary)
        app.router.add_get("/diary/raw", self._handle_diary_raw)
        app.router.add_get("/curiosity", self._handle_curiosity)
        app.router.add_get("/modifications", self._handle_modifications)
        app.router.add_get("/beliefs", self._handle_beliefs)
        app.router.add_get("/contradictions", self._handle_contradictions)
        app.router.add_get("/shell/stats", self._handle_shell_stats)
        app.router.add_post("/shell/execute", self._handle_shell_execute)
        app.router.add_get("/time", self._handle_time)  # Stage 22
        app.router.add_get("/meta-cognition", self._handle_meta_cognition)  # Stage 24
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        log.info(f"Introspection API started at http://{self._host}:{self._port}")

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            log.info("Introspection API stopped.")

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

    async def _handle_meta_cognition(self, request: web.Request) -> web.Response:
        """GET /meta-cognition - Stage 24"""
        try:
            meta_cog = self._c.get("meta_cognition")
            if not meta_cog:
                return self._json({"error": "MetaCognition not available"})
            
            state = meta_cog.get_current_state()
            insights = meta_cog._state.get("insights", [])
            decisions = meta_cog._state.get("decision_quality_log", [])
            
            return self._json({
                "current_state": state,
                "recent_insights": insights[-5:],
                "decision_log": decisions[-10:],
                "stats": meta_cog.get_stats()
            })
        except Exception as e:
            return self._error(e)

    async def _handle_time(self, request: web.Request) -> web.Response:
        """GET /time - Stage 22"""
        try:
            tp = self._c.get("time_perception")
            if not tp:
                return self._json({"error": "TimePerception not available"})
            
            current_context = tp._state.get("current_context", {})
            current_patterns = tp.get_current_patterns(min_confidence=0.5)
            all_patterns = tp.get_patterns(min_confidence=0.4)
            stats = tp.get_stats()
            
            return self._json({
                "current_context": current_context,
                "current_patterns": current_patterns,
                "all_patterns": all_patterns,
                "stats": stats,
            })
        except Exception as e:
            return self._error(e)

    async def _handle_shell_stats(self, request: web.Request) -> web.Response:
        """GET /shell/stats - Stage 21"""
        try:
            shell = self._c.get("shell_executor")
            if not shell:
                return self._json({"error": "ShellExecutor not available"})
            stats = shell.get_stats()
            allowed_commands = shell.get_allowed_commands()
            allowed_dir = shell.get_allowed_dir()
            payload = {"stats": stats, "allowed_commands": allowed_commands, "allowed_dir": allowed_dir}
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_shell_execute(self, request: web.Request) -> web.Response:
        """POST /shell/execute - Stage 21"""
        try:
            shell = self._c.get("shell_executor")
            mem = self._c.get("episodic")
            if not shell or not mem:
                return self._json({"error": "ShellExecutor or EpisodicMemory not available"})
            data = await request.json()
            command = data.get("command", "")
            if not command:
                return self._json({"error": "Missing command"})
            result = shell.execute_safe(command, mem)
            return self._json(result)
        except Exception as e:
            return self._error(e)

    async def _handle_status(self, request: web.Request) -> web.Response:
        try:
            uptime = time.time() - self._start_time
            mem = self._c.get("episodic")
            values = self._c.get("value_engine")
            ollama = self._c.get("ollama")
            gp = self._c.get("goal_persistence")
            attn = self._c.get("attention_system")
            payload = {"uptime_sec": int(uptime), "tick_count": getattr(self._c.get("heavy_tick"), "_tick_count", 0),
                       "mode": values.get_mode() if values else "unknown", "ollama_available": ollama.is_available() if ollama else False,
                       "episode_count": mem.count() if mem else 0, "attention_focus": attn.get_focus_summary() if attn else ""}
            if gp:
                ag = gp.get_active()
                payload["current_goal"] = ag.get("goal", "") if ag else "no active goal"
                payload["goal_stats"] = gp.get_stats()
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_memory(self, request: web.Request) -> web.Response:
        try:
            mem = self._c.get("episodic")
            vec = self._c.get("vector_memory")
            payload = {"episode_count": mem.count() if mem else 0, "vector_count": vec.count() if vec else 0,
                       "recent": mem.get_recent_episodes(10) if mem else []}
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_values(self, request: web.Request) -> web.Response:
        try:
            values = self._c.get("value_engine")
            if not values:
                return self._json({"error": "ValueEngine not available"})
            payload = {"scores": values.get_scores(), "mode": values.get_mode(),
                       "conflicts": {"exploration_vs_stability": values.get_conflict_winner("exploration_vs_stability"),
                                     "action_vs_caution": values.get_conflict_winner("action_vs_caution")}}
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_strategy(self, request: web.Request) -> web.Response:
        try:
            strategy = self._c.get("strategy_engine")
            if not strategy:
                return self._json({"error": "StrategyEngine not available"})
            state = strategy.to_dict()
            return self._json(state)
        except Exception as e:
            return self._error(e)

    async def _handle_milestones(self, request: web.Request) -> web.Response:
        try:
            milestones = self._c.get("milestones")
            if not milestones:
                return self._json({"error": "Milestones not available"})
            return self._json(milestones.to_dict())
        except Exception as e:
            return self._error(e)

    async def _handle_dream(self, request: web.Request) -> web.Response:
        try:
            dream = self._c.get("dream_mode")
            if not dream:
                return self._json({"error": "DreamMode not available"})
            payload = {"run_count": dream._run_count, "last_run": dream._last_run if dream._last_run else None,
                       "interval_hours": dream._interval_hours, "next_run_in_sec": dream.time_until_next() if dream._last_run else 0}
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_episodes(self, request: web.Request) -> web.Response:
        try:
            mem = self._c.get("episodic")
            if not mem:
                return self._json({"error": "EpisodicMemory not available"})
            limit = int(request.query.get("limit", "20"))
            event_type = request.query.get("event_type", "")
            if event_type:
                episodes = mem.get_episodes_by_type(event_type, limit=limit)
            else:
                episodes = mem.get_recent_episodes(limit)
            return self._json({"count": len(episodes), "episodes": episodes})
        except Exception as e:
            return self._error(e)

    async def _handle_search(self, request: web.Request) -> web.Response:
        try:
            query = request.query.get("q", "")
            if not query:
                return self._json({"error": "Missing query parameter 'q'"})
            top_k = int(request.query.get("top_k", "5"))
            vec = self._c.get("vector_memory")
            ollama = self._c.get("ollama")
            if not vec or not ollama:
                return self._json({"error": "VectorMemory or Ollama not available"})
            embedding = ollama.embed(query)
            if not embedding:
                return self._json({"error": "Failed to generate embedding"})
            results = vec.search(embedding, top_k=top_k)
            return self._json({"query": query, "top_k": top_k, "results": results})
        except Exception as e:
            return self._error(e)

    async def _handle_emotions(self, request: web.Request) -> web.Response:
        try:
            emotions = self._c.get("emotion_engine")
            if not emotions:
                return self._json({"error": "EmotionEngine not available"})
            dominant_name, dominant_val = emotions.get_dominant()
            payload = {"current": emotions.get_state(), "dominant": {"name": dominant_name, "value": dominant_val},
                       "tone_modifier": emotions.get_tone_modifier()}
            return self._json(payload)
        except Exception as e:
            return self._error(e)

    async def _handle_reflection(self, request: web.Request) -> web.Response:
        try:
            reflection = self._c.get("reflection_engine")
            if not reflection:
                return self._json({"error": "ReflectionEngine not available"})
            log_data = reflection.load_log()
            last_5 = log_data[-5:] if len(log_data) >= 5 else log_data
            return self._json({"last_5": last_5, "total_count": len(log_data)})
        except Exception as e:
            return self._error(e)

    async def _handle_diary(self, request: web.Request) -> web.Response:
        try:
            narrative = self._c.get("narrative_engine")
            if not narrative:
                return self._json({"error": "NarrativeEngine not available"})
            log_data = narrative.load_log()
            limit = int(request.query.get("limit", "5"))
            last_n = log_data[-limit:] if len(log_data) >= limit else log_data
            return self._json({"entries": last_n, "total_count": len(log_data)})
        except Exception as e:
            return self._error(e)

    async def _handle_diary_raw(self, request: web.Request) -> web.Response:
        try:
            narrative = self._c.get("narrative_engine")
            if not narrative:
                return web.Response(text="NarrativeEngine not available", content_type="text/plain", status=404)
            diary_path = narrative._memory_dir / "diary.md"
            if not diary_path.exists():
                return web.Response(text="Diary file not found", content_type="text/plain", status=404)
            diary_text = diary_path.read_text(encoding="utf-8")
            return web.Response(text=diary_text, content_type="text/plain")
        except Exception as e:
            return web.Response(text=f"Error: {e}", content_type="text/plain", status=500)

    async def _handle_curiosity(self, request: web.Request) -> web.Response:
        try:
            curiosity = self._c.get("curiosity_engine")
            if not curiosity:
                return self._json({"error": "CuriosityEngine not available"})
            open_q = curiosity.get_open_questions(10)
            stats = curiosity.get_stats()
            return self._json({"open_questions": open_q, "stats": stats})
        except Exception as e:
            return self._error(e)

    async def _handle_modifications(self, request: web.Request) -> web.Response:
        try:
            self_mod = self._c.get("self_modification")
            if not self_mod:
                return self._json({"error": "SelfModificationEngine not available"})
            history = self_mod.get_history(10)
            stats = self_mod.get_stats()
            return self._json({"history": history, "stats": stats})
        except Exception as e:
            return self._error(e)

    async def _handle_beliefs(self, request: web.Request) -> web.Response:
        try:
            bs = self._c.get("belief_system")
            if bs is None:
                return self._json({"active": [], "strong": [], "stats": {}, "note": "BeliefSystem not available"})
            active = bs.get_beliefs(status="active")
            strong = bs.get_beliefs(status="strong")
            stats = bs.get_stats()
            return self._json({"active": active, "strong": strong, "stats": stats})
        except Exception as e:
            return self._error(e)

    async def _handle_contradictions(self, request: web.Request) -> web.Response:
        try:
            cr = self._c.get("contradiction_resolver")
            if cr is None:
                return self._json({"pending": [], "resolved": [], "stats": {}, "note": "ContradictionResolver not available"})
            pending = cr.get_pending()
            resolved = cr.get_resolved(5)
            stats = cr.get_stats()
            return self._json({"pending": pending, "resolved": resolved, "stats": stats})
        except Exception as e:
            return self._error(e)

    def _json(self, data: dict) -> "web.Response":
        return web.Response(text=json.dumps(data, ensure_ascii=False, default=str), content_type="application/json")

    def _error(self, exc: Exception) -> "web.Response":
        log.error(f"IntrospectionAPI handler error: {exc}")
        return web.Response(text=json.dumps({"error": str(exc)}), content_type="application/json", status=500)
