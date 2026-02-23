"""
Unit tests for HotReloader.

Tests:
- File change detection
- Syntax validation
- Dependency tracking
- Notifications
- Rollback on errors
- Statistics
"""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.hot_reloader import HotReloader


class TestHotReloader:
    """Test suite for HotReloader."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def reloader(self, temp_dir):
        """Create HotReloader instance."""
        watch_dir = temp_dir / "core"
        watch_dir.mkdir()
        
        outbox = temp_dir / "outbox.txt"
        
        return HotReloader(
            watch_dirs=[str(watch_dir)],
            check_interval=0.1,
            auto_reload=True,
            outbox_path=str(outbox),
            enable_notifications=True,
        )
    
    def test_initialization(self, reloader, temp_dir):
        """Test HotReloader initialization."""
        assert reloader._auto_reload is True
        assert reloader._enable_notifications is True
        assert reloader._check_interval == 0.1
        assert len(reloader._blacklist) > 0
    
    def test_file_to_module_conversion(self, reloader):
        """Test converting file path to module name."""
        # Normal case
        module = reloader.file_to_module("core/emotions.py")
        assert module == "core.emotions"
        
        # __init__ case
        module = reloader.file_to_module("core/__init__.py")
        assert module == "core"
        
        # Nested
        module = reloader.file_to_module("core/memory/vector.py")
        assert module == "core.memory.vector"
    
    def test_syntax_validation_valid(self, reloader, temp_dir):
        """Test syntax validation with valid code."""
        test_file = temp_dir / "core" / "test.py"
        test_file.write_text(
            "def hello():\n    return 'world'\n",
            encoding="utf-8"
        )
        
        is_valid, error = reloader.validate_syntax(str(test_file))
        assert is_valid is True
        assert error == ""
    
    def test_syntax_validation_invalid(self, reloader, temp_dir):
        """Test syntax validation with invalid code."""
        test_file = temp_dir / "core" / "broken.py"
        test_file.write_text(
            "def hello(\n    return 'broken'\n",  # Missing closing paren
            encoding="utf-8"
        )
        
        is_valid, error = reloader.validate_syntax(str(test_file))
        assert is_valid is False
        assert "Line" in error
    
    def test_detect_changes_new_file(self, reloader, temp_dir):
        """Test detection of new file."""
        # Initial scan
        reloader.scan_files()
        
        # Create new file
        test_file = temp_dir / "core" / "new_module.py"
        test_file.write_text("# New module\n", encoding="utf-8")
        
        # Should detect as new (but not as changed)
        changed = reloader.detect_changes()
        assert len(changed) == 0  # New files are tracked but not "changed"
    
    def test_detect_changes_modified_file(self, reloader, temp_dir):
        """Test detection of modified file."""
        # Create file
        test_file = temp_dir / "core" / "test_module.py"
        test_file.write_text("# Version 1\n", encoding="utf-8")
        
        # Initial scan
        reloader.scan_files()
        reloader.detect_changes()
        
        # Modify file
        time.sleep(0.1)  # Ensure mtime changes
        test_file.write_text("# Version 2\n", encoding="utf-8")
        
        # Should detect change
        changed = reloader.detect_changes()
        assert len(changed) == 1
        assert "test_module.py" in changed[0]
    
    def test_blacklist_functionality(self, reloader):
        """Test module blacklisting."""
        # Add to blacklist
        reloader.blacklist_module("core.critical")
        assert "core.critical" in reloader._blacklist
        
        # Should not reload blacklisted module
        with patch.object(sys.modules, '__contains__', return_value=True):
            result = reloader.reload_module("core.critical")
            assert result is False
    
    def test_notifications_sent(self, reloader, temp_dir):
        """Test that notifications are written to outbox."""
        reloader.send_notification("core.test", "success", "test reload")
        
        outbox_path = temp_dir / "outbox.txt"
        assert outbox_path.exists()
        
        content = outbox_path.read_text(encoding="utf-8")
        assert "🔥" in content
        assert "core.test" in content
        assert "test reload" in content
    
    def test_notifications_disabled(self, reloader, temp_dir):
        """Test that notifications can be disabled."""
        reloader.disable_notifications()
        reloader.send_notification("core.test", "success")
        
        outbox_path = temp_dir / "outbox.txt"
        # File might exist but should not have new content
        if outbox_path.exists():
            content = outbox_path.read_text(encoding="utf-8")
            assert len(content) == 0
    
    def test_statistics_tracking(self, reloader):
        """Test statistics are tracked correctly."""
        initial_stats = reloader.get_stats()
        assert initial_stats["total_reloads"] == 0
        assert initial_stats["successful_reloads"] == 0
        assert initial_stats["failed_reloads"] == 0
        
        # Simulate successful reload
        reloader._stats["total_reloads"] = 5
        reloader._stats["successful_reloads"] = 4
        reloader._stats["failed_reloads"] = 1
        
        stats = reloader.get_stats()
        assert stats["total_reloads"] == 5
        assert stats["success_rate"] == 0.8
    
    def test_callback_execution(self, reloader):
        """Test that callbacks are executed after reload."""
        callback = Mock()
        reloader.add_callback("test.module", callback)
        
        # Create mock module
        mock_module = MagicMock()
        with patch.dict(sys.modules, {"test.module": mock_module}):
            with patch('importlib.reload', return_value=mock_module):
                reloader.reload_module("test.module")
        
        # Callback should have been called
        callback.assert_called_once()
    
    def test_auto_reload_can_be_toggled(self, reloader):
        """Test auto-reload can be enabled/disabled."""
        assert reloader._auto_reload is True
        
        reloader.disable_auto_reload()
        assert reloader._auto_reload is False
        
        reloader.enable_auto_reload()
        assert reloader._auto_reload is True
    
    def test_dependency_tracking(self, reloader):
        """Test basic dependency tracking."""
        # This is a simple test - real dependency tracking is complex
        # We just verify the method exists and returns a set
        deps = reloader.analyze_dependencies("test.module")
        assert isinstance(deps, set)
    
    def test_check_throttling(self, reloader):
        """Test that check() respects throttling interval."""
        # First check should work
        result1 = reloader.check()
        assert isinstance(result1, dict)
        
        # Immediate second check should be throttled
        result2 = reloader.check()
        assert result2 == {}  # Empty due to throttling
        
        # After interval, should work again
        time.sleep(0.2)  # check_interval is 0.1
        result3 = reloader.check()
        assert isinstance(result3, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
