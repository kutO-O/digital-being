"""
Digital Being — IntrospectionAPI
Stage 27.5: Added Web UI + Chat endpoints.
Stage 28-30: Added Advanced Multi-Agent, Memory, Self-Evolution endpoints.
Stage 31: Added Autoscaler endpoints.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from core.multi_agent.agent_roles import AgentRoleManager, AgentRole, ROLE_DEFINITIONS
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
    from core.meta_cognition import MetaCognition
    from core.milestones import Milestones
    from core.narrative_engine import NarrativeEngine
    from core.ollama_client import OllamaClient
    from core.reflection_engine import ReflectionEngine
    from core.self_modification import SelfModificationEngine
    from core.shell_executor import ShellExecutor
    from core.skill_library import SkillLibrary
    from core.strategy_engine import StrategyEngine
    from core.time_perception import TimePerception
    from core.value_engine import ValueEngine

log = logging.getLogger("digital_being.introspection_api")

_CORS_HEADERS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"}

class IntrospectionAPI:
    def __init__(self, host: str, port: int, components: dict, start_time: float) -> None:
        self._host, self._port, self._c, self._start_time = host, port, components, start_time
        self._runner, self._site = None, None
        self._web_ui_dir = Path(__file__).parent.parent / "web_ui"
        self._project_root = Path(__file__).parent.parent

    async def start(self) -> None:
        if web is None:
            log.error("IntrospectionAPI: aiohttp is not installed. Run: pip install aiohttp")
            return
        app = web.Application(middlewares=[self._cors_middleware])
        
        # Web UI static files
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/index.html", self._handle_index)
        app.router.add_get("/style.css", self._handle_css)
        app.router.add_get("/app.js", self._handle_js)
        app.router.add_get("/README.md", self._handle_readme)
        
        # Chat endpoints
        app.router.add_get("/chat/outbox", self._handle_chat_outbox)
        app.router.add_post("/chat/send", self._handle_chat_send)
        
        # Core API endpoints
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
        app.router.add_get("/time", self._handle_time)
        app.router.add_get("/meta-cognition", self._handle_meta_cognition)
        app.router.add_get("/skills", self._handle_skills)
        app.router.add_get("/multi-agent", self._handle_multi_agent)
        
        # Stage 28: Advanced Multi-Agent
        app.router.add_get("/multi-agent/roles", self._handle_agent_roles)
        app.router.add_get("/multi-agent/tasks", self._handle_tasks)
        app.router.add_get("/multi-agent/proposals", self._handle_proposals)
        app.router.add_post("/multi-agent/vote", self._handle_vote)
        
        # Stage 29: Long-term Memory
        app.router.add_get("/memory/consolidated", self._handle_consolidated_memory)
        app.router.add_get("/memory/semantic", self._handle_semantic_memory)
        app.router.add_get("/memory/concepts", self._handle_concepts)
        app.router.add_get("/memory/facts", self._handle_facts)
        app.router.add_get("/memory/retrieval-stats", self._handle_retrieval_stats)
        
        # Stage 30: Self-Evolution
        app.router.add_get("/evolution/stats", self._handle_evolution_stats)
        app.router.add_get("/evolution/proposals", self._handle_evolution_proposals)
        app.router.add_get("/evolution/history", self._handle_evolution_history)
        app.router.add_post("/evolution/approve", self._handle_approve_change)
        app.router.add_post("/evolution/reject", self._handle_reject_change)
        
        # Stage 31: Autoscaler
        app.router.add_get("/autoscaler/stats", self._handle_autoscaler_stats)
        app.router.add_get("/autoscaler/events", self._handle_autoscaler_events)
        app.router.add_post("/autoscaler/check", self._handle_autoscaler_check)
        app.router.add_post("/autoscaler/enable", self._handle_autoscaler_enable)
        app.router.add_post("/autoscaler/disable", self._handle_autoscaler_disable)
        
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

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve index.html"""
        try:
            index_path = self._web_ui_dir / "index.html"
            if not index_path.exists():
                return web.Response(text="Web UI not found", status=404)
            content = index_path.read_text(encoding="utf-8")
            return web.Response(text=content, content_type="text/html")
        except Exception as e:
            log.error(f"Error serving index.html: {e}")
            return web.Response(text=f"Error: {e}", status=500)

    async def _handle_css(self, request: web.Request) -> web.Response:
        """Serve style.css"""
        try:
            css_path = self._web_ui_dir / "style.css"
            if not css_path.exists():
                return web.Response(text="style.css not found", status=404)
            content = css_path.read_text(encoding="utf-8")
            return web.Response(text=content, content_type="text/css")
        except Exception as e:
            log.error(f"Error serving style.css: {e}")
            return web.Response(text=f"Error: {e}", status=500)

    async def _handle_js(self, request: web.Request) -> web.Response:
        """Serve app.js"""
        try:
            js_path = self._web_ui_dir / "app.js"
            if not js_path.exists():
                return web.Response(text="app.js not found", status=404)
            content = js_path.read_text(encoding="utf-8")
            return web.Response(text=content, content_type="application/javascript")
        except Exception as e:
            log.error(f"Error serving app.js: {e}")
            return web.Response(text=f"Error: {e}", status=500)

    async def _handle_readme(self, request: web.Request) -> web.Response:
        """Serve README.md"""
        try:
            readme_path = self._web_ui_dir / "README.md"
            if not readme_path.exists():
                return web.Response(text="README.md not found", status=404)
            content = readme_path.read_text(encoding="utf-8")
            return web.Response(text=content, content_type="text/markdown")
        except Exception as e:
            log.error(f"Error serving README.md: {e}")
            return web.Response(text=f"Error: {e}", status=500)

    async def _handle_chat_outbox(self, request: web.Request) -> web.Response:
        """GET /chat/outbox - Read outbox.txt"""
        try:
            outbox_path = self._project_root / "outbox.txt"
            if not outbox_path.exists():
                return self._json({"messages": []})
            
            content = outbox_path.read_text(encoding="utf-8")
            
            # Parse messages
            messages = []
            for block in content.split("\n\n--- ["):
                if not block.strip():
                    continue
                if "] Digital Being ---" in block:
                    parts = block.split("] Digital Being ---\n", 1)
                    if len(parts) == 2:
                        timestamp = parts[0].strip()
                        message = parts[1].strip()
                        messages.append({
                            "timestamp": timestamp,
                            "message": message
                        })
            
            return self._json({"messages": messages})
        except Exception as e:
            log.error(f"Error reading outbox: {e}")
            return self._error(e)

    async def _handle_chat_send(self, request: web.Request) -> web.Response:
        """POST /chat/send - Write to inbox.txt"""
        try:
            data = await request.json()
            message = data.get("message", "").strip()
            
            if not message:
                return self._json({"error": "Empty message"})
            
            inbox_path = self._project_root / "memory" / "inbox.txt"
            inbox_path.parent.mkdir(exist_ok=True)
            
            # Append message
            with inbox_path.open("a", encoding="utf-8") as f:
                f.write(f"\n{message}\n")
            
            return self._json({"success": True, "message": "Сообщение добавлено в inbox.txt"})
        except Exception as e:
            log.error(f"Error writing to inbox: {e}")
            return self._error(e)

    # ========== Stage 31: Autoscaler ==========
    
    async def _handle_autoscaler_stats(self, request: web.Request) -> web.Response:
        """GET /autoscaler/stats - Autoscaler statistics"""
        try:
            autoscaler = self._c.get("autoscaler")
            if not autoscaler:
                return self._json({"error": "Autoscaler not available or not enabled"})
            
            stats = autoscaler.get_stats()
            
            return self._json(stats)
        except Exception as e:
            return self._error(e)
    
    async def _handle_autoscaler_events(self, request: web.Request) -> web.Response:
        """GET /autoscaler/events - Recent scaling events"""
        try:
            autoscaler = self._c.get("autoscaler")
            if not autoscaler:
                return self._json({"error": "Autoscaler not available or not enabled"})
            
            limit = int(request.query.get("limit", "20"))
            events = autoscaler._state.get("scaling_events", [])[-limit:]
            
            return self._json({
                "events": events,
                "count": len(events)
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_autoscaler_check(self, request: web.Request) -> web.Response:
        """POST /autoscaler/check - Trigger immediate scaling check"""
        try:
            autoscaler = self._c.get("autoscaler")
            if not autoscaler:
                return self._json({"error": "Autoscaler not available or not enabled"})
            
            result = await autoscaler.check_and_scale()
            
            return self._json({
                "success": True,
                "result": result
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_autoscaler_enable(self, request: web.Request) -> web.Response:
        """POST /autoscaler/enable - Enable autoscaling"""
        try:
            autoscaler = self._c.get("autoscaler")
            if not autoscaler:
                return self._json({"error": "Autoscaler not available"})
            
            autoscaler._enabled = True
            
            return self._json({
                "success": True,
                "message": "Autoscaler enabled"
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_autoscaler_disable(self, request: web.Request) -> web.Response:
        """POST /autoscaler/disable - Disable autoscaling"""
        try:
            autoscaler = self._c.get("autoscaler")
            if not autoscaler:
                return self._json({"error": "Autoscaler not available"})
            
            autoscaler._enabled = False
            
            return self._json({
                "success": True,
                "message": "Autoscaler disabled"
            })
        except Exception as e:
            return self._error(e)

    # ========== Stage 28: Advanced Multi-Agent ==========
    
    async def _handle_agent_roles(self, request: web.Request) -> web.Response:
        """GET /multi-agent/roles - Agent roles and capabilities"""
        try:
            multi_agent = self._c.get("multi_agent")
            if not multi_agent:
                return self._json({"error": "MultiAgentCoordinator not available"})
            
            agent_roles = multi_agent._role_manager
            if not agent_roles:
                return self._json({"error": "AgentRoles not initialized"})
            
            current_role = agent_roles.get_current_role()
            capabilities = agent_roles.get_capabilities()
            preferred_tasks = agent_roles.get_preferred_tasks()
            stats = agent_roles.get_all_stats()

            return self._json({
                "current_role": current_role,
                "capabilities": capabilities,
                "preferred_tasks": preferred_tasks,
                "stats": stats,
                "available_roles": [role.value for role in AgentRole]
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_tasks(self, request: web.Request) -> web.Response:
        """GET /multi-agent/tasks - Active and completed tasks"""
        try:
            multi_agent = self._c.get("multi_agent")
            if not multi_agent:
                return self._json({"error": "MultiAgentCoordinator not available"})
            
            task_delegation = multi_agent._task_delegation
            if not task_delegation:
                return self._json({"error": "TaskDelegation not initialized"})
            
            active = task_delegation.get_pending_tasks()
            completed = [t for t in task_delegation._state.get("tasks_created", []) 
                        if t.get("status") == "completed"][-10:]
            stats = task_delegation.get_stats()
            
            return self._json({
                "active_tasks": active,
                "recent_completed": completed,
                "stats": stats
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_proposals(self, request: web.Request) -> web.Response:
        """GET /multi-agent/proposals - Active voting proposals"""
        try:
            multi_agent = self._c.get("multi_agent")
            if not multi_agent:
                return self._json({"error": "MultiAgentCoordinator not available"})
            
            consensus = multi_agent._consensus_builder
            if not consensus:
                return self._json({"error": "ConsensusBuilder not initialized"})
            
            active = [p for p in consensus._state.get("proposals_created", []) 
                    if p.get("status") == "open"]
            recent = consensus._state.get("proposals_created", [])[-5:]
            stats = consensus.get_stats()
            
            return self._json({
                "active_proposals": active,
                "recent_proposals": recent,
                "stats": stats
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_vote(self, request: web.Request) -> web.Response:
        """POST /multi-agent/vote - Cast a vote on proposal"""
        try:
            multi_agent = self._c.get("multi_agent")
            if not multi_agent:
                return self._json({"error": "MultiAgentCoordinator not available"})
            
            data = await request.json()
            proposal_id = data.get("proposal_id")
            agent_id = data.get("agent_id")
            vote = data.get("vote")  # True/False
            
            if not all([proposal_id, agent_id, vote is not None]):
                return self._json({"error": "Missing required fields"})
            
            consensus = multi_agent._consensus_builder
            consensus.cast_vote(proposal_id, vote, weight=1.0, reasoning="")
            
            # Check if resolved
            result = consensus.get_result(proposal_id)
            
            return self._json({
                "success": True,
                "result": result
            })
        except Exception as e:
            return self._error(e)
    
    # ========== Stage 29: Long-term Memory ==========
    
    async def _handle_consolidated_memory(self, request: web.Request) -> web.Response:
        """GET /memory/consolidated - Consolidated long-term memories"""
        try:
            mem_consolidation = self._c.get("memory_consolidation")
            if not mem_consolidation:
                return self._json({"error": "MemoryConsolidation not available"})
            
            limit = int(request.query.get("limit", "20"))
            important = mem_consolidation.get_important_memories(limit)
            stats = mem_consolidation.get_stats()
            
            return self._json({
                "important_memories": important,
                "stats": stats
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_semantic_memory(self, request: web.Request) -> web.Response:
        """GET /memory/semantic - Semantic memory stats"""
        try:
            semantic = self._c.get("semantic_memory")
            if not semantic:
                return self._json({"error": "SemanticMemory not available"})
            
            stats = semantic.get_stats()
            
            return self._json({
                "stats": stats
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_concepts(self, request: web.Request) -> web.Response:
        """GET /memory/concepts - Search concepts"""
        try:
            semantic = self._c.get("semantic_memory")
            if not semantic:
                return self._json({"error": "SemanticMemory not available"})
            
            query = request.query.get("q", "")
            concept_type = request.query.get("type", "")
            
            if query:
                concepts = semantic.search_concepts(query, concept_type if concept_type else None)
            else:
                # Return all concepts (limited)
                all_concepts = list(semantic._state["concepts"].values())[:50]
                concepts = sorted(all_concepts, key=lambda c: c["confidence"], reverse=True)
            
            return self._json({
                "concepts": concepts,
                "count": len(concepts)
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_facts(self, request: web.Request) -> web.Response:
        """GET /memory/facts - Search facts"""
        try:
            semantic = self._c.get("semantic_memory")
            if not semantic:
                return self._json({"error": "SemanticMemory not available"})
            
            keyword = request.query.get("q", "")
            
            if keyword:
                facts = semantic.get_facts_about(keyword)
            else:
                facts = semantic._state["facts"][-20:]  # Last 20
            
            return self._json({
                "facts": facts,
                "count": len(facts)
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_retrieval_stats(self, request: web.Request) -> web.Response:
        """GET /memory/retrieval-stats - Memory retrieval statistics"""
        try:
            retrieval = self._c.get("memory_retrieval")
            if not retrieval:
                return self._json({"error": "MemoryRetrieval not available"})
            
            stats = retrieval.get_stats()
            
            return self._json({
                "stats": stats
            })
        except Exception as e:
            return self._error(e)
    
    # ========== Stage 30: Self-Evolution ==========
    
    async def _handle_evolution_stats(self, request: web.Request) -> web.Response:
        """GET /evolution/stats - Self-evolution statistics"""
        try:
            evolution = self._c.get("self_evolution")
            if not evolution:
                return self._json({"error": "SelfEvolutionManager not available"})
            
            stats = evolution.get_stats()
            
            return self._json({
                "stats": stats
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_evolution_proposals(self, request: web.Request) -> web.Response:
        """GET /evolution/proposals - Pending evolution proposals"""
        try:
            evolution = self._c.get("self_evolution")
            if not evolution:
                return self._json({"error": "SelfEvolutionManager not available"})
            
            pending = evolution.get_pending_approvals()
            
            return self._json({
                "pending_proposals": pending,
                "count": len(pending)
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_evolution_history(self, request: web.Request) -> web.Response:
        """GET /evolution/history - Evolution change history"""
        try:
            evolution = self._c.get("self_evolution")
            if not evolution:
                return self._json({"error": "SelfEvolutionManager not available"})
            
            limit = int(request.query.get("limit", "20"))
            history = evolution.get_change_history(limit)
            
            return self._json({
                "history": history,
                "count": len(history)
            })
        except Exception as e:
            return self._error(e)
    
    async def _handle_approve_change(self, request: web.Request) -> web.Response:
        """POST /evolution/approve - Approve a pending change"""
        try:
            evolution = self._c.get("self_evolution")
            if not evolution:
                return self._json({"error": "SelfEvolutionManager not available"})
            
            data = await request.json()
            proposal_id = data.get("proposal_id")
            
            if not proposal_id:
                return self._json({"error": "Missing proposal_id"})
            
            result = evolution.approve_change(proposal_id)
            
            return self._json(result)
        except Exception as e:
            return self._error(e)
    
    async def _handle_reject_change(self, request: web.Request) -> web.Response:
        """POST /evolution/reject - Reject a pending change"""
        try:
            evolution = self._c.get("self_evolution")
            if not evolution:
                return self._json({"error": "SelfEvolutionManager not available"})
            
            data = await request.json()
            proposal_id = data.get("proposal_id")
            reason = data.get("reason", "")
            
            if not proposal_id:
                return self._json({"error": "Missing proposal_id"})
            
            result = evolution.reject_change(proposal_id, reason)
            
            return self._json(result)
        except Exception as e:
            return self._error(e)
    
    # ========== Original Handlers ==========

    async def _handle_multi_agent(self, request: web.Request) -> web.Response:
        """GET /multi-agent - Stage 27"""
        try:
            multi_agent = self._c.get("multi_agent")
            if not multi_agent:
                return self._json({"error": "MultiAgentCoordinator not available"})
            
            stats = multi_agent.get_stats()
            online = multi_agent.get_online_agents()
            
            return self._json({
                "online_agents": online,
                "stats": stats
            })
        except Exception as e:
            return self._error(e)

    async def _handle_skills(self, request: web.Request) -> web.Response:
        """GET /skills - Stage 26"""
        try:
            skill_lib = self._c.get("skill_library")
            if not skill_lib:
                return self._json({"error": "SkillLibrary not available"})
            
            all_skills = skill_lib._skills
            sorted_skills = sorted(all_skills, key=lambda x: x.get("confidence", 0.0), reverse=True)
            stats = skill_lib.get_stats()
            
            return self._json({
                "skills": sorted_skills,
                "stats": stats
            })
        except Exception as e:
            return self._error(e)

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
            emotions = self._c.get("emotion_engine")
            
            payload = {
                "uptime_sec": int(uptime),
                "tick_count": getattr(self._c.get("heavy_tick"), "_tick_count", 0),
                "mode": values.get_mode() if values else "unknown",
                "ollama_available": ollama.is_available() if ollama else False,
                "episode_count": mem.count() if mem else 0,
                "attention_focus": attn.get_focus_summary() if attn else ""
            }
            
            if gp:
                ag = gp.get_active()
                payload["current_goal"] = ag.get("goal", "") if ag else "no active goal"
                payload["goal_stats"] = gp.get_stats()
            
            if emotions:
                dominant_name, dominant_val = emotions.get_dominant()
                payload["emotions"] = {
                    "dominant": {"name": dominant_name, "value": dominant_val},
                    "all": emotions.get_state()
                }
            
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
            limit = int(request.query.get("limit", "50"))
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
