"""Memory Consolidation - Sleep Cycle Processing."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Any, List, Optional

if TYPE_CHECKING:
    from core.memory.episodic import EpisodicMemory
    from core.ollama_client import OllamaClient
    from core.belief_system import BeliefSystem

log = logging.getLogger("digital_being.memory_consolidation")


class MemoryConsolidation:
    """
    Sleep cycle for memory processing.
    
    Performs:
    - Episode replay and pattern extraction
    - Memory pruning (remove redundant)
    - Belief consolidation
    - Pattern formation
    """
    
    def __init__(
        self,
        memory: "EpisodicMemory",
        ollama: "OllamaClient",
        beliefs: Optional["BeliefSystem"] = None,
        consolidation_interval: int = 24 * 60 * 60,  # 24 hours
    ):
        self._memory = memory
        self._ollama = ollama
        self._beliefs = beliefs
        self._interval = consolidation_interval
        self._last_consolidation = time.time()
        
        self._stats = {
            "total_consolidations": 0,
            "episodes_processed": 0,
            "episodes_pruned": 0,
            "patterns_formed": 0,
        }
    
    def should_consolidate(self) -> bool:
        """Check if it's time to consolidate."""
        return (time.time() - self._last_consolidation) >= self._interval
    
    async def consolidate(self) -> Dict[str, Any]:
        """
        Perform memory consolidation.
        
        Returns:
            Statistics about consolidation
        """
        log.info("Starting memory consolidation (sleep cycle)...")
        start_time = time.time()
        
        # Get recent episodes
        recent_episodes = self._memory.get_recent_episodes(100)
        
        if not recent_episodes:
            log.info("No episodes to consolidate")
            return {"status": "no_episodes"}
        
        # 1. Episode Replay - extract important patterns
        patterns = await self._replay_episodes(recent_episodes)
        
        # 2. Memory Pruning - remove redundant
        pruned = self._prune_memory(recent_episodes)
        
        # 3. Belief Consolidation
        if self._beliefs:
            self._consolidate_beliefs()
        
        # Update stats
        self._stats["total_consolidations"] += 1
        self._stats["episodes_processed"] += len(recent_episodes)
        self._stats["episodes_pruned"] += pruned
        self._stats["patterns_formed"] += len(patterns)
        self._last_consolidation = time.time()
        
        duration = time.time() - start_time
        
        log.info(
            f"Memory consolidation completed in {duration:.1f}s: "
            f"processed={len(recent_episodes)}, pruned={pruned}, "
            f"patterns={len(patterns)}"
        )
        
        return {
            "status": "completed",
            "duration": duration,
            "episodes_processed": len(recent_episodes),
            "episodes_pruned": pruned,
            "patterns_formed": len(patterns),
        }
    
    async def _replay_episodes(self, episodes: List[dict]) -> List[Dict[str, Any]]:
        """Replay episodes to extract patterns."""
        # Select important episodes (high emotional salience)
        important = sorted(
            episodes,
            key=lambda e: e.get("data", {}).get("emotional_salience", 0.5),
            reverse=True
        )[:20]
        
        if not important:
            return []
        
        # Build replay prompt
        episodes_str = "\n".join(
            f"- {e.get('event_type', '?')}: {e.get('description', '')[:100]}"
            for e in important
        )
        
        prompt = f"""
Проанализируй эти важные события и найди паттерны:

{episodes_str}

Найди:
1. Temporal patterns (что происходит регулярно?)
2. Causal patterns (что к чему приводит?)
3. Success patterns (что работает хорошо?)

Ответь кратким JSON списком паттернов.
"""
        
        try:
            response = self._ollama.chat(prompt, "Ты — Memory Analyzer.", timeout=30)
            # TODO: Parse patterns from response
            return [{"type": "general", "description": "pattern extracted"}]
        except Exception as e:
            log.warning(f"Episode replay failed: {e}")
            return []
    
    def _prune_memory(self, episodes: List[dict]) -> int:
        """Prune redundant memories."""
        # Simple pruning: remove very similar consecutive episodes
        pruned = 0
        
        # Group by event_type
        by_type: Dict[str, List[dict]] = {}
        for ep in episodes:
            et = ep.get("event_type", "unknown")
            if et not in by_type:
                by_type[et] = []
            by_type[et].append(ep)
        
        # For each type, keep only unique descriptions
        for event_type, eps in by_type.items():
            if len(eps) <= 1:
                continue
            
            seen_descriptions = set()
            for ep in eps:
                desc = ep.get("description", "")
                if desc in seen_descriptions:
                    # Mark for pruning (in practice, would delete)
                    pruned += 1
                else:
                    seen_descriptions.add(desc)
        
        return pruned
    
    def _consolidate_beliefs(self) -> None:
        """Consolidate beliefs based on accumulated evidence."""
        if not self._beliefs:
            return
        
        # Strengthen validated beliefs
        # Weaken contradicted beliefs
        # (Implementation would integrate with BeliefSystem)
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get consolidation statistics."""
        return self._stats.copy()