"""
Digital Being — Memory Retrieval System
Stage 29: Optimized memory search and retrieval.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
import math

log = logging.getLogger("digital_being.memory_retrieval")

class MemoryRetrieval:
    """
    Optimized memory retrieval system.
    
    Features:
    - Fast similarity search
    - Context-aware retrieval
    - Temporal filtering
    - Multi-criteria ranking
    - Query caching
    """
    
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path / "memory_retrieval.json"
        
        self._state = {
            "query_cache": {},  # query_hash -> results
            "popular_queries": [],  # frequently accessed queries
            "retrieval_stats": {
                "total_queries": 0,
                "cache_hits": 0,
                "avg_retrieval_time": 0.0
            }
        }
        
        self._load_state()
        
        # In-memory cache for current session
        self._session_cache: dict[str, list] = {}
    
    def _load_state(self) -> None:
        """Load retrieval state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info("MemoryRetrieval: loaded state")
            except Exception as e:
                log.error(f"MemoryRetrieval: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save retrieval state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"MemoryRetrieval: failed to save state: {e}")
    
    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """
        Compute simple text similarity.
        
        Uses word overlap and common patterns.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score (0-1)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _compute_temporal_relevance(self, timestamp: float, current_time: float) -> float:
        """
        Compute temporal relevance score.
        
        Recent memories more relevant.
        
        Args:
            timestamp: Memory timestamp
            current_time: Current timestamp
        
        Returns:
            Relevance score (0-1)
        """
        age_hours = (current_time - timestamp) / 3600
        
        # Exponential decay
        # Half-life of 7 days (168 hours)
        half_life = 168
        decay_factor = 0.5 ** (age_hours / half_life)
        
        return decay_factor
    
    def _rank_memories(
        self,
        memories: list[dict],
        query: str,
        weights: dict[str, float] | None = None
    ) -> list[dict]:
        """
        Rank memories by relevance.
        
        Args:
            memories: List of memory dicts
            query: Search query
            weights: Scoring weights
        
        Returns:
            Ranked list of memories
        """
        if not weights:
            weights = {
                "similarity": 0.5,
                "importance": 0.3,
                "recency": 0.2
            }
        
        current_time = time.time()
        scored_memories = []
        
        for memory in memories:
            # Text similarity
            text = memory.get("description", "") + " " + memory.get("summary", "")
            similarity = self._compute_text_similarity(query, text)
            
            # Importance
            importance = memory.get("importance", 0.5)
            
            # Recency
            timestamp = memory.get("timestamp", current_time)
            recency = self._compute_temporal_relevance(timestamp, current_time)
            
            # Combined score
            score = (
                similarity * weights["similarity"] +
                importance * weights["importance"] +
                recency * weights["recency"]
            )
            
            scored_memories.append({
                "memory": memory,
                "score": score,
                "similarity": similarity,
                "importance": importance,
                "recency": recency
            })
        
        # Sort by score
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_memories
    
    def search(
        self,
        query: str,
        memories: list[dict],
        filters: dict | None = None,
        limit: int = 10,
        use_cache: bool = True
    ) -> list[dict]:
        """
        Search memories with ranking.
        
        Args:
            query: Search query
            memories: Pool of memories to search
            filters: Optional filters (event_type, min_importance, time_range)
            limit: Maximum results
            use_cache: Whether to use cache
        
        Returns:
            Ranked search results
        """
        start_time = time.time()
        
        # Generate cache key
        cache_key = f"{query}_{limit}_{json.dumps(filters, sort_keys=True) if filters else ''}"
        
        # Check cache
        if use_cache and cache_key in self._session_cache:
            self._state["retrieval_stats"]["cache_hits"] += 1
            log.debug(f"MemoryRetrieval: cache hit for '{query}'")
            return self._session_cache[cache_key]
        
        # Apply filters
        filtered = memories
        
        if filters:
            # Event type filter
            if "event_type" in filters:
                event_type = filters["event_type"]
                filtered = [m for m in filtered if m.get("event_type") == event_type]
            
            # Importance filter
            if "min_importance" in filters:
                min_imp = filters["min_importance"]
                filtered = [m for m in filtered if m.get("importance", 0) >= min_imp]
            
            # Time range filter
            if "time_range" in filters:
                start, end = filters["time_range"]
                filtered = [
                    m for m in filtered
                    if start <= m.get("timestamp", 0) <= end
                ]
        
        # Rank memories
        ranked = self._rank_memories(filtered, query)
        
        # Limit results
        results = ranked[:limit]
        
        # Update stats
        self._state["retrieval_stats"]["total_queries"] += 1
        elapsed = time.time() - start_time
        
        current_avg = self._state["retrieval_stats"]["avg_retrieval_time"]
        total_queries = self._state["retrieval_stats"]["total_queries"]
        new_avg = ((current_avg * (total_queries - 1)) + elapsed) / total_queries
        self._state["retrieval_stats"]["avg_retrieval_time"] = new_avg
        
        # Cache results
        if use_cache:
            self._session_cache[cache_key] = results
            
            # Limit cache size
            if len(self._session_cache) > 100:
                # Remove oldest entry
                oldest_key = next(iter(self._session_cache))
                del self._session_cache[oldest_key]
        
        self._save_state()
        
        log.debug(
            f"MemoryRetrieval: found {len(results)} results for '{query}' in {elapsed:.3f}s"
        )
        
        return results
    
    def find_similar(
        self,
        reference_memory: dict,
        memories: list[dict],
        limit: int = 5
    ) -> list[dict]:
        """
        Find memories similar to reference.
        
        Args:
            reference_memory: Reference memory
            memories: Pool to search
            limit: Maximum results
        
        Returns:
            Similar memories
        """
        ref_text = reference_memory.get("description", "")
        ref_type = reference_memory.get("event_type")
        ref_id = reference_memory.get("id")
        
        similar = []
        
        for memory in memories:
            # Skip self
            if memory.get("id") == ref_id:
                continue
            
            # Calculate similarity
            mem_text = memory.get("description", "")
            similarity = self._compute_text_similarity(ref_text, mem_text)
            
            # Bonus for same event type
            if memory.get("event_type") == ref_type:
                similarity += 0.2
            
            similar.append({
                "memory": memory,
                "similarity": min(1.0, similarity)
            })
        
        # Sort by similarity
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similar[:limit]
    
    def get_context(
        self,
        target_memory: dict,
        all_memories: list[dict],
        window_hours: int = 24
    ) -> list[dict]:
        """
        Get temporal context around a memory.
        
        Args:
            target_memory: Target memory
            all_memories: All memories
            window_hours: Time window in hours
        
        Returns:
            Memories in temporal context
        """
        target_time = target_memory.get("timestamp", time.time())
        window_seconds = window_hours * 3600
        
        context = [
            m for m in all_memories
            if abs(m.get("timestamp", 0) - target_time) <= window_seconds
            and m.get("id") != target_memory.get("id")
        ]
        
        # Sort by time
        context.sort(key=lambda m: m.get("timestamp", 0))
        
        return context
    
    def clear_cache(self) -> None:
        """Clear query cache."""
        self._session_cache.clear()
        self._state["query_cache"].clear()
        self._save_state()
        log.info("MemoryRetrieval: cache cleared")
    
    def get_stats(self) -> dict:
        """Get retrieval statistics."""
        cache_hit_rate = 0.0
        total = self._state["retrieval_stats"]["total_queries"]
        if total > 0:
            hits = self._state["retrieval_stats"]["cache_hits"]
            cache_hit_rate = hits / total
        
        return {
            "total_queries": total,
            "cache_hits": self._state["retrieval_stats"]["cache_hits"],
            "cache_hit_rate": cache_hit_rate,
            "avg_retrieval_time": self._state["retrieval_stats"]["avg_retrieval_time"],
            "session_cache_size": len(self._session_cache)
        }
