"""
Test Suite for Digital Being

Structure:
  tests/
    ├── unit/          # Unit tests (isolated)
    ├── integration/   # Integration tests (multi-component)
    ├── e2e/          # End-to-end tests (full system)
    ├── fixtures/     # Shared test fixtures
    └── conftest.py   # Pytest configuration

Running tests:
  # All tests
  pytest
  
  # With coverage
  pytest --cov=core --cov-report=html
  
  # Specific test
  pytest tests/unit/test_cache.py
  
  # Watch mode
  pytest-watch
"""

__version__ = "1.0.0"
