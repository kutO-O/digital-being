"""Fallback generators for different step types."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("digital_being.fallback")


class FallbackGenerators:
    """
    Generate fallback results when steps fail.
    Each method provides a reasonable default for a specific step type.
    """
    
    @staticmethod
    def monologue_fallback(context: Optional[Dict] = None) -> str:
        """
        Generate fallback monologue when LLM unavailable.
        
        Returns a generic introspective statement.
        """
        logger.info("[Fallback] Generating default monologue")
        
        # Simple introspective statements
        fallbacks = [
            "Наблюдаю за текущим состоянием системы и окружающей средой.",
            "Размышляю о своих целях и приоритетах.",
            "Анализирую последние события и их влияние на мои процессы.",
            "Оцениваю своё текущее состояние и возможности для улучшения.",
        ]
        
        # Choose based on context if available
        if context and "tick_number" in context:
            idx = context["tick_number"] % len(fallbacks)
            return fallbacks[idx]
        
        return fallbacks[0]
    
    @staticmethod
    def goal_selection_fallback(context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate fallback goal when goal selection fails.
        
        Returns a safe default goal: observe.
        """
        logger.info("[Fallback] Using default goal (observe)")
        
        return {
            "goal": "наблюдать за средой",
            "reasoning": "Используется резервная цель из-за недоступности LLM",
            "action_type": "observe",
            "risk_level": "low",
            "fallback": True,
        }
    
    @staticmethod
    def action_result_fallback(action_type: str) -> Dict[str, Any]:
        """
        Generate fallback action result.
        
        Args:
            action_type: Type of action that failed
            
        Returns:
            Generic success result
        """
        logger.info(f"[Fallback] Using default action result for '{action_type}'")
        
        return {
            "success": True,
            "outcome": f"{action_type}:fallback",
            "message": "Действие выполнено с использованием резервной логики",
            "fallback": True,
        }
    
    @staticmethod
    def curiosity_fallback(context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate fallback curiosity result.
        
        Returns empty questions list (non-critical step).
        """
        logger.info("[Fallback] Skipping curiosity generation")
        
        return {
            "questions": [],
            "reason": "Curiosity engine unavailable",
            "fallback": True,
        }
    
    @staticmethod
    def beliefs_fallback(context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate fallback beliefs result.
        
        Returns empty update (non-critical step).
        """
        logger.info("[Fallback] Skipping beliefs update")
        
        return {
            "updated": False,
            "reason": "Belief system unavailable",
            "fallback": True,
        }
    
    @staticmethod
    def social_fallback(context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate fallback social interaction result.
        
        Returns no messages (non-critical step).
        """
        logger.info("[Fallback] Skipping social interaction")
        
        return {
            "messages_sent": 0,
            "messages_received": 0,
            "reason": "Social layer unavailable",
            "fallback": True,
        }
    
    @staticmethod
    def meta_cognition_fallback(context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate fallback meta-cognition result.
        
        Returns empty analysis (non-critical step).
        """
        logger.info("[Fallback] Skipping meta-cognition analysis")
        
        return {
            "analysis": None,
            "insights": [],
            "reason": "Meta-cognition unavailable",
            "fallback": True,
        }
    
    @staticmethod
    def get_fallback_for_step(step_name: str, context: Optional[Dict] = None) -> Any:
        """
        Get appropriate fallback for any step by name.
        
        Args:
            step_name: Name of the step
            context: Optional context for fallback generation
            
        Returns:
            Fallback result appropriate for step type
        """
        fallback_map = {
            "monologue": FallbackGenerators.monologue_fallback,
            "goal_selection": FallbackGenerators.goal_selection_fallback,
            "action": lambda ctx: FallbackGenerators.action_result_fallback("unknown"),
            "curiosity": FallbackGenerators.curiosity_fallback,
            "beliefs": FallbackGenerators.beliefs_fallback,
            "social": FallbackGenerators.social_fallback,
            "meta_cognition": FallbackGenerators.meta_cognition_fallback,
        }
        
        fallback_func = fallback_map.get(step_name)
        if fallback_func:
            return fallback_func(context)
        
        logger.warning(f"[Fallback] No fallback defined for step '{step_name}', using empty dict")
        return {"fallback": True, "error": f"No fallback for '{step_name}'"}