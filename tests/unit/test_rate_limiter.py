"""
Unit Tests for Rate Limiter
"""

import time
import pytest
from core.rate_limiter import RateLimiter, MultiRateLimiter


class TestRateLimiter:
    """Test token bucket rate limiter."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter creates with full bucket."""
        limiter = RateLimiter(rate=10.0, burst=20)
        
        stats = limiter.get_stats()
        assert stats["available_tokens"] == 20  # Full burst
        assert stats["accepted"] == 0
        assert stats["rejected"] == 0
    
    def test_rate_limiter_allows_within_rate(self):
        """Test limiter allows requests within rate."""
        limiter = RateLimiter(rate=10.0, burst=10)
        
        # Should allow 10 immediately (burst)
        for _ in range(10):
            assert limiter.acquire() is True
    
    def test_rate_limiter_rejects_over_rate(self):
        """Test limiter rejects requests over rate."""
        limiter = RateLimiter(rate=10.0, burst=5)
        
        # Use up burst
        for _ in range(5):
            limiter.acquire()
        
        # Next should be rejected (no time for refill)
        assert limiter.acquire() is False
    
    def test_rate_limiter_refills_tokens(self):
        """Test tokens refill over time."""
        limiter = RateLimiter(rate=10.0, burst=5)  # 10 tokens/sec
        
        # Use burst
        for _ in range(5):
            limiter.acquire()
        
        # Wait 0.5s (should refill 5 tokens)
        time.sleep(0.5)
        
        # Should allow more
        assert limiter.acquire() is True
    
    def test_rate_limiter_burst_capacity(self):
        """Test burst capacity is respected."""
        limiter = RateLimiter(rate=1.0, burst=10)
        
        # Should allow burst of 10
        allowed = sum(limiter.acquire() for _ in range(15))
        
        # Exactly 10 should be allowed
        assert allowed == 10
    
    def test_rate_limiter_statistics(self):
        """Test statistics tracking."""
        limiter = RateLimiter(rate=10.0, burst=5)
        
        # 5 allowed
        for _ in range(5):
            limiter.acquire()
        
        # 3 rejected
        for _ in range(3):
            limiter.acquire()
        
        stats = limiter.get_stats()
        
        assert stats["accepted"] == 5
        assert stats["rejected"] == 3
    
    def test_multi_rate_limiter(self):
        """Test multiple independent limiters."""
        multi = MultiRateLimiter()
        
        multi.add("chat", rate=5.0, burst=10)
        multi.add("embed", rate=20.0, burst=50)
        
        # Chat limiter
        for _ in range(10):
            assert multi.acquire("chat") is True
        assert multi.acquire("chat") is False  # Over burst
        
        # Embed limiter should still allow
        assert multi.acquire("embed") is True
    
    def test_multi_rate_limiter_all_stats(self):
        """Test stats for all limiters."""
        multi = MultiRateLimiter()
        multi.add("op1", rate=10.0, burst=5)
        multi.add("op2", rate=20.0, burst=10)
        
        multi.acquire("op1")
        multi.acquire("op2")
        
        all_stats = multi.get_all_stats()
        
        assert "op1" in all_stats
        assert "op2" in all_stats
        assert all_stats["op1"]["accepted"] == 1
        assert all_stats["op2"]["accepted"] == 1
    
    def test_rate_limiter_zero_rate(self):
        """Test limiter with rate 0 (disabled)."""
        limiter = RateLimiter(rate=0.0, burst=10)
        
        # Should allow up to burst
        for _ in range(10):
            assert limiter.acquire() is True
        
        # No refill
        assert limiter.acquire() is False
    
    def test_rate_limiter_concurrent_access(self):
        """Test rate limiter is thread-safe."""
        import threading
        
        limiter = RateLimiter(rate=100.0, burst=50)
        results = []
        
        def worker():
            results.append(limiter.acquire())
        
        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have exactly 50 accepts (burst capacity)
        assert sum(results) == 50
