"""
ИСПРАВЛЕННЫЕ МЕТОДЫ для core/heavy_tick.py

ЗАМЕНИ в файле heavy_tick.py:

1. Найди строку:
   # ────────────────────────────────────────────────────────────────
   # Stage 23: Social Interaction
   # ────────────────────────────────────────────────────────────────
   
2. УДАЛИ всё от этой строки до строки:
   # ────────────────────────────────────────────────────────────────
   # Stage 22: Time Perception
   # ────────────────────────────────────────────────────────────────

3. ВСТАВЬ на это место код ниже (ВСЁ между линиями КОПИРОВАТЬ ОТСЮДА и КОПИРОВАТЬ ДО СЮДА)
"""

# ═════════════════════════════════════════════════════════════════
# КОПИРОВАТЬ ОТСЮДА
# ═════════════════════════════════════════════════════════════════

    # ────────────────────────────────────────────────────────────────
    # Stage 22: Time Perception
    # ────────────────────────────────────────────────────────────────
    async def _step_time_perception(self, n: int) -> None:
        """Stage 22: Detect temporal patterns periodically."""
        if self._time_perc is None:
            return
        
        loop = asyncio.get_event_loop()
        
        # Detect patterns periodically
        if self._time_perc.should_detect(n):
            log.info(f"[HeavyTick #{n}] TimePerception: detecting patterns.")
            try:
                episodes = self._mem.get_recent_episodes(50)
                patterns = await loop.run_in_executor(
                    None, lambda: self._time_perc.detect_patterns(episodes, self._ollama)
                )
                
                for p in patterns[:3]:  # max 3 per cycle
                    self._time_perc.add_pattern(
                        p["pattern_type"], p["condition"], p["observation"], p.get("confidence", 0.5)
                    )
                
                if patterns:
                    log.info(f"[HeavyTick #{n}] TimePerception: {len(patterns)} pattern(s) detected.")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] TimePerception error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Stage 23: Social Interaction
    # ────────────────────────────────────────────────────────────────
    async def _step_social_interaction(self, n: int) -> None:
        """Stage 23: Check inbox and handle user messages, initiate conversation if needed."""
        if self._social is None:
            return
        
        loop = asyncio.get_event_loop()
        
        # Check for incoming messages
        new_messages = await loop.run_in_executor(None, self._social.check_inbox)
        
        if new_messages:
            for msg in new_messages:
                # Update tick in message
                msg["tick"] = n
                
                # Add to memory
                self._mem.add_episode(
                    "social.incoming",
                    f"Пользователь написал: {msg['content'][:200]}",
                    outcome="success",
                    data={"message_id": msg["id"]}
                )
                
                # Generate response
                context = self._build_social_context()
                response = await loop.run_in_executor(
                    None,
                    lambda m=msg: self._social.generate_response(m, context, self._ollama)
                )
                
                if response:
                    # Send response
                    outgoing = self._social.add_outgoing(response, n, response_to=msg["id"])
                    await loop.run_in_executor(None, lambda r=response: self._social.write_to_outbox(r))
                    self._social.mark_responded(msg["id"])
                    
                    self._mem.add_episode(
                        "social.outgoing",
                        f"Ответил пользователю: {response[:200]}",
                        outcome="success"
                    )
                    
                    log.info(f"[HeavyTick #{n}] SocialLayer: responded to user message.")
                else:
                    # LLM unavailable
                    self._mem.add_episode(
                        "social.llm_unavailable",
                        "Не удалось сгенерировать ответ — LLM недоступен",
                        outcome="error"
                    )
                    log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate response (LLM unavailable).")
        
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
                lambda: self._social.generate_initiative(reason, context, self._ollama)
            )
            
            if message:
                outgoing = self._social.add_outgoing(message, n)
                await loop.run_in_executor(None, lambda m=message: self._social.write_to_outbox(m))
                
                self._mem.add_episode(
                    "social.initiative",
                    f"Написал пользователю (reason={reason}): {message[:200]}",
                    outcome="success"
                )
                
                log.info(f"[HeavyTick #{n}] SocialLayer: initiated conversation (reason={reason}).")
            else:
                log.warning(f"[HeavyTick #{n}] SocialLayer: failed to generate initiative message.")

    # ────────────────────────────────────────────────────────────────
    # Stage 24: Meta-Cognition
    # ────────────────────────────────────────────────────────────────
    async def _step_meta_cognition(self, n: int) -> None:
        """Stage 24: Analyze decision quality and discover cognitive patterns."""
        if self._meta_cog is None:
            return
        
        loop = asyncio.get_event_loop()
        
        # Periodic analysis
        if self._meta_cog.should_analyze(n):
            log.info(f"[HeavyTick #{n}] MetaCognition: analyzing decision quality.")
            try:
                episodes = self._mem.get_recent_episodes(20)
                quality = await loop.run_in_executor(
                    None, lambda: self._meta_cog.analyze_decision_quality(episodes, self._ollama)
                )
                
                if quality:
                    log.info(
                        f"[HeavyTick #{n}] MetaCognition: "
                        f"reasoning={quality.get('reasoning_quality', 0):.2f}, "
                        f"confusion={quality.get('confusion_level', 0):.2f}"
                    )
                    
                    # Detect cognitive patterns
                    beliefs = self._beliefs.get_beliefs() if self._beliefs else []
                    insights = await loop.run_in_executor(
                        None,
                        lambda: self._meta_cog.detect_cognitive_patterns(
                            episodes, beliefs, self._ollama
                        )
                    )
                    
                    for ins in insights[:2]:
                        self._meta_cog.add_insight(
                            ins["insight_type"],
                            ins["description"],
                            [],  # evidence episode IDs can be added later
                            ins.get("confidence", 0.5),
                            ins.get("impact", "medium")
                        )
                    
                    if insights:
                        log.info(f"[HeavyTick #{n}] MetaCognition: {len(insights)} insight(s) discovered.")
            
            except Exception as e:
                log.error(f"[HeavyTick #{n}] MetaCognition error: {e}")

    # ────────────────────────────────────────────────────────────────
    # Helper: Build Social Context
    # ────────────────────────────────────────────────────────────────
    def _build_social_context(self) -> str:
        """Построить контекст для social interaction."""
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

# ═════════════════════════════════════════════════════════════════
# КОПИРОВАТЬ ДО СЮДА
# ═════════════════════════════════════════════════════════════════

"""
ДОПОЛНИТЕЛЬНО: В методе _step_monologue найди где строится промпт и ДОБАВЬ:

        # Add temporal context
        if self._time_perc:
            time_ctx = self._time_perc.to_prompt_context(3)
            prompt += f"\n{time_ctx}\n"
        
        # Add meta-cognitive awareness
        if self._meta_cog:
            meta_ctx = self._meta_cog.to_prompt_context(2)
            prompt += f"\n{meta_ctx}\n"

Это должно быть ПЕРЕД вызовом LLM (перед self._ollama.generate_stream или similar).
"""
