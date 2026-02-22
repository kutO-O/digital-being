# Digital Being - Architecture Master Document

> **Last Updated:** 2026-02-22  
> **Version:** Stage 28-30 (Full Integration)  
> **Status:** 🟡 Functional but requires production-grade refactoring

---

## Executive Summary

**Digital Being** is an experimental autonomous AI agent built to explore the boundaries between complex automation and emergent intelligent behavior. The project aims to create a "digital companion" that exhibits memory, personality, emotions, learning, and self-modification capabilities.

### Current State

✅ **What Works:**
- Full 30-stage cognitive architecture implementation
- Memory systems (episodic, vector, semantic)
- Emotion and reflection engines
- Multi-agent coordination basics
- Self-evolution framework
- Web UI for introspection

⚠️ **Known Issues:**
- Code quality varies significantly across modules
- Technical debt from rapid iteration (30 stages added sequentially)
- Insufficient error handling in many places
- Missing comprehensive documentation
- No automated testing
- Performance not optimized

## Project Vision

### Core Goal
**Create a reference implementation** that represents the maximum achievable with 2026 technology for an autonomous AI companion.

### Success Criteria
1. **Production-Grade Code** - Every module follows best practices
2. **Emergent Behavior** - System exhibits unpredictable but meaningful actions
3. **Long-term Stability** - Runs for weeks/months without crashes
4. **Clear Documentation** - Any developer can understand architecture in <1 hour
5. **Maintainability** - Changes don't break unrelated components

---

## Architecture Overview

### High-Level Structure

```
┌────────────────────────────────────────────────────┐
│                   MAIN.PY                          │
│              (Entry Point & Orchestrator)          │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│               COGNITIVE LAYERS                     │
├────────────────────────────────────────────────────┤
│ Layer 0: Heavy Tick (Main Loop)                    │
│ Layer 1: Goal-Oriented Behavior                    │
│ Layer 2: Tool Registry                             │
│ Layer 3: Learning Engine                           │
│ Layer 4: Memory Consolidation                      │
│ Layer 5: Theory of Mind (User Model)               │
│ Layer 6: (Reserved)                                │
│ Layer 7: Proactive Behavior                        │
│ Layer 8: Meta-Learning Optimizer                   │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│               CORE SYSTEMS                         │
├────────────────────────────────────────────────────┤
│ • Memory (Episodic, Vector, Semantic)              │
│ • Emotions & Reflection                            │
│ • Values & Self-Model                              │
│ • Strategy & Goals                                 │
│ • Beliefs & Contradictions                         │
│ • Attention & Curiosity                            │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│           ADVANCED FEATURES (Stage 26-30)          │
├────────────────────────────────────────────────────┤
│ Stage 26: Skill Library                            │
│ Stage 27: Multi-Agent Basic                        │
│ Stage 28: Advanced Multi-Agent                     │
│ Stage 29: Long-term Memory                         │
│ Stage 30: Self-Evolution                           │
│ Stage 31: Autoscaler (API only)                    │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│               INTERFACES                           │
├────────────────────────────────────────────────────┤
│ • Web UI (http://127.0.0.1:8765)                   │
│ • Introspection API (REST)                         │
│ • File-based messaging (inbox.txt/outbox.txt)      │
│ • Ollama Integration (LLM backend)                 │
└────────────────────────────────────────────────────┘
```

---

## Component Inventory

### Core Components (Priority: Critical)

| Component | File | Status | Priority |
|-----------|------|--------|----------|
| Episodic Memory | `core/memory/episodic.py` | 🟡 Working | P0 |
| Vector Memory | `core/memory/vector_memory.py` | 🟡 Working | P0 |
| Semantic Memory | `core/memory/semantic_memory.py` | 🟡 New (Stage 29) | P0 |
| Heavy Tick | `core/fault_tolerant_heavy_tick.py` | 🟡 Complex | P0 |
| Emotion Engine | `core/emotion_engine.py` | 🟢 Stable | P1 |
| Reflection Engine | `core/reflection_engine.py` | 🟡 Working | P1 |
| Value Engine | `core/value_engine.py` | 🟢 Stable | P1 |
| Self Model | `core/self_model.py` | 🟢 Stable | P1 |
| Ollama Client | `core/ollama_client.py` | 🟢 Stable | P0 |

### Advanced Features (Priority: High)

| Component | File | Status | Priority |
|-----------|------|--------|----------|
| Skill Library | `core/skill_library.py` | 🟡 Working | P1 |
| Multi-Agent Coordinator | `core/multi_agent_coordinator.py` | 🟡 Basic | P2 |
| Task Delegation | `core/multi_agent/task_delegation.py` | 🟡 New | P2 |
| Consensus Builder | `core/multi_agent/consensus_builder.py` | 🟡 New | P2 |
| Agent Roles | `core/multi_agent/agent_roles.py` | 🟡 New | P2 |
| Memory Consolidation | `core/memory/memory_consolidation.py` | 🟡 New | P1 |
| Self Evolution | `core/self_evolution/self_evolution_manager.py` | 🔴 Risky | P3 |

### Supporting Systems (Priority: Medium)

| Component | Status | Notes |
|-----------|--------|-------|
| Attention System | 🟢 Stable | Focus management |
| Curiosity Engine | 🟢 Stable | Question generation |
| Narrative Engine | 🟢 Stable | Diary writing |
| Shell Executor | 🟡 Functional | Security concerns |
| Time Perception | 🟢 Stable | Pattern detection |
| Social Layer | 🟡 Basic | File-based messaging |
| Meta Cognition | 🟡 Working | Self-awareness |

**Legend:**
- 🟢 Stable - Production ready
- 🟡 Working - Functional but needs improvement
- 🔴 Risky - Requires careful review

---

## Known Problems

### P0 - Critical (Blocks Production Use)

1. **No Error Recovery in Heavy Tick**
   - File: `core/fault_tolerant_heavy_tick.py`
   - Issue: Crashes propagate, no graceful degradation
   - Impact: System stops completely on component failure

2. **Memory Leaks in Vector Memory**
   - File: `core/memory/vector_memory.py`
   - Issue: Embeddings not cleaned up properly
   - Impact: RAM usage grows unbounded

3. **Race Conditions in Multi-Agent**
   - File: `core/multi_agent_coordinator.py`
   - Issue: File-based message queue not thread-safe
   - Impact: Message loss or corruption

### P1 - High (Significant Quality Issues)

4. **Inconsistent Type Hints**
   - Files: Multiple across `core/`
   - Issue: Many functions lack proper type annotations
   - Impact: Hard to maintain, IDE support limited

5. **Poor Error Messages**
   - Files: Throughout codebase
   - Issue: Generic exceptions, no context
   - Impact: Debugging is painful

6. **Tight Coupling**
   - Files: `main.py`, heavy tick
   - Issue: Components directly depend on each other
   - Impact: Can't test or modify independently

### P2 - Medium (Technical Debt)

7. **No Configuration Validation**
   - File: `config.yaml`
   - Issue: Invalid configs crash at runtime
   - Impact: Bad user experience

8. **Hardcoded Paths**
   - Files: Multiple
   - Issue: Assumes specific directory structure
   - Impact: Not portable

9. **Missing Docstrings**
   - Files: ~40% of modules
   - Issue: No documentation for complex logic
   - Impact: Knowledge loss, hard onboarding

---

## Refactoring Roadmap

### Phase 1: Audit & Documentation (Week 1)
**Goal:** Understand current state completely

- [ ] Complete code audit with quality scores
- [ ] Document all architectural decisions
- [ ] Identify all technical debt
- [ ] Create dependency graph
- [ ] List all TODO/FIXME comments

**Deliverables:**
- Audit report with scores per module
- Architecture decision records (ADRs)
- Technical debt register

### Phase 2: Critical Fixes (Week 2-3)
**Goal:** Stabilize core systems

- [ ] Fix P0 issues (error recovery, memory leaks, race conditions)
- [ ] Add comprehensive logging
- [ ] Implement health checks for all components
- [ ] Add graceful degradation

**Success Metric:** System runs 7 days without crashes

### Phase 3: Code Quality (Week 4-6)
**Goal:** Production-grade implementation

- [ ] Add type hints everywhere (PEP 484)
- [ ] Write docstrings for all public APIs
- [ ] Refactor tight coupling
- [ ] Standardize error handling
- [ ] Add unit tests for critical paths

**Success Metric:** Passes strict linting, 50%+ test coverage

### Phase 4: Architecture Cleanup (Week 7-9)
**Goal:** Clean, maintainable design

- [ ] Extract interfaces for major components
- [ ] Implement dependency injection
- [ ] Consolidate duplicate functionality
- [ ] Optimize hot paths
- [ ] Document patterns and idioms

**Success Metric:** New features don't break existing code

### Phase 5: Advanced Features (Week 10+)
**Goal:** Polish and extend

- [ ] Improve multi-agent coordination
- [ ] Enhance memory consolidation
- [ ] Add telemetry and metrics
- [ ] Performance profiling
- [ ] Long-term stability testing

**Success Metric:** System exhibits emergent behavior

---

## Decision Log

### Why SQLite for Episodic Memory?
**Decision:** Use SQLite instead of PostgreSQL  
**Reasoning:**
- Single-file portability
- No external dependencies
- Good enough performance for <1M episodes
- ACID guarantees

**Alternatives Considered:**
- PostgreSQL: Overkill for single-user system
- JSON files: No query capabilities
- In-memory: Data loss on crashes

**Status:** ✅ Validated, keep

---

### Why File-based Multi-Agent Communication?
**Decision:** Use shared JSON files for agent messaging  
**Reasoning:**
- Simple to debug (can inspect files)
- No network setup required
- Works across processes

**Alternatives Considered:**
- Redis: Adds external dependency
- ZeroMQ: Network complexity
- Shared memory: Platform-specific

**Status:** ⚠️ Works but has race conditions, consider upgrade to SQLite queue

---

### Why Ollama over OpenAI API?
**Decision:** Use local Ollama for LLM inference  
**Reasoning:**
- Privacy (no data leaves machine)
- No API costs
- Works offline
- Full control over models

**Alternatives Considered:**
- OpenAI API: Costs money, privacy concerns
- llama.cpp: Lower level, more complex integration
- vLLM: Overkill for single user

**Status:** ✅ Validated, keep

---

## Style Guide

### Python Version
- **Target:** Python 3.11+
- Use modern syntax (match/case, | for Union types)

### Type Hints
```python
from typing import Optional, Dict, List, Any
from pathlib import Path

def process_memory(
    episodes: List[Dict[str, Any]],
    threshold: float = 0.5,
    output_path: Optional[Path] = None
) -> Dict[str, int]:
    """Process episodic memories and return statistics.
    
    Args:
        episodes: List of episode dictionaries
        threshold: Importance threshold (0.0-1.0)
        output_path: Optional path to save results
        
    Returns:
        Dictionary with processing statistics
        
    Raises:
        ValueError: If threshold is out of range
    """
    ...
```

### Error Handling
```python
# ❌ BAD
try:
    result = risky_operation()
except:
    pass

# ✅ GOOD
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    return default_value
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed trace for developers")
logger.info("Important state changes")
logger.warning("Recoverable issues")
logger.error("Failures that need attention")
logger.critical("System is broken")
```

### Documentation
```python
class MemorySystem:
    """Manages episodic and semantic memory storage.
    
    This class implements a two-tier memory architecture:
    - Episodic: Time-ordered events
    - Semantic: Extracted knowledge and concepts
    
    Design Decision:
        Uses SQLite for persistence instead of JSON files
        because we need ACID guarantees and query capabilities.
        
    Thread Safety:
        All public methods are thread-safe via internal locking.
        
    Example:
        >>> memory = MemorySystem(Path("./memory.db"))
        >>> memory.add_episode("user.message", "Hello world")
        >>> episodes = memory.get_recent(10)
    """
```

---

## Working with This Document

### For New Contributors
1. Read this document first
2. Review specific component docs in `docs/`
3. Check current phase in Roadmap
4. Pick a task from prompts in `docs/prompts/`

### For AI Assistants
When working on this project:
1. Always check this ARCHITECTURE_MASTER.md first
2. Follow the Style Guide strictly
3. Update Decision Log for significant choices
4. Mark tasks as complete in Roadmap
5. Add new problems to Known Problems section

### Keeping This Document Updated
- Update after each phase completion
- Add new decisions to Decision Log
- Move solved problems from Known Problems
- Keep Component Inventory current

---

## References

### Key Documentation
- [Stage 28-30 Integration](../STAGE_28-30_README.md)
- [Multi-Agent System](./MULTI_AGENT.md)
- [Skill Library](./SKILL_LIBRARY.md)
- [Advanced Cognitive Features](./ADVANCED_COGNITIVE_FEATURES.md)

### External Resources
- [Ollama Documentation](https://ollama.ai/)
- [LangChain Memory](https://python.langchain.com/docs/modules/memory/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

**Next Steps:** See `docs/WORKFLOW.md` for how to work with this documentation system.
