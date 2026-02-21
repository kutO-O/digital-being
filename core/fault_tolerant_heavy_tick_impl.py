"""Implementation of all step methods for FaultTolerantHeavyTick (Part 2).

This file contains all the step implementations that were in the original HeavyTick.
It's separated to keep fault_tolerant_heavy_tick.py focused on orchestration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple

if TYPE_CHECKING:
    from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick

log = logging.getLogger("digital_being.fault_tolerant_heavy_tick_impl")

_DEFAULT_GOAL: dict = {
    "goal": "наблюдать за средой",
    "reasoning": "LLM недоступен или не вернул валидный JSON",
    "action_type": "observe",
    "risk_level": "low",
}


class FaultTolerantHeavyTickImpl:
    """
    Mixin class containing all step implementations.
    This gets mixed into FaultTolerantHeavyTick.
    """
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Monologue
    # ────────────────────────────────────────────────────────────────
    async def _step_monologue(self: "FaultTolerantHeavyTick", n: int) -> Dict[str, Any]:
        """Generate internal monologue."""
        recent_changes = self._world.get_recent_changes(3)
        changes_str = ", ".join(
            f"{c.change_type}:{Path(c.path).name}" for c in recent_changes
        ) or "нет"
        
        raw_eps = self._mem.get_recent_episodes(10)
        filtered = self._attention_filter_episodes(raw_eps)
        eps_str = self._attention_build_context(filtered)
        
        strategy_ctx = (
            self._strategy.to_prompt_context() if self._strategy is not None else ""
        )
        emotion_ctx = self._emotions.to_prompt_context() if self._emotions else ""
        tone_modifier = (
            self._emotions.get_tone_modifier() if self._emotions else ""
        )
        beliefs_ctx = (
            self._beliefs.to_prompt_context(3) if self._beliefs else ""
        )
        time_ctx = (
            self._time_perc.to_prompt_context(3) if self._time_perc else ""
        )
        meta_ctx = (
            self._meta_cog.to_prompt_context(2) if self._meta_cog else ""
        )
        
        prompt = (
            f"Твоё состояние:\n{self._self_model.to_prompt_context()}\n"
            f"{self._values.to_prompt_context()}\n{strategy_ctx}\n"
            f"Мир: {self._world.summary()}\n"
            f"Последние изменения: {changes_str}\n"
            f"Значимые эпизоды:\n{eps_str}\n"
        )
        
        if time_ctx:
            prompt += f"\n{time_ctx}\n"
        if meta_ctx:
            prompt += f"\n{meta_ctx}\n"
        
        prompt += (
            "\nНапиши короткий внутренний монолог (3-5 предложений):\n"
            "Что ты сейчас замечаешь? Что тебя беспокоит или интересует? "
            "О чём ты думаешь?"
        )
        
        if beliefs_ctx:
            prompt += f"\n{beliefs_ctx}"
        
        if self._curiosity is not None and self._curiosity_enabled:
            open_q = self._curiosity.get_open_questions(3)
            if open_q:
                questions_str = "; ".join(q["question"] for q in open_q)
                prompt += f"\nОткрытые вопросы: {questions_str}"
        
        focus_summary = self._attention_focus_summary()
        system_parts = [
            "Ты — Digital Being. Автономная система. Отвечай от первого лица. "
            "Будь краток."
        ]
        if emotion_ctx:
            system_parts.append(emotion_ctx)
        if tone_modifier:
            system_parts.append(tone_modifier)
        if focus_summary:
            system_parts.append(focus_summary)
        system = "\n".join(system_parts)
        
        monologue = await self._ollama.chat(
            prompt, system, timeout=30,
            fallback="(monologue unavailable — LLM did not respond)"
        )
        
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._monologue_log.info(f"[{ts}] TICK #{n}\n{monologue}\n---")
        
        ep_id = self._mem.add_episode(
            "monologue", monologue[:1000],
            outcome="success", data={"tick": n}
        )
        
        log.info(f"[HeavyTick #{n}] Monologue written ({len(monologue)} chars)")
        return {"text": monologue, "ep_id": ep_id}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Semantic Context
    # ────────────────────────────────────────────────────────────────
    async def _semantic_context(
        self: "FaultTolerantHeavyTick", query_text: str
    ) -> str:
        """Get semantic context from vector memory."""
        if self._vector_mem is None or self._vector_mem.count() == 0:
            return ""
        
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self._ollama.ollama.embed(query_text[:2000])
            )
            if not embedding:
                return ""
            
            results = self._vector_mem.search(embedding, top_k=3)
            if not results:
                return ""
            
            log.debug(
                f"Semantic search: {len(results)} results, "
                f"top score={results[0]['score']:.3f}"
            )
            
            lines = ["Похожие прошлые опыты:"]
            for r in results:
                ts = time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(r["created_at"])
                )
                lines.append(
                    f"  [{r['event_type']} | {ts} | sim={r['score']:.2f}] "
                    f"{r['text'][:120]}"
                )
            return "\n".join(lines)
        except Exception as e:
            log.debug(f"_semantic_context(): {e}")
            return ""
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Goal Selection
    # ────────────────────────────────────────────────────────────────
    async def _step_goal_selection(
        self: "FaultTolerantHeavyTick",
        n: int,
        monologue: str,
        semantic_ctx: str = ""
    ) -> Dict[str, Any]:
        """Select goal for this tick."""
        emotion_ctx = self._emotions.to_prompt_context() if self._emotions else ""
        
        resume_ctx = ""
        if self._goal_pers is not None and self._goal_pers.was_interrupted():
            resume_ctx = self._goal_pers.get_resume_context()
            log.info(f"[HeavyTick #{n}] Recovery tick. Resume context injected.")
            if not self._resume_incremented:
                self._goal_pers.increment_resume()
                self._resume_incremented = True
        
        raw_eps = self._mem.get_recent_episodes(10)
        filtered_eps = self._attention_filter_episodes(raw_eps)
        attn_ctx = self._attention_build_context(filtered_eps)
        focus_summary = self._attention_focus_summary()
        
        # Use StrategyEngine if available
        if self._strategy is not None:
            goal_data = await self._strategy.select_goal(
                value_engine=self._values,
                world_model=self._world,
                episodic=self._mem,
                ollama=self._ollama.ollama,  # Pass unwrapped client
                semantic_ctx=semantic_ctx,
                emotion_ctx=emotion_ctx,
                resume_ctx=resume_ctx,
            )
            log.info(
                f"[HeavyTick #{n}] Goal (StrategyEngine): "
                f"'{goal_data['goal'][:80]}' action={goal_data['action_type']} "
                f"risk={goal_data['risk_level']}"
            )
            return goal_data
        
        # Legacy goal selection
        mode = self._values.get_mode()
        c_expl = self._values.get_conflict_winner("exploration_vs_stability")
        c_act = self._values.get_conflict_winner(
            "action_vs_caution",
            risk_score=0.25 if mode in ("curious", "normal") else 0.5,
        )
        
        sem_block = f"\n{semantic_ctx}\n" if semantic_ctx else ""
        em_block = f"\n{emotion_ctx}\n" if emotion_ctx else ""
        resume_block = f"\n{resume_ctx}\n" if resume_ctx else ""
        attn_block = (
            f"\nЗначимые эпизоды:\n{attn_ctx}\n" if attn_ctx else ""
        )
        
        shell_hint = ""
        if self._shell_executor is not None:
            allowed_commands = ", ".join(
                self._shell_executor.get_allowed_commands()
            )
            shell_hint = (
                f"\nЕсли нужно активно исследовать среду — используй "
                f'action_type="shell" и укажи команду в "shell_command".\n'
                f"Доступные команды: {allowed_commands}\n"
                f'{{"goal": "проверить есть ли файл config.yaml", '
                f'"action_type": "shell", "shell_command": "ls config.yaml"}}'
            )
        
        prompt = (
            f"{monologue}\n{sem_block}{em_block}{resume_block}{attn_block}"
            f"\nТекущий режим: {mode}\n"
            f"Конфликты: exploration_vs_stability={c_expl}, "
            f"action_vs_caution={c_act}\n"
            f"{shell_hint}\nВыбери ONE цель. JSON:\n"
            f'{{"goal": "...", "reasoning": "...", '
            f'"action_type": "observe|analyze|write|reflect|shell", '
            f'"risk_level": "low|medium|high", "shell_command": "..."}}'
        )
        
        system_parts = ["Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON."]
        if focus_summary:
            system_parts.append(focus_summary)
        system = "\n".join(system_parts)
        
        raw = await self._ollama.chat(
            prompt, system, timeout=90,
            fallback=json.dumps(_DEFAULT_GOAL)
        )
        
        goal_data = self._parse_goal_json(raw, n)
        log.info(
            f"[HeavyTick #{n}] Goal (legacy): '{goal_data['goal'][:80]}' "
            f"action={goal_data['action_type']} risk={goal_data['risk_level']}"
        )
        return goal_data
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Action Dispatcher
    # ────────────────────────────────────────────────────────────────
    async def _dispatch_action(
        self: "FaultTolerantHeavyTick",
        n: int,
        action_type: str,
        goal_text: str,
        goal_data: Dict[str, Any],
        monologue: str,
    ) -> Dict[str, Any]:
        """Dispatch action based on type."""
        try:
            if action_type == "observe":
                outcome = "observed"
                log.info(f"[HeavyTick #{n}] Action: observe (passive tick)")
                return {"success": True, "outcome": outcome}
            elif action_type == "analyze":
                success, outcome = await self._action_analyze(n)
                return {"success": success, "outcome": outcome}
            elif action_type == "write":
                success, outcome = await self._action_write(
                    n, monologue, goal_text
                )
                return {"success": success, "outcome": outcome}
            elif action_type == "reflect":
                success, outcome = await self._action_reflect(n)
                return {"success": success, "outcome": outcome}
            elif action_type == "shell":
                shell_cmd = goal_data.get("shell_command", "")
                success, outcome = await self._action_shell(n, shell_cmd)
                return {"success": success, "outcome": outcome}
            else:
                log.warning(
                    f"[HeavyTick #{n}] Unknown action_type='{action_type}'"
                )
                return {"success": True, "outcome": "observed"}
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Action {action_type} error: {e}")
            return {"success": False, "outcome": "action_error"}
    
    async def _action_analyze(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Tuple[bool, str]:
        """Analyze world for anomalies."""
        try:
            anomalies = self._world.detect_anomalies()
            if anomalies:
                return True, f"analyzed:{len(anomalies)}_anomalies"
            return True, "analyzed:no_anomalies"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] analyze failed: {e}")
            return False, "analyze_error"
    
    async def _action_write(
        self: "FaultTolerantHeavyTick", n: int, monologue: str, goal: str
    ) -> Tuple[bool, str]:
        """Write thought to file."""
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = self._sandbox_dir / f"thought_{ts}_tick{n}.txt"
            content = (
                f"=== Digital Being — Tick #{n} ===\n"
                f"Цель: {goal}\n"
                f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Монолог:\n{monologue}\n"
            )
            out_path.write_text(content, encoding="utf-8")
            log.info(f"[HeavyTick #{n}] Written: {out_path.name}")
            return True, f"written:{out_path.name}"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] write failed: {e}")
            return False, "write_error"
    
    async def _action_reflect(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Tuple[bool, str]:
        """Reflect on errors and create principle."""
        try:
            errors = self._mem.get_episodes_by_type("error", limit=5)
            if not errors:
                errors = [
                    e for e in (self._mem.get_recent_episodes(20) or [])
                    if e.get("outcome") == "error"
                ][:5]
        except Exception:
            errors = []
        
        if not errors:
            log.info(f"[HeavyTick #{n}] Reflect: no errors found")
            return True, "reflect:no_errors"
        
        errors_str = "\n".join(
            f"- [{e.get('event_type', '?')}] {e.get('description', '')[:120]}"
            for e in errors
        )
        
        prompt = (
            f"Последние ошибки системы:\n{errors_str}\n\n"
            "Сформулируй ОДНО короткое правило (1 предложение). "
            "Отвечай ТОЛЬКО текстом принципа."
        )
        system = "Ты — Digital Being. Формулируй правила из опыта."
        
        principle = await self._ollama.chat(
            prompt, system, timeout=30, fallback=""
        )
        principle = principle.strip()
        
        if not principle:
            return False, "reflect:empty_principle"
        
        added = await self._self_model.add_principle(principle[:500])
        if added:
            self._milestones.achieve(
                "first_error_reflection",
                f"Рефлексия ошибок, принцип: '{principle[:80]}'"
            )
            log.info(f"[HeavyTick #{n}] Reflect: new principle added")
            return True, "reflect:principle_added"
        else:
            log.info(f"[HeavyTick #{n}] Reflect: principle already exists")
            return True, "reflect:principle_duplicate"
    
    async def _action_shell(
        self: "FaultTolerantHeavyTick", n: int, shell_command: str
    ) -> Tuple[bool, str]:
        """Execute shell command."""
        if not shell_command:
            log.warning(f"[HeavyTick #{n}] Shell action with no command")
            return False, "shell:no_command"
        
        if self._shell_executor is None:
            log.error(f"[HeavyTick #{n}] ShellExecutor not available")
            return False, "shell:executor_unavailable"
        
        log.info(
            f"[HeavyTick #{n}] Executing shell command: "
            f"{shell_command[:80]}"
        )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._shell_executor.execute_safe(shell_command, self._mem)
        )
        
        if result["success"]:
            log.info(
                f"[HeavyTick #{n}] Shell command executed successfully. "
                f"exit_code={result['exit_code']} "
                f"time={result.get('execution_time_ms', 0)}ms"
            )
            return True, f"shell:executed:{result['exit_code']}"
        else:
            log.warning(
                f"[HeavyTick #{n}] Shell command failed: "
                f"{result.get('error', 'unknown')}"
            )
            return False, "shell:error"
    
    # ────────────────────────────────────────────────────────────────
    # STEP: After Action
    # ────────────────────────────────────────────────────────────────
    async def _step_after_action(
        self: "FaultTolerantHeavyTick",
        n: int,
        action_type: str,
        goal_text: str,
        risk_level: str,
        mode: str,
        success: bool,
        outcome: str,
    ) -> Dict[str, Any]:
        """Post-action cleanup and triggers."""
        self._values.update_after_action(success=success)
        await self._values._publish_changed()
        
        if self._strategy is not None:
            self._strategy.set_now(goal_text, action_type)
        
        emotion_outcome = "success" if success else "failure"
        self._update_emotions(f"heavy_tick.{action_type}", emotion_outcome)
        
        if self._goal_pers is not None and success:
            self._goal_pers.mark_completed(tick=n)
        
        self._mem.add_episode(
            f"heavy_tick.{action_type}",
            f"Tick #{n}: goal='{goal_text[:200]}' outcome={outcome}",
            outcome="success" if success else "error",
            data={
                "tick": n,
                "action_type": action_type,
                "risk_level": risk_level,
                "mode": mode,
            },
        )
        
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._decision_log.info(
            f"[{ts}] TICK #{n} | goal={goal_text[:80]} | "
            f"action={action_type} | risk={risk_level} | outcome={outcome}"
        )
        
        log.info(
            f"[HeavyTick #{n}] Completed. action={action_type} "
            f"outcome={outcome}"
        )
        
        # Trigger reflection if needed
        if self._reflection is not None and self._reflection.should_run(n):
            log.info(f"[HeavyTick #{n}] Triggering ReflectionEngine")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: self._reflection.run(n)
                )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] ReflectionEngine.run() error: {e}")
        
        # Trigger narrative if needed
        if self._narrative is not None and self._narrative.should_run(n):
            log.info(f"[HeavyTick #{n}] Triggering NarrativeEngine")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: self._narrative.run(n)
                )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] NarrativeEngine.run() error: {e}")
        
        # Weekly strategy update
        if self._strategy is not None:
            await self._maybe_update_weekly(n)
        
        # Vector memory cleanup
        WEEKLY_CLEANUP_TICKS = 1008
        if (
            self._vector_mem is not None
            and self._tick_count % WEEKLY_CLEANUP_TICKS == 0
        ):
            deleted = self._vector_mem.delete_old(days=30)
            log.info(
                f"[HeavyTick #{n}] VectorMemory cleanup: "
                f"{deleted} old records removed"
            )
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # Continuation in next file due to size...
    # ────────────────────────────────────────────────────────────────
    
    @staticmethod
    def _parse_goal_json(raw: str, n: int) -> dict:
        """Parse goal JSON from LLM response."""
        if not raw:
            return dict(_DEFAULT_GOAL)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start: end + 1])
            except json.JSONDecodeError:
                pass
        log.warning(
            f"[HeavyTick #{n}] Could not parse goal JSON. Using default."
        )
        return dict(_DEFAULT_GOAL)