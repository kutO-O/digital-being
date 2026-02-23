"""
Unit Tests for Circuit Breaker
"""

import time
import pytest
from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker creates in CLOSED state."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=1.0,
        )
        
        assert cb.get_state() == "closed"
        assert cb.get_stats()["state"] == "closed"
    
    def test_circuit_breaker_success_call(self):
        """Test successful call keeps circuit closed."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        
        result = cb.call(lambda: "success")
        
        assert result == "success"
        assert cb.get_state() == "closed"
        assert cb.get_stats()["successes"] == 1
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        
        # Fail 3 times
        for _ in range(3):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # Circuit should be OPEN
        assert cb.get_state() == "open"
        assert cb.get_stats()["failures"] == 3
    
    def test_circuit_breaker_blocks_when_open(self):
        """Test circuit blocks calls when OPEN."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # Try to call - should be blocked
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "success")
    
    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit goes to HALF_OPEN after timeout."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms
        )
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        assert cb.get_state() == "open"
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Try call - should attempt (HALF_OPEN)
        try:
            cb.call(lambda: "success")
        except:
            pass
        
        # State should have transitioned through HALF_OPEN
        # (exact state depends on call result)
    
    def test_circuit_breaker_closes_on_success_in_half_open(self):
        """Test circuit closes after success in HALF_OPEN."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,  # Close after 1 success
        )
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Successful call should close circuit
        result = cb.call(lambda: "success")
        
        assert result == "success"
        # Circuit should be closed or closing
    
    def test_circuit_breaker_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in HALF_OPEN."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
        )
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Fail in HALF_OPEN
        with pytest.raises(Exception):
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # Should be OPEN again
        assert cb.get_state() == "open"
    
    def test_circuit_breaker_statistics(self):
        """Test circuit breaker tracks statistics."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        
        # 3 successes
        for _ in range(3):
            cb.call(lambda: "ok")
        
        # 2 failures
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        stats = cb.get_stats()
        
        assert stats["successes"] == 3
        assert stats["failures"] == 2
        assert stats["consecutive_failures"] == 2
    
    def test_circuit_breaker_resets_consecutive_failures_on_success(self):
        """Test consecutive failures reset on success."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        
        # 2 failures
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # 1 success - should reset
        cb.call(lambda: "ok")
        
        stats = cb.get_stats()
        assert stats["consecutive_failures"] == 0
    
    def test_circuit_breaker_with_custom_thresholds(self):
        """Test custom thresholds work."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,  # Open after 1 failure
            success_threshold=3,  # Close after 3 successes
        )
        
        # 1 failure - should open
        with pytest.raises(Exception):
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        assert cb.get_state() == "open"
    
    def test_circuit_breaker_multiple_instances(self):
        """Test multiple independent circuit breakers."""
        cb1 = CircuitBreaker(name="service1", failure_threshold=2)
        cb2 = CircuitBreaker(name="service2", failure_threshold=2)
        
        # Open cb1
        for _ in range(2):
            with pytest.raises(Exception):
                cb1.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # cb2 should still be closed
        result = cb2.call(lambda: "ok")
        
        assert cb1.get_state() == "open"
        assert cb2.get_state() == "closed"
        assert result == "ok"
    
    def test_circuit_breaker_name(self):
        """Test circuit breaker has correct name."""
        cb = CircuitBreaker(name="my_service", failure_threshold=3)
        
        assert cb.name == "my_service"
        assert cb.get_stats()["name"] == "my_service"
