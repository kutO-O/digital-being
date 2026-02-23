"""
Pytest Configuration & Shared Fixtures
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


# ============================================================
# Pytest Configuration
# ============================================================

def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers",
        "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (slower, multi-component)"
    )
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end tests (slowest, full system)"
    )
    config.addinivalue_line(
        "markers",
        "slow: Slow tests (skip with -m 'not slow')"
    )


# ============================================================
# Event Loop (for async tests)
# ============================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Configuration Fixtures
# ============================================================

@pytest.fixture
def test_config() -> dict:
    """Minimal test configuration."""
    return {
        "ollama": {
            "base_url": "http://localhost:11434",
            "strategy_model": "llama3.2:3b",
            "embed_model": "nomic-embed-text",
            "timeout_sec": 30,
        },
        "cache": {
            "max_size": 10,
            "ttl_seconds": 60.0,
        },
        "rate_limit": {
            "chat_rate": 10.0,
            "chat_burst": 20,
            "embed_rate": 30.0,
            "embed_burst": 50,
        },
        "resources": {
            "budget": {
                "max_llm_calls": 10,
            }
        },
        "logging": {
            "level": "ERROR",  # Quiet during tests
            "dir": "logs",
        },
    }


@pytest.fixture
def test_config_no_cache(test_config: dict) -> dict:
    """Config without cache."""
    cfg = test_config.copy()
    cfg["cache"] = {"max_size": 0, "ttl_seconds": 0.0}
    return cfg


# ============================================================
# Temporary Directory Fixtures
# ============================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory, cleanup after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_dir: Path) -> Path:
    """Create temporary database file."""
    db_path = temp_dir / "test.db"
    return db_path


# ============================================================
# Mock Fixtures
# ============================================================

@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response."""
    return {
        "message": {
            "role": "assistant",
            "content": "Test response"
        },
        "done": True,
    }


@pytest.fixture
def mock_embedding():
    """Mock embedding vector."""
    return [0.1] * 768  # nomic-embed-text dimension


# ============================================================
# Cleanup Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Add any global cleanup here


# ============================================================
# Skip Markers
# ============================================================

def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Skip slow tests if --fast flag
    if config.getoption("-m") == "not slow":
        skip_slow = pytest.mark.skip(reason="Skipping slow tests (--fast)")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
