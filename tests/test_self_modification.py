"""
Unit tests for SelfModificationEngine.

Tests:
- Metrics tracking
- Rollback mechanism
- Health checks
- Config modifications
- Performance validation
- Risk scoring
"""

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.self_modification import SelfModificationEngine


class TestSelfModificationEngine:
    """Test suite for SelfModificationEngine."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_ollama(self):
        """Create mock OllamaClient."""
        mock = Mock()
        mock.is_available.return_value = True
        mock.chat.return_value = json.dumps({
            "approved": True,
            "comment": "Test approval",
            "risk_score": 0.3
        })
        return mock
    
    @pytest.fixture
    def config_path(self, temp_dir):
        """Create test config file."""
        config = {
            "ticks": {"heavy_tick_sec": 60},
            "dream": {"interval_hours": 8},
            "reflection": {"every_n_ticks": 10},
        }
        config_file = temp_dir / "config.yaml"
        with config_file.open("w") as f:
            yaml.dump(config, f)
        return config_file
    
    @pytest.fixture
    def engine(self, temp_dir, config_path, mock_ollama):
        """Create SelfModificationEngine instance."""
        memory_dir = temp_dir / "memory"
        memory_dir.mkdir()
        
        return SelfModificationEngine(
            config_path=config_path,
            memory_dir=memory_dir,
            ollama=mock_ollama,
            event_bus=None,
        )
    
    def test_initialization(self, engine):
        """Test engine initialization."""
        assert engine._total_applied == 0
        assert len(engine._history) == 0
        assert engine._config_path.exists()
    
    def test_load_config(self, engine):
        """Test loading configuration."""
        config = engine._load_config()
        assert "ticks" in config
        assert config["ticks"]["heavy_tick_sec"] == 60
    
    def test_get_config_value(self, engine):
        """Test getting config value with dotted notation."""
        value = engine._get_config_value("ticks.heavy_tick_sec")
        assert value == 60
        
        value = engine._get_config_value("dream.interval_hours")
        assert value == 8
        
        # Non-existent key
        value = engine._get_config_value("nonexistent.key")
        assert value is None
    
    def test_set_config_value(self, engine):
        """Test setting config value."""
        engine._set_config_value("ticks.heavy_tick_sec", 90)
        
        value = engine._get_config_value("ticks.heavy_tick_sec")
        assert value == 90
    
    def test_config_backup_and_restore(self, engine):
        """Test config backup and restore."""
        # Backup
        success = engine._backup_config()
        assert success is True
        assert engine._backup_path.exists()
        
        # Modify config
        engine._set_config_value("ticks.heavy_tick_sec", 120)
        assert engine._get_config_value("ticks.heavy_tick_sec") == 120
        
        # Restore
        success = engine._restore_backup()
        assert success is True
        assert engine._get_config_value("ticks.heavy_tick_sec") == 60
    
    def test_health_check_healthy(self, engine):
        """Test health check when system is healthy."""
        healthy, message = engine.health_check()
        assert healthy is True
        assert message == "healthy"
    
    def test_health_check_unhealthy_ollama(self, engine, mock_ollama):
        """Test health check when Ollama is unavailable."""
        mock_ollama.is_available.return_value = False
        
        healthy, message = engine.health_check()
        assert healthy is False
        assert "ollama" in message.lower()
    
    def test_capture_metrics(self, engine):
        """Test metrics capture."""
        metrics = engine.capture_metrics()
        
        assert "timestamp" in metrics
        assert "tick_duration_avg" in metrics
        assert "memory_usage_mb" in metrics
        assert "goal_success_rate" in metrics
        assert "error_count" in metrics
    
    def test_compare_metrics_improvement(self, engine):
        """Test metrics comparison when performance improves."""
        before = {
            "timestamp": 1.0,
            "tick_duration_avg": 2.0,
            "memory_usage_mb": 100.0,
            "goal_success_rate": 0.5,
            "error_count": 10,
        }
        
        after = {
            "timestamp": 2.0,
            "tick_duration_avg": 1.5,  # Better (lower)
            "memory_usage_mb": 90.0,    # Better (lower)
            "goal_success_rate": 0.7,   # Better (higher)
            "error_count": 5,            # Better (lower)
        }
        
        comparison = engine.compare_metrics(before, after)
        
        assert comparison["score"] > 0  # Positive = improvement
        assert comparison["degradation"] is False
    
    def test_compare_metrics_degradation(self, engine):
        """Test metrics comparison when performance degrades."""
        before = {
            "timestamp": 1.0,
            "tick_duration_avg": 1.0,
            "memory_usage_mb": 100.0,
            "goal_success_rate": 0.8,
            "error_count": 5,
        }
        
        after = {
            "timestamp": 2.0,
            "tick_duration_avg": 3.0,   # Worse (higher)
            "memory_usage_mb": 200.0,   # Worse (higher)
            "goal_success_rate": 0.4,   # Worse (lower)
            "error_count": 20,           # Worse (higher)
        }
        
        comparison = engine.compare_metrics(before, after)
        
        assert comparison["score"] < 0  # Negative = degradation
        # Note: might trigger auto-rollback if score < -0.3
    
    @pytest.mark.asyncio
    async def test_propose_whitelist_rejection(self, engine):
        """Test proposal rejection for non-whitelisted key."""
        result = await engine.propose(
            "invalid.key",
            100,
            "Testing invalid key"
        )
        
        assert result["status"] == "rejected"
        assert result["reason"] == "key_not_allowed"
    
    @pytest.mark.asyncio
    async def test_propose_bounds_rejection(self, engine):
        """Test proposal rejection for out-of-bounds value."""
        result = await engine.propose(
            "ticks.heavy_tick_sec",
            10000,  # Way above max (3600)
            "Testing out of bounds"
        )
        
        assert result["status"] == "rejected"
        assert result["reason"] == "out_of_bounds"
    
    @pytest.mark.asyncio
    async def test_propose_success(self, engine, mock_ollama):
        """Test successful proposal."""
        mock_ollama.chat.return_value = json.dumps({
            "approved": True,
            "comment": "Safe change",
            "risk_score": 0.2
        })
        
        result = await engine.propose(
            "ticks.heavy_tick_sec",
            90,
            "Need more thinking time"
        )
        
        assert result["status"] == "approved"
        assert result["old"] == 60
        assert result["new"] == 90
        assert "risk_score" in result
    
    @pytest.mark.asyncio
    async def test_propose_llm_rejection(self, engine, mock_ollama):
        """Test proposal rejected by LLM."""
        mock_ollama.chat.return_value = json.dumps({
            "approved": False,
            "comment": "Too risky",
            "risk_score": 0.9
        })
        
        result = await engine.propose(
            "ticks.heavy_tick_sec",
            3600,
            "Radical change"
        )
        
        assert result["status"] == "rejected"
        assert "Too risky" in result["reason"]
    
    def test_rollback_last_no_history(self, engine):
        """Test rollback when no history exists."""
        result = engine.rollback_last()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rollback_last_success(self, engine, mock_ollama):
        """Test successful rollback of last change."""
        # Make a change
        await engine.propose(
            "ticks.heavy_tick_sec",
            90,
            "Test change"
        )
        
        assert engine._get_config_value("ticks.heavy_tick_sec") == 90
        
        # Rollback
        result = engine.rollback_last()
        assert result is True
        assert engine._get_config_value("ticks.heavy_tick_sec") == 60
    
    def test_get_stats(self, engine):
        """Test statistics retrieval."""
        stats = engine.get_stats()
        
        assert "total_applied" in stats
        assert "approved" in stats
        assert "rejected" in stats
        assert "rolled_back" in stats
        assert "success_rate" in stats
    
    def test_get_metrics_report(self, engine):
        """Test metrics report generation."""
        report = engine.get_metrics_report()
        
        assert "active_monitoring" in report
        assert "changes_with_metrics" in report
        assert "performance_improvements" in report
        assert "performance_degradations" in report
    
    def test_suggest_improvements(self, engine, mock_ollama):
        """Test improvement suggestions generation."""
        mock_ollama.chat.return_value = json.dumps([
            {
                "key": "ticks.heavy_tick_sec",
                "value": 120,
                "reason": "More time for deep thinking"
            }
        ])
        
        reflection_log = [
            {"timestamp_str": "2026-02-23", "insight": "Need more processing time"}
        ]
        emotion_state = {
            "dominant": ("curious", 0.8),
            "emotions": {"curious": 0.8, "calm": 0.6}
        }
        
        suggestions = engine.suggest_improvements(reflection_log, emotion_state)
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        if suggestions:
            assert "key" in suggestions[0]
            assert "value" in suggestions[0]
            assert "reason" in suggestions[0]
    
    def test_history_tracking(self, engine):
        """Test that history is properly tracked."""
        engine._add_to_history(
            key="test.key",
            old_value=10,
            new_value=20,
            reason="Test",
            status="approved",
            llm_comment="Test comment"
        )
        
        history = engine.get_history(limit=10)
        assert len(history) == 1
        assert history[0]["key"] == "test.key"
        assert history[0]["status"] == "approved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
