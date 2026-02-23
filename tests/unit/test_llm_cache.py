"""
Unit Tests for LLM Cache
"""

import time
import pytest
from core.llm_cache import LLMCache


class TestLLMCache:
    """Test LLM response cache."""
    
    def test_cache_initialization(self):
        """Test cache creates successfully."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        assert cache.max_size == 10
        assert cache.ttl_seconds == 60.0
        assert cache.get_stats()["current_size"] == 0
    
    def test_cache_set_and_get(self):
        """Test basic set/get operations."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        cache.set("prompt1", "system1", "response1")
        result = cache.get("prompt1", "system1")
        
        assert result == "response1"
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        result = cache.get("nonexistent", "")
        
        assert result is None
    
    def test_cache_hit_statistics(self):
        """Test cache hit tracking."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        cache.set("prompt", "", "response")
        cache.get("prompt", "")  # Hit
        cache.get("other", "")   # Miss
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache full."""
        cache = LLMCache(max_size=3, ttl_seconds=60.0)
        
        # Fill cache
        cache.set("prompt1", "", "response1")
        cache.set("prompt2", "", "response2")
        cache.set("prompt3", "", "response3")
        
        # Add one more (should evict prompt1)
        cache.set("prompt4", "", "response4")
        
        assert cache.get("prompt1", "") is None  # Evicted
        assert cache.get("prompt4", "") == "response4"  # Present
        assert cache.get_stats()["evictions"] == 1
    
    def test_cache_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = LLMCache(max_size=10, ttl_seconds=0.1)  # 100ms TTL
        
        cache.set("prompt", "", "response")
        assert cache.get("prompt", "") == "response"  # Fresh
        
        time.sleep(0.2)  # Wait for expiration
        
        assert cache.get("prompt", "") is None  # Expired
    
    def test_cache_different_systems(self):
        """Test same prompt with different systems are separate."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        cache.set("prompt", "system1", "response1")
        cache.set("prompt", "system2", "response2")
        
        assert cache.get("prompt", "system1") == "response1"
        assert cache.get("prompt", "system2") == "response2"
    
    def test_cache_clear(self):
        """Test cache clearing."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        cache.set("prompt1", "", "response1")
        cache.set("prompt2", "", "response2")
        
        cache.clear()
        
        assert cache.get("prompt1", "") is None
        assert cache.get("prompt2", "") is None
        assert cache.get_stats()["current_size"] == 0
    
    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = LLMCache(max_size=10, ttl_seconds=0.1)
        
        cache.set("prompt1", "", "response1")
        cache.set("prompt2", "", "response2")
        
        time.sleep(0.2)  # Expire all
        
        cache.cleanup_expired()
        
        assert cache.get_stats()["current_size"] == 0
    
    def test_cache_top_entries(self):
        """Test top entries tracking."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        cache.set("prompt1", "", "response1")
        cache.get("prompt1", "")  # 1 hit
        cache.get("prompt1", "")  # 2 hits
        
        cache.set("prompt2", "", "response2")
        cache.get("prompt2", "")  # 1 hit
        
        top = cache.get_top_entries(n=2)
        
        # prompt1 should be first (2 hits)
        assert top[0][1] == 2  # hit count
    
    def test_cache_zero_size(self):
        """Test cache with size 0 (disabled)."""
        cache = LLMCache(max_size=0, ttl_seconds=60.0)
        
        cache.set("prompt", "", "response")
        result = cache.get("prompt", "")
        
        # Should not cache
        assert result is None
    
    def test_cache_concurrent_access(self):
        """Test cache is thread-safe."""
        import threading
        
        cache = LLMCache(max_size=100, ttl_seconds=60.0)
        errors = []
        
        def worker(i):
            try:
                cache.set(f"prompt{i}", "", f"response{i}")
                result = cache.get(f"prompt{i}", "")
                assert result == f"response{i}"
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0  # No race conditions
    
    def test_cache_stats_accuracy(self):
        """Test statistics are accurate."""
        cache = LLMCache(max_size=5, ttl_seconds=60.0)
        
        # 3 sets
        cache.set("p1", "", "r1")
        cache.set("p2", "", "r2")
        cache.set("p3", "", "r3")
        
        # 2 hits, 2 misses
        cache.get("p1", "")  # hit
        cache.get("p2", "")  # hit
        cache.get("p4", "")  # miss
        cache.get("p5", "")  # miss
        
        stats = cache.get_stats()
        
        assert stats["current_size"] == 3
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 50.0
    
    def test_cache_key_generation(self):
        """Test cache key is consistent."""
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        
        # Same prompt + system should generate same key
        cache.set("test", "sys", "response1")
        cache.set("test", "sys", "response2")  # Overwrites
        
        result = cache.get("test", "sys")
        
        assert result == "response2"  # Latest value
        assert cache.get_stats()["current_size"] == 1  # Only one entry
