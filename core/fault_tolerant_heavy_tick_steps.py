"""Optional steps implementation for FaultTolerantHeavyTick."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from core.fault_tolerant_heavy_tick import FaultTolerantHeavyTick

log = logging.getLogger("digital_being.fault_tolerant_heavy_tick_steps")


class FaultTolerantHeavyTickSteps:
    """Mixin with all optional step implementations."""
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Curiosity
    # ────────────────────────────────────────────────────────────────
    async def _step_curiosity(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Generate and answer curiosity questions."""
        if self._curiosity is None or not self._curiosity_enabled:
            return {"status": "disabled"}
        
        loop = asyncio.get_event_loop()
        
        # Generate questions
        if self._curiosity.should_ask(n):
            log.info(f"[HeavyTick #{n}] CuriosityEngine: generating questions")
            try:
                recent_eps = self._mem.get_recent_episodes(10)
                new_questions = await loop.run_in_executor(
                    None,
                    lambda: self._curiosity.generate_questions(
                        recent_eps, self._world, self._ollama.ollama
                    )
                )
                for q in new_questions:
                    self._curiosity.add_question(q, context="auto", priority=0.6)
                if new_questions:
                    log.info(
                        f"[HeavyTick #{n}] CuriosityEngine: "
                        f"{len(new_questions)} question(s) generated"
                    )
            except Exception as e:
                log.error(
                    f"[HeavyTick #{n}] CuriosityEngine generate error: {e}"
                )
        
        # Answer question
        if self._curiosity.should_answer(n):
            q = self._curiosity.get_next_question()
            if q:
                log.info(
                    f"[HeavyTick #{n}] CuriosityEngine: seeking answer for "
                    f"'{q['question'][:60]}'"
                )
                try:
                    answer = await loop.run_in_executor(
                        None,
                        lambda: self._curiosity.seek_answer(
                            q, self._mem, self._vector_mem, self._ollama.ollama
                        )
                    )
                    self._curiosity.answer_question(q["id"], answer)
                except Exception as e:
                    log.error(
                        f"[HeavyTick #{n}] CuriosityEngine seek_answer error: {e}"
                    )
                    self._curiosity.answer_question(q["id"], "Ответ не найден")
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Self Modification
    # ────────────────────────────────────────────────────────────────
    async def _step_self_modification(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Suggest and apply self-modifications."""
        if self._self_mod is None:
            return {"status": "unavailable"}
        
        if not self._self_mod.should_suggest(n):
            return {"status": "skipped"}
        
        log.info(
            f"[HeavyTick #{n}] SelfModificationEngine: generating suggestions"
        )
        
        try:
            loop = asyncio.get_event_loop()
            reflection_log = (
                self._reflection.load_log() if self._reflection else []
            )
            emotion_state = (
                self._emotions.get_state() if self._emotions else {}
            )
            
            suggestions = await loop.run_in_executor(
                None,
                lambda: self._self_mod.suggest_improvements(
                    reflection_log, emotion_state
                )
            )
            
            if not suggestions:
                log.info(
                    f"[HeavyTick #{n}] SelfModificationEngine: "
                    "no suggestions generated"
                )
                return {"status": "no_suggestions"}
            
            log.info(
                f"[HeavyTick #{n}] SelfModificationEngine: "
                f"{len(suggestions)} suggestion(s) generated"
            )
            
            for s in suggestions[:2]:
                key = s.get("key", "")
                value = s.get("value")
                reason = s.get("reason", "")
                
                result = await loop.run_in_executor(
                    None, lambda: self._self_mod.propose(key, value, reason)
                )
                
                status = result.get("status", "unknown")
                if status == "approved":
                    log.info(
                        f"[HeavyTick #{n}] Config change APPROVED: "
                        f"{key} = {value} (was {result.get('old')})"
                    )
                    self._mem.add_episode(
                        "self_modification.approved",
                        f"Config change: {key} = {value}. "
                        f"Reason: {reason[:200]}",
                        outcome="success",
                    )
                else:
                    log.info(
                        f"[HeavyTick #{n}] Config change REJECTED: "
                        f"{key} = {value}. Reason: {result.get('reason', '?')}"
                    )
            
            return {"status": "completed", "count": len(suggestions)}
        except Exception as e:
            log.error(f"[HeavyTick #{n}] SelfModificationEngine error: {e}")
            return {"status": "error", "error": str(e)}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Belief System
    # ────────────────────────────────────────────────────────────────
    async def _step_belief_system(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Form and validate beliefs."""
        if self._beliefs is None:
            return {"status": "unavailable"}
        
        loop = asyncio.get_event_loop()
        recent_episodes = self._mem.get_recent_episodes(15)
        
        # Form new beliefs
        if self._beliefs.should_form(n):
            log.info(f"[HeavyTick #{n}] BeliefSystem: forming new beliefs")
            try:
                new_beliefs = await loop.run_in_executor(
                    None,
                    lambda: self._beliefs.form_beliefs(
                        recent_episodes, self._world, self._ollama.ollama
                    )
                )
                
                for b in new_beliefs:
                    added = self._beliefs.add_belief(
                        b["statement"],
                        b["category"],
                        b.get("initial_confidence", 0.5)
                    )
                    if added:
                        self._mem.add_episode(
                            "belief.formed",
                            f"[{b['category']}] {b['statement'][:200]}",
                            outcome="success",
                            data={"confidence": b.get("initial_confidence", 0.5)},
                        )
                
                if new_beliefs:
                    log.info(
                        f"[HeavyTick #{n}] BeliefSystem: "
                        f"{len(new_beliefs)} belief(s) added"
                    )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] BeliefSystem form error: {e}")
        
        # Validate existing beliefs
        if self._beliefs.should_validate(n):
            try:
                beliefs_to_check = self._beliefs.get_beliefs(
                    min_confidence=0.3, status="active"
                )
                if beliefs_to_check:
                    import random
                    b = random.choice(beliefs_to_check)
                    log.info(
                        f"[HeavyTick #{n}] BeliefSystem: validating "
                        f"'{b['statement'][:60]}'"
                    )
                    validated = await loop.run_in_executor(
                        None,
                        lambda: self._beliefs.validate_belief(
                            b["id"], recent_episodes, self._ollama.ollama
                        )
                    )
                    if validated:
                        log.info(
                            f"[HeavyTick #{n}] BeliefSystem: "
                            "validation completed"
                        )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] BeliefSystem validate error: {e}")
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Contradiction Resolver
    # ────────────────────────────────────────────────────────────────
    async def _step_contradiction_resolver(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Detect and resolve contradictions."""
        if self._contradictions is None or self._beliefs is None:
            return {"status": "unavailable"}
        
        loop = asyncio.get_event_loop()
        
        # Detect contradictions
        if self._contradictions.should_detect(n):
            log.info(
                f"[HeavyTick #{n}] ContradictionResolver: "
                "detecting contradictions"
            )
            try:
                beliefs = self._beliefs.get_beliefs(status="active")
                principles = self._self_model.get_principles()
                
                contradictions = await loop.run_in_executor(
                    None,
                    lambda: self._contradictions.detect_contradictions(
                        beliefs, principles, self._ollama.ollama
                    )
                )
                
                for c in contradictions[:2]:
                    added = self._contradictions.add_contradiction(
                        c["type"], c["item_a"], c["item_b"]
                    )
                    if added:
                        self._mem.add_episode(
                            "contradiction.detected",
                            f"[{c['type']}] {c['item_a']['text'][:60]} vs "
                            f"{c['item_b']['text'][:60]}",
                            outcome="pending",
                        )
                
                if contradictions:
                    log.info(
                        f"[HeavyTick #{n}] ContradictionResolver: "
                        f"{len(contradictions)} detected, "
                        f"{len(contradictions[:2])} added"
                    )
            except Exception as e:
                log.error(
                    f"[HeavyTick #{n}] ContradictionResolver detect error: {e}"
                )
        
        # Resolve contradictions
        if self._contradictions.should_resolve(n):
            pending = self._contradictions.get_pending()
            if pending:
                c = pending[0]
                log.info(
                    f"[HeavyTick #{n}] ContradictionResolver: resolving "
                    f"'{c['item_a']['text'][:40]} vs {c['item_b']['text'][:40]}'"
                )
                try:
                    resolved = await loop.run_in_executor(
                        None,
                        lambda: self._contradictions.resolve_contradiction(
                            c["id"], self._ollama.ollama
                        )
                    )
                    if resolved:
                        await self._apply_verdict(c["id"], n)
                        log.info(
                            f"[HeavyTick #{n}] ContradictionResolver: "
                            "resolution completed and applied"
                        )
                except Exception as e:
                    log.error(
                        f"[HeavyTick #{n}] ContradictionResolver "
                        f"resolve error: {e}"
                    )
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Time Perception
    # ────────────────────────────────────────────────────────────────
    async def _step_time_perception(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Detect temporal patterns."""
        if self._time_perc is None:
            return {"status": "unavailable"}
        
        loop = asyncio.get_event_loop()
        
        if self._time_perc.should_detect(n):
            log.info(
                f"[HeavyTick #{n}] TimePerception: detecting patterns"
            )
            try:
                episodes = self._mem.get_recent_episodes(50)
                patterns = await loop.run_in_executor(
                    None,
                    lambda: self._time_perc.detect_patterns(
                        episodes, self._ollama.ollama
                    )
                )
                
                for p in patterns[:3]:
                    self._time_perc.add_pattern(
                        p["pattern_type"],
                        p["condition"],
                        p["observation"],
                        p.get("confidence", 0.5)
                    )
                
                if patterns:
                    log.info(
                        f"[HeavyTick #{n}] TimePerception: "
                        f"{len(patterns)} pattern(s) detected"
                    )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] TimePerception error: {e}")
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Social Interaction
    # ────────────────────────────────────────────────────────────────
    async def _step_social_interaction(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Handle social messages and conversations."""
        if self._social is None:
            return {"status": "unavailable"}
        
        loop = asyncio.get_event_loop()
        
        # Check inbox
        new_messages = await loop.run_in_executor(
            None, self._social.check_inbox
        )
        
        if new_messages:
            for msg in new_messages:
                msg["tick"] = n
                self._mem.add_episode(
                    "social.incoming",
                    f"Пользователь написал: {msg['content'][:200]}",
                    outcome="success",
                    data={"message_id": msg["id"]},
                )
                
                context = self._build_social_context()
                response = await loop.run_in_executor(
                    None,
                    lambda m=msg: self._social.generate_response(
                        m, context, self._ollama.ollama
                    )
                )
                
                if response:
                    self._social.add_outgoing(response, n, response_to=msg["id"])
                    await loop.run_in_executor(
                        None, lambda r=response: self._social.write_to_outbox(r)
                    )
                    self._social.mark_responded(msg["id"])
                    self._mem.add_episode(
                        "social.outgoing",
                        f"Ответил пользователю: {response[:200]}",
                        outcome="success",
                    )
                    log.info(
                        f"[HeavyTick #{n}] SocialLayer: "
                        "responded to user message"
                    )
                else:
                    self._mem.add_episode(
                        "social.llm_unavailable",
                        "Не удалось сгенерировать ответ — LLM недоступен",
                        outcome="error",
                    )
                    log.warning(
                        f"[HeavyTick #{n}] SocialLayer: "
                        "failed to generate response (LLM unavailable)"
                    )
        
        # Check if should initiate conversation
        should_write, reason = await loop.run_in_executor(
            None,
            lambda: self._social.should_initiate(
                n, self._mem, self._emotions, self._curiosity
            )
        )
        
        if should_write:
            context = self._build_social_context()
            message = await loop.run_in_executor(
                None,
                lambda: self._social.generate_initiative(
                    reason, context, self._ollama.ollama
                )
            )
            
            if message:
                self._social.add_outgoing(message, n)
                await loop.run_in_executor(
                    None, lambda m=message: self._social.write_to_outbox(m)
                )
                self._mem.add_episode(
                    "social.initiative",
                    f"Написал пользователю (reason={reason}): "
                    f"{message[:200]}",
                    outcome="success",
                )
                log.info(
                    f"[HeavyTick #{n}] SocialLayer: "
                    f"initiated conversation (reason={reason})"
                )
            else:
                log.warning(
                    f"[HeavyTick #{n}] SocialLayer: "
                    "failed to generate initiative message"
                )
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # STEP: Meta-Cognition
    # ────────────────────────────────────────────────────────────────
    async def _step_meta_cognition(
        self: "FaultTolerantHeavyTick", n: int
    ) -> Dict[str, Any]:
        """Analyze decision quality and cognitive patterns."""
        if self._meta_cog is None:
            return {"status": "unavailable"}
        
        loop = asyncio.get_event_loop()
        
        if self._meta_cog.should_analyze(n):
            log.info(
                f"[HeavyTick #{n}] MetaCognition: "
                "analyzing decision quality"
            )
            try:
                episodes = self._mem.get_recent_episodes(20)
                quality = await loop.run_in_executor(
                    None,
                    lambda: self._meta_cog.analyze_decision_quality(
                        episodes, self._ollama.ollama
                    )
                )
                
                if quality:
                    log.info(
                        f"[HeavyTick #{n}] MetaCognition: "
                        f"reasoning={quality.get('reasoning_quality', 0):.2f}, "
                        f"confusion={quality.get('confusion_level', 0):.2f}"
                    )
                    
                    beliefs = (
                        self._beliefs.get_beliefs() if self._beliefs else []
                    )
                    insights = await loop.run_in_executor(
                        None,
                        lambda: self._meta_cog.detect_cognitive_patterns(
                            episodes, beliefs, self._ollama.ollama
                        )
                    )
                    
                    for ins in insights[:2]:
                        self._meta_cog.add_insight(
                            ins["insight_type"],
                            ins["description"],
                            [],
                            ins.get("confidence", 0.5),
                            ins.get("impact", "medium"),
                        )
                    
                    if insights:
                        log.info(
                            f"[HeavyTick #{n}] MetaCognition: "
                            f"{len(insights)} insight(s) discovered"
                        )
            except Exception as e:
                log.error(f"[HeavyTick #{n}] MetaCognition error: {e}")
        
        return {"status": "completed"}
    
    # ────────────────────────────────────────────────────────────────
    # Helper: Build Social Context
    # ────────────────────────────────────────────────────────────────
    def _build_social_context(self: "FaultTolerantHeavyTick") -> str:
        """Build context for social interaction."""
        parts = [
            self._self_model.to_prompt_context(),
            self._values.to_prompt_context(),
        ]
        if self._emotions:
            parts.append(self._emotions.to_prompt_context())
        if self._beliefs:
            parts.append(self._beliefs.to_prompt_context(3))
        if self._time_perc:
            parts.append(self._time_perc.to_prompt_context(2))
        if self._meta_cog:
            parts.append(self._meta_cog.to_prompt_context(2))
        return "\n".join(parts)
    
    # ────────────────────────────────────────────────────────────────
    # Helper: Apply Contradiction Verdict
    # ────────────────────────────────────────────────────────────────
    async def _apply_verdict(
        self: "FaultTolerantHeavyTick", contradiction_id: str, tick: int
    ) -> None:
        """Apply resolution verdict to beliefs/principles."""
        resolved = self._contradictions.get_resolved(limit=50)
        contradiction = None
        for c in resolved:
            if c["id"] == contradiction_id:
                contradiction = c
                break
        
        if not contradiction or not contradiction.get("resolution"):
            log.warning(
                f"_apply_verdict: contradiction {contradiction_id} "
                "not found or unresolved"
            )
            return
        
        resolution = contradiction["resolution"]
        verdict = resolution["verdict"]
        item_a, item_b = contradiction["item_a"], contradiction["item_b"]
        
        log.info(
            f"Applying verdict '{verdict}' to contradiction: "
            f"{item_a['text'][:30]} vs {item_b['text'][:30]}"
        )
        
        loop = asyncio.get_event_loop()
        
        if verdict == "choose_a":
            await self._modify_item_confidence(item_b, -0.3, loop)
            self._mem.add_episode(
                "contradiction.resolved",
                f"Verdict: choose_a. Weakened: {item_b['text'][:100]}",
                outcome="success",
                data={"verdict": verdict, "weakened_id": item_b["id"]}
            )
        elif verdict == "choose_b":
            await self._modify_item_confidence(item_a, -0.3, loop)
            self._mem.add_episode(
                "contradiction.resolved",
                f"Verdict: choose_b. Weakened: {item_a['text'][:100]}",
                outcome="success",
                data={"verdict": verdict, "weakened_id": item_a["id"]}
            )
        elif verdict == "synthesis":
            synthesis_text = resolution.get("synthesis_text", "")
            if synthesis_text:
                await self._create_synthesis(item_a, item_b, synthesis_text, loop)
                await self._modify_item_confidence(item_a, -0.2, loop)
                await self._modify_item_confidence(item_b, -0.2, loop)
                self._mem.add_episode(
                    "contradiction.resolved",
                    f"Verdict: synthesis. Created: {synthesis_text[:100]}",
                    outcome="success",
                    data={"verdict": verdict, "synthesis": synthesis_text}
                )
        elif verdict == "both_valid":
            self._mem.add_episode(
                "contradiction.resolved",
                "Verdict: both_valid. No changes applied.",
                outcome="success",
                data={"verdict": verdict}
            )
    
    async def _modify_item_confidence(
        self: "FaultTolerantHeavyTick",
        item: dict,
        delta: float,
        loop
    ) -> None:
        """Modify confidence of belief or principle."""
        item_type = item.get("type", "belief")
        item_id = item["id"]
        
        if item_type == "belief" and self._beliefs:
            updated = await loop.run_in_executor(
                None, lambda: self._beliefs.update_confidence(item_id, delta)
            )
            if updated:
                log.info(
                    f"Updated belief confidence via update_confidence(): "
                    f"{item['text'][:40]}"
                )
        elif item_type == "principle":
            log.debug(
                f"Principle confidence modification not implemented: {item_id}"
            )
    
    async def _create_synthesis(
        self: "FaultTolerantHeavyTick",
        item_a: dict,
        item_b: dict,
        synthesis_text: str,
        loop
    ) -> None:
        """Create synthesis belief or principle."""
        if item_a.get("type") == "belief" or item_b.get("type") == "belief":
            if self._beliefs:
                if (
                    item_a.get("type") == "belief"
                    and item_b.get("type") == "belief"
                ):
                    beliefs = self._beliefs.get_beliefs(status="active")
                    cat_a = next(
                        (b["category"] for b in beliefs if b["id"] == item_a["id"]),
                        "cause_effect"
                    )
                    cat_b = next(
                        (b["category"] for b in beliefs if b["id"] == item_b["id"]),
                        "cause_effect"
                    )
                    category = cat_a if cat_a == cat_b else "cause_effect"
                else:
                    category = "cause_effect"
                
                added = self._beliefs.add_belief(synthesis_text, category, 0.6)
                if added:
                    log.info(f"Created synthesis belief: {synthesis_text[:60]}")
        else:
            added = await self._self_model.add_principle(synthesis_text)
            if added:
                log.info(f"Created synthesis principle: {synthesis_text[:60]}")
    
    # ────────────────────────────────────────────────────────────────
    # Helper: Weekly Strategy Update
    # ────────────────────────────────────────────────────────────────
    async def _maybe_update_weekly(
        self: "FaultTolerantHeavyTick", n: int
    ) -> None:
        """Update weekly strategic direction."""
        if not self._strategy.should_update_weekly():
            return
        
        log.info(f"[HeavyTick #{n}] Weekly direction update triggered")
        
        context = self._strategy.to_prompt_context()
        prompt = (
            f"{context}\n\nПрошли сутки. Сформулируй новое недельное направление "
            "(1 предложение). Отвечай ТОЛЬКО текстом направления."
        )
        system = "Ты — Digital Being. Формулируй кратко и по делу."
        
        try:
            direction = await self._ollama.chat(
                prompt, system, timeout=30, fallback=""
            )
            direction = direction.strip() if direction else ""
            
            if direction:
                self._strategy.update_weekly(direction)
                self._mem.add_episode(
                    "strategy.weekly_update",
                    f"Недельное направление обновлено: '{direction[:200]}'",
                    outcome="success",
                )
                log.info(f"[HeavyTick #{n}] Weekly direction updated")
            else:
                log.warning(
                    f"[HeavyTick #{n}] Weekly update: LLM returned empty"
                )
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Weekly update failed: {e}")
    
    # ────────────────────────────────────────────────────────────────
    # Helper: Embed and Store
    # ────────────────────────────────────────────────────────────────
    async def _embed_and_store(
        self: "FaultTolerantHeavyTick",
        ep_id: int | None,
        event_type: str,
        text: str
    ) -> None:
        """Embed text and store in vector memory."""
        if self._vector_mem is None:
            return
        
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self._ollama.ollama.embed(text[:2000])
            )
            if embedding:
                self._vector_mem.add(
                    episode_id=ep_id or 0,
                    event_type=event_type,
                    text=text[:500],
                    embedding=embedding
                )
        except Exception as e:
            log.debug(f"_embed_and_store(): {e}")
    
    # ────────────────────────────────────────────────────────────────
    # Helper: Attention System
    # ────────────────────────────────────────────────────────────────
    def _attention_filter_episodes(
        self: "FaultTolerantHeavyTick", episodes: list[dict]
    ) -> list[dict]:
        """Filter episodes by attention score."""
        if self._attention is None or not episodes:
            return episodes
        try:
            return self._attention.filter_episodes(
                episodes, top_k=self._attn_top_k, min_score=self._attn_min_score
            )
        except Exception as e:
            log.debug(f"_attention_filter_episodes(): {e}")
            return episodes
    
    def _attention_build_context(
        self: "FaultTolerantHeavyTick", episodes: list[dict]
    ) -> str:
        """Build context string from episodes."""
        if self._attention is None:
            return "; ".join(
                f"{e.get('event_type', '?')}: {e.get('description', '')[:60]}"
                for e in episodes
            ) if episodes else "нет"
        try:
            return self._attention.build_context(
                episodes, max_chars=self._attn_max_chars
            )
        except Exception as e:
            log.debug(f"_attention_build_context(): {e}")
            return "(контекст недоступен)"
    
    def _attention_focus_summary(
        self: "FaultTolerantHeavyTick"
    ) -> str:
        """Get attention focus summary."""
        if self._attention is None:
            return ""
        try:
            return self._attention.get_focus_summary()
        except Exception as e:
            log.debug(f"_attention_focus_summary(): {e}")
            return ""
    
    # ────────────────────────────────────────────────────────────────
    # Helper: Update Emotions
    # ────────────────────────────────────────────────────────────────
    def _update_emotions(
        self: "FaultTolerantHeavyTick", event_type: str, outcome: str
    ) -> None:
        """Update emotion state based on event."""
        if self._emotions is None:
            return
        try:
            self._emotions.update(
                event_type=event_type,
                outcome=outcome,
                value_scores=(
                    self._values.get_scores()
                    if hasattr(self._values, "get_scores")
                    else {}
                ),
            )
        except Exception as e:
            log.error(f"EmotionEngine.update() failed: {e}")