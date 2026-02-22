"""
Add this to strategy_engine.py.

Add _detect_loop() method to StrategyEngine class.
Call it at start of select_goal() method.
"""

def _detect_loop(self) -> bool:
    """
    Detect if system is stuck in repetitive behavior.
    Returns True if last 10 ticks show >80% same action.
    """
    if self._episodic is None:
        return False
    
    # Check for observe loops
    recent_observe = self._episodic.get_episodes_by_type(
        "heavy_tick.observe", limit=10
    )
    if len(recent_observe) >= 8:
        log.warning(
            f"[StrategyEngine] 🔁 LOOP DETECTED: "
            f"'observe' repeated {len(recent_observe)}/10 times"
        )
        return True
    
    # Check for write loops
    recent_write = self._episodic.get_episodes_by_type(
        "heavy_tick.write", limit=10
    )
    if len(recent_write) >= 8:
        log.warning(
            f"[StrategyEngine] 🔁 LOOP DETECTED: "
            f"'write' repeated {len(recent_write)}/10 times"
        )
        return True
    
    return False


# Add at START of select_goal() method:
async def select_goal(
    self,
    value_engine: "ValueEngine",
    world_model: "WorldModel",
    episodic: "EpisodicMemory",
    ollama: "OllamaClient",
    semantic_ctx: str = "",
    emotion_ctx: str = "",
    resume_ctx: str = "",
) -> dict:
    # 🔴 ADD THIS CHECK FIRST
    if self._detect_loop():
        log.info("[StrategyEngine] Breaking loop with forced 'reflect' action")
        return {
            "goal": "выйти из повторяющегося паттерна",
            "reasoning": "Обнаружен цикл, принудительная рефлексия",
            "action_type": "reflect",
            "risk_level": "low",
        }
    
    # ... rest of method
