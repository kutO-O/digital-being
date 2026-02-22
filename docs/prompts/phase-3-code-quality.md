# Phase 3: Code Quality Enhancement

> **Goal:** Transform the working but rough codebase into production-grade code with proper type hints, documentation, error handling, and testing.

---

## Context

### Prerequisites
- ✅ Phase 1 audit complete
- ✅ Phase 2 critical fixes applied
- ✅ System runs stably for 24+ hours

### What We're Improving
Now that the system doesn't crash (Phase 2), we make it:
- **Readable:** Clear code that explains itself
- **Maintainable:** Easy to modify without breaking
- **Professional:** Follows all Python best practices
- **Testable:** Can verify behavior automatically

### Scope
Focus on **P1 (High Priority)** issues from Phase 1 audit:
- Missing type hints
- Inadequate docstrings
- Poor error messages
- Tight coupling
- Code style violations

---

## Your Task

### 1. Type Hints (PEP 484)

**Goal:** Every function and method has complete type annotations.

**Before:**
```python
def retrieve_memories(query, limit):
    results = self.vector_db.search(query, limit)
    return results
```

**After:**
```python
from typing import List, Dict, Any

def retrieve_memories(
    query: str, 
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Retrieve similar memories using vector search.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        
    Returns:
        List of memory dictionaries with metadata
    """
    results = self.vector_db.search(query, limit)
    return results
```

**Requirements:**
- ✅ All function parameters typed
- ✅ All return types specified
- ✅ Optional parameters marked as `Optional[T]`
- ✅ Complex types use `typing` module
- ✅ Passes `mypy --strict` checking

---

### 2. Comprehensive Docstrings (PEP 257)

**Goal:** Every public function, class, and module has clear documentation.

**Template:**
```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """One-line summary (ends with period).
    
    Detailed explanation of what this function does,
    including any important behavior or side effects.
    
    Design Decision (if applicable):
        Why this approach was chosen instead of alternatives.
        Example: "Uses BFS instead of DFS because..."
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this exception occurs
        
    Example:
        >>> result = function_name("test", 42)
        >>> print(result)
        expected_output
        
    Note:
        Any important caveats or warnings
    """
```

**Requirements:**
- ✅ All public APIs documented
- ✅ Complex internal functions documented
- ✅ Classes have docstrings explaining purpose
- ✅ Modules have docstrings at top
- ✅ Examples provided for non-obvious usage

---

### 3. Error Handling Improvements

**Goal:** Clear, actionable error messages with proper exception types.

**Before:**
```python
def load_config(path):
    data = json.load(open(path))
    return Config(data)
```

**After:**
```python
class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass

def load_config(path: Path) -> Config:
    """Load and validate configuration from YAML file.
    
    Args:
        path: Path to config file
        
    Returns:
        Validated Config object
        
    Raises:
        ConfigError: If file doesn't exist, is invalid, or fails validation
    """
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(
            f"Configuration file not found: {path}. "
            f"Create it by copying config.yaml.example"
        ) from None
    except yaml.YAMLError as e:
        raise ConfigError(
            f"Invalid YAML in {path}: {e}. "
            f"Check syntax at line {e.problem_mark.line}"
        ) from e
    
    try:
        return Config.from_dict(data)
    except ValueError as e:
        raise ConfigError(
            f"Configuration validation failed: {e}. "
            f"See docs/configuration.md for valid options"
        ) from e
```

**Requirements:**
- ✅ Custom exception types for domain errors
- ✅ Error messages explain what went wrong
- ✅ Error messages suggest how to fix
- ✅ Original exception preserved with `from e`
- ✅ No bare `except:` clauses

---

### 4. Decouple Tight Dependencies

**Goal:** Components depend on interfaces, not concrete implementations.

**Before:**
```python
class GoalManager:
    def __init__(self):
        self.memory = EpisodicMemory()  # Tight coupling
        self.ollama = OllamaClient()
```

**After:**
```python
from abc import ABC, abstractmethod
from typing import Protocol

class MemorySystem(Protocol):
    """Interface for memory storage and retrieval."""
    def store(self, event: Event) -> None: ...
    def retrieve(self, query: str) -> List[Event]: ...

class LLMProvider(Protocol):
    """Interface for LLM inference."""
    async def generate(self, prompt: str) -> str: ...

class GoalManager:
    """Manages agent goals and planning.
    
    Uses dependency injection for flexibility and testability.
    """
    def __init__(
        self,
        memory: MemorySystem,
        llm: LLMProvider,
        logger: Optional[logging.Logger] = None
    ):
        self.memory = memory
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)
```

**Benefits:**
- Easy to test (inject mocks)
- Easy to swap implementations
- Clear dependencies
- Follows Dependency Inversion Principle

---

### 5. Code Style Consistency

**Goal:** Entire codebase follows PEP 8 and project style guide.

**Tools:**
```bash
# Check style
flake8 core/ memory/ main.py

# Auto-format
black core/ memory/ main.py

# Sort imports
isort core/ memory/ main.py

# Type checking
mypy --strict core/ memory/ main.py
```

**Common Fixes:**
- Line length ≤ 88 characters (Black default)
- 2 blank lines between top-level definitions
- Imports sorted (stdlib, third-party, local)
- Consistent naming (snake_case, PascalCase)
- No trailing whitespace

---

### 6. Add Unit Tests

**Goal:** Critical paths have automated tests.

**Example:**
```python
# tests/test_memory.py
import pytest
from memory.episodic import EpisodicMemory

class TestEpisodicMemory:
    @pytest.fixture
    def memory(self, tmp_path):
        """Create isolated memory for each test."""
        db_path = tmp_path / "test.db"
        return EpisodicMemory(db_path)
    
    def test_store_and_retrieve(self, memory):
        """Test basic storage and retrieval."""
        # Given
        event = {"type": "test", "data": "hello"}
        
        # When
        memory.add_episode(event)
        results = memory.retrieve_recent(limit=1)
        
        # Then
        assert len(results) == 1
        assert results[0]["data"] == "hello"
    
    def test_retrieve_empty(self, memory):
        """Test retrieval from empty memory."""
        results = memory.retrieve_recent(limit=10)
        assert results == []
    
    def test_importance_filtering(self, memory):
        """Test filtering by importance score."""
        memory.add_episode({"type": "low", "importance": 0.2})
        memory.add_episode({"type": "high", "importance": 0.9})
        
        important = memory.retrieve_important(threshold=0.5)
        assert len(important) == 1
        assert important[0]["type"] == "high"
```

**Test Coverage Target:** 50% minimum
- All memory systems
- Core cognitive components
- Critical utility functions
- Error handling paths

---

## Output Format

### Component Refactoring Report

For each component improved:

```markdown
## Component: [Name]
**File:** `path/to/file.py`
**Status:** ✅ Complete

### Changes Made

#### Type Hints
- [x] All functions typed
- [x] Complex types documented
- [x] Passes mypy --strict

**Example:**
```python
# Before
def process(data, opts):
    ...

# After  
def process(data: List[Dict], opts: Optional[ProcessOpts] = None) -> Result:
    ...
```

#### Docstrings
- [x] All public APIs documented
- [x] Complex logic explained
- [x] Examples provided

**Coverage:** XX functions documented

#### Error Handling
- [x] Custom exceptions defined
- [x] Clear error messages
- [x] Fix suggestions included

**New Exception Types:**
- `MemoryError`: When memory operations fail
- `ConfigError`: When configuration is invalid

#### Decoupling
- [x] Dependencies injected
- [x] Interfaces defined
- [x] Testability improved

**Dependencies Removed:** X direct imports

#### Tests
- [x] Unit tests added
- [x] Coverage: XX%
- [x] All tests passing

**Test Files:**
- `tests/test_component.py` (XX tests)

### Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Type Coverage | XX% | YY% | +ZZ% |
| Docstring Coverage | XX% | YY% | +ZZ% |
| Test Coverage | XX% | YY% | +ZZ% |
| Pylint Score | X.X/10 | Y.Y/10 | +Z.Z |
| Lines of Code | XXX | YYY | Change |

### Breaking Changes
- None (or list if any)

### Migration Notes
- Any code using this component should... (if applicable)

---
```

---

## Success Criteria

**Phase 3 is complete when:**

### Code Quality
- [x] Type hints: 100% coverage on public APIs
- [x] Docstrings: 100% coverage on public APIs
- [x] Passes `flake8` with zero errors
- [x] Passes `mypy --strict` with zero errors
- [x] Formatted with `black` and `isort`

### Testing
- [x] Test coverage ≥50% overall
- [x] All core components have tests
- [x] All tests passing
- [x] Test suite runs in <1 minute

### Architecture
- [x] Major components use dependency injection
- [x] Interfaces defined for swappable dependencies
- [x] Circular dependencies removed
- [x] Component coupling reduced significantly

### Documentation
- [x] Every module has header docstring
- [x] Complex algorithms explained
- [x] Design decisions documented
- [x] Examples provided for non-obvious usage

---

## Deliverables

1. **Phase 3 Results Document**
   - Save as: `docs/prompts/phase-3-results.md`
   - Component-by-component improvements
   - Metrics before/after
   - Lessons learned

2. **Improved Code**
   - All P1 quality issues fixed
   - Code passes all linters
   - Tests passing
   - Committed with clear messages

3. **Test Suite**
   - `tests/` directory created
   - Test files for each major component
   - `pytest.ini` configuration
   - GitHub Actions workflow (optional)

4. **Updated Documentation**
   - Technical Debt Register (P1 marked "Fixed")
   - ARCHITECTURE_MASTER.md updated
   - New interfaces documented

---

## Execution Strategy

### Recommended Order

1. **Core Memory** (most used)
   - `memory/episodic.py`
   - `memory/vector_memory.py`
   - `memory/semantic_memory.py`

2. **Core Cognitive** (most complex)
   - `core/emotion_engine.py`
   - `core/reflection_engine.py`
   - `core/value_engine.py`

3. **Supporting Systems**
   - `core/goal_manager.py`
   - `core/strategy_engine.py`
   - `core/attention_system.py`

4. **Entry Point**
   - `main.py` (after everything else is clean)

### Per Component Workflow

```bash
# 1. Create branch
git checkout -b refactor/component-name

# 2. Add type hints
# 3. Add docstrings  
# 4. Fix error handling
# 5. Decouple dependencies
# 6. Write tests

# 7. Run quality checks
black path/to/file.py
isort path/to/file.py
flake8 path/to/file.py
mypy path/to/file.py
pytest tests/test_file.py

# 8. Commit
git add .
git commit -m "Refactor: Improve code quality in component

- Added complete type hints
- Added comprehensive docstrings
- Improved error handling with custom exceptions
- Decoupled dependencies
- Added unit tests (XX% coverage)

Passes: black, isort, flake8, mypy --strict
"

# 9. Merge
git checkout main
git merge refactor/component-name
git push
```

---

## Common Patterns

### Pattern 1: Optional Dependencies

```python
from typing import Optional
import logging

class Component:
    def __init__(
        self,
        required_dep: RequiredType,
        optional_dep: Optional[OptionalType] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.required = required_dep
        self.optional = optional_dep
        self.logger = logger or logging.getLogger(__name__)
```

### Pattern 2: Configuration Objects

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ComponentConfig:
    """Configuration for Component.
    
    Attributes:
        setting1: Description
        setting2: Description
    """
    setting1: str
    setting2: int = 100  # Default value
    setting3: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ComponentConfig':
        """Create config from dictionary, with validation."""
        # Validate and create
        ...
```

### Pattern 3: Protocol-based Interfaces

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MemoryProvider(Protocol):
    """Interface for memory storage systems."""
    
    def store(self, event: Event) -> str:
        """Store an event, return its ID."""
        ...
    
    def retrieve(self, query: str, limit: int) -> List[Event]:
        """Retrieve events matching query."""
        ...

# Usage
def process_with_memory(memory: MemoryProvider) -> None:
    # Works with any implementation of MemoryProvider
    ...
```

---

## Estimated Time

- **Per Component:** 3-6 hours
- **Core Memory (3 files):** 1-2 days
- **Core Cognitive (6 files):** 2-3 days
- **Supporting (8 files):** 3-4 days
- **Main.py:** 1 day
- **Testing & Validation:** 2 days

**Total Phase 3:** 2-3 weeks

---

## Quality Checklist

Before marking a component complete:

```markdown
- [ ] Type hints: 100% on public APIs
- [ ] Docstrings: 100% on public APIs  
- [ ] Custom exceptions for domain errors
- [ ] Clear error messages with fix suggestions
- [ ] Dependencies injected, not hardcoded
- [ ] No circular imports
- [ ] Passes `black --check`
- [ ] Passes `isort --check`
- [ ] Passes `flake8`
- [ ] Passes `mypy --strict`
- [ ] Unit tests written
- [ ] Test coverage ≥50%
- [ ] All tests passing
- [ ] Committed to git
```

---

**When ready, begin with the memory components as they're the foundation for everything else.**
