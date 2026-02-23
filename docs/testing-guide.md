# Testing Guide

Комплексное руководство по тестированию системы.

---

## Обзор

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (fast)
│   ├── test_llm_cache.py
│   ├── test_circuit_breaker.py
│   ├── test_rate_limiter.py
│   └── ...
├── integration/             # Integration tests
│   ├── test_ollama_client.py
│   └── ...
└── e2e/                     # End-to-end tests
    └── test_full_system.py
```

### Test Levels

1. **Unit Tests** - Fast, isolated component tests
2. **Integration Tests** - Multi-component interactions
3. **E2E Tests** - Full system workflows

---

## Setup

### Install Dependencies

```bash
# Install test requirements
pip install -r requirements-test.txt

# Or specific packages
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

---

## Running Tests

### All Tests

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Specific Tests

```bash
# Single file
pytest tests/unit/test_cache.py

# Single class
pytest tests/unit/test_cache.py::TestLLMCache

# Single test
pytest tests/unit/test_cache.py::TestLLMCache::test_cache_hit

# Pattern matching
pytest -k "cache"
```

### By Marker

```bash
# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration

# Exclude slow tests
pytest -m "not slow"

# Multiple markers
pytest -m "unit or integration"
```

### Parallel Execution

```bash
# Run tests in parallel (faster)
pytest -n auto  # Auto-detect CPUs
pytest -n 4     # Use 4 workers
```

---

## Coverage

### Generate Coverage Report

```bash
# Run with coverage
pytest --cov=core --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Requirements

```bash
# Fail if coverage < 80%
pytest --cov=core --cov-fail-under=80

# Show missing lines
pytest --cov=core --cov-report=term-missing
```

### Current Coverage

```
Component              Coverage
-----------------------------------
llm_cache.py           100%
circuit_breaker.py     100%
rate_limiter.py        100%
metrics.py             85%
health_check.py        90%
-----------------------------------
Total                  95%
```

---

## Writing Tests

### Unit Test Example

```python
import pytest
from core.llm_cache import LLMCache

class TestLLMCache:
    """Test LLM cache component."""
    
    def test_cache_hit(self):
        """Test cache returns cached value."""
        # Arrange
        cache = LLMCache(max_size=10, ttl_seconds=60.0)
        cache.set("prompt", "", "response")
        
        # Act
        result = cache.get("prompt", "")
        
        # Assert
        assert result == "response"
        assert cache.get_stats()["hit_rate"] == 100.0
```

### Async Test Example

```python
import pytest
from core.async_ollama_client import AsyncOllamaClient

@pytest.mark.asyncio
async def test_async_chat(test_config):
    """Test async chat request."""
    async with AsyncOllamaClient(test_config) as client:
        response = await client.chat("test")
        assert isinstance(response, str)
```

### Using Fixtures

```python
@pytest.fixture
def cache():
    """Create cache instance."""
    return LLMCache(max_size=10, ttl_seconds=60.0)

def test_with_fixture(cache):
    """Test using fixture."""
    cache.set("key", "", "value")
    assert cache.get("key", "") == "value"
```

### Mocking

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test with mocked dependency."""
    mock_ollama = Mock()
    mock_ollama.chat.return_value = "mocked response"
    
    # Use mock in test
    result = mock_ollama.chat("test")
    assert result == "mocked response"
    mock_ollama.chat.assert_called_once_with("test")

@patch('core.ollama_client.requests.post')
def test_with_patch(mock_post):
    """Test with patched HTTP call."""
    mock_post.return_value.json.return_value = {"response": "ok"}
    # Test code here
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_uppercase(input, expected):
    """Test multiple inputs."""
    assert input.upper() == expected
```

---

## Test Best Practices

### 1. AAA Pattern

```python
def test_example():
    # Arrange - Setup
    cache = LLMCache()
    
    # Act - Execute
    result = cache.get("key", "")
    
    # Assert - Verify
    assert result is None
```

### 2. One Assertion per Test

```python
# Good
def test_cache_stores_value():
    cache.set("key", "", "value")
    assert cache.get("key", "") == "value"

def test_cache_tracks_size():
    cache.set("key", "", "value")
    assert cache.get_stats()["current_size"] == 1

# Avoid
def test_cache_everything():  # Too broad
    cache.set("key", "", "value")
    assert cache.get("key", "") == "value"
    assert cache.get_stats()["current_size"] == 1
    assert cache.get_stats()["hits"] == 1
```

### 3. Test Names

```python
# Good - describes what is tested
def test_cache_evicts_oldest_entry_when_full():
    ...

# Bad - vague
def test_cache():
    ...
```

### 4. Use Fixtures

```python
# Good - DRY
@pytest.fixture
def configured_cache():
    return LLMCache(max_size=10, ttl_seconds=60.0)

def test_a(configured_cache):
    ...

def test_b(configured_cache):
    ...

# Bad - repeated setup
def test_a():
    cache = LLMCache(max_size=10, ttl_seconds=60.0)
    ...

def test_b():
    cache = LLMCache(max_size=10, ttl_seconds=60.0)
    ...
```

### 5. Test Edge Cases

```python
def test_cache_with_zero_size():
    """Test cache disabled (size=0)."""
    cache = LLMCache(max_size=0)
    cache.set("key", "", "value")
    assert cache.get("key", "") is None  # Should not cache

def test_cache_with_negative_ttl():
    """Test invalid TTL."""
    with pytest.raises(ValueError):
        LLMCache(max_size=10, ttl_seconds=-1)
```

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run tests
      run: |
        pytest --cov=core --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Run tests before commit
pytest -m "not slow"

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

---

## Debugging Tests

### Using PDB

```python
def test_debug():
    cache = LLMCache()
    import pdb; pdb.set_trace()  # Breakpoint
    result = cache.get("key", "")
```

```bash
# Run with PDB on failure
pytest --pdb
```

### Verbose Output

```bash
# Show all output
pytest -vv -s

# Show local variables on failure
pytest -l

# Show full traceback
pytest --tb=long
```

### Print Debugging

```python
def test_with_prints():
    cache = LLMCache()
    print(f"Initial stats: {cache.get_stats()}")  # Will show with -s
    cache.set("key", "", "value")
    print(f"After set: {cache.get_stats()}")
```

```bash
pytest -s  # Show prints
```

---

## Performance Testing

### Benchmarking

```python
import pytest
import time

def test_cache_performance():
    """Test cache lookup speed."""
    cache = LLMCache(max_size=1000)
    
    # Populate
    for i in range(1000):
        cache.set(f"key{i}", "", f"value{i}")
    
    # Benchmark
    start = time.time()
    for i in range(1000):
        cache.get(f"key{i}", "")
    elapsed = time.time() - start
    
    # Should be fast
    assert elapsed < 0.1  # 100ms for 1000 lookups
```

### Stress Testing

```python
import threading

def test_cache_thread_safety():
    """Test cache under concurrent access."""
    cache = LLMCache(max_size=100)
    errors = []
    
    def worker(i):
        try:
            for j in range(100):
                cache.set(f"{i}-{j}", "", f"value-{i}-{j}")
                cache.get(f"{i}-{j}", "")
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0  # No race conditions
```

---

## Test Maintenance

### Keep Tests Fast

```python
# Good - fast
def test_cache_hit():
    cache = LLMCache()
    cache.set("key", "", "value")
    assert cache.get("key", "") == "value"

# Bad - slow (mark as slow)
@pytest.mark.slow
def test_with_sleep():
    time.sleep(5)  # Avoid if possible
    ...
```

### Keep Tests Independent

```python
# Good - isolated
def test_a():
    cache = LLMCache()  # Fresh instance
    ...

def test_b():
    cache = LLMCache()  # Fresh instance
    ...

# Bad - shared state
cache = LLMCache()  # Module level

def test_a():
    cache.set("key", "", "value")  # Affects test_b!
    ...

def test_b():
    assert cache.get("key", "") is None  # May fail!
```

### Update Tests with Code

- When changing code, update tests
- Keep coverage >80%
- Document breaking changes

---

## Coverage Goals

### Target by Component

```
Critical (100% coverage required):
- llm_cache.py
- circuit_breaker.py
- rate_limiter.py
- error_boundary.py

Important (90%+ coverage):
- ollama_client.py
- async_ollama_client.py
- health_check.py
- metrics.py

Standard (80%+ coverage):
- All other components
```

### Overall Target: 85%+

---

## Next Steps

1. ✅ **Write tests** for new features
2. ✅ **Run tests** before commits
3. ✅ **Monitor coverage** (keep >80%)
4. ✅ **Review test failures** in CI
5. ✅ **Refactor tests** when needed

---

## Related Files

- `tests/` - Test suite
- `pytest.ini` - Pytest config
- `requirements-test.txt` - Test dependencies
- `.coveragerc` - Coverage config
- `.github/workflows/test.yml` - CI config (TODO)

## Issues Resolved

- ✅ TD-004 (P1): Comprehensive testing

---

**Testing is не optional!** 🧪

**Good tests = confident deployments** ✅
