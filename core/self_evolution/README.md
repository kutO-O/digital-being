# Self-Evolution System 🧠✨

**Stage 30 Enhanced**: Autonomous code improvement and evolution with advanced safety and monitoring.

## Overview

The Self-Evolution system enables Digital Being to propose, test, and apply code changes to improve itself over time. This enhanced version includes LLM-powered code generation, comprehensive safety validation, performance monitoring, and automatic rollback capabilities.

## Architecture

```
┌─────────────────────────┐
│ SelfEvolutionManager   │
│    (Orchestrator)       │
└───────┬─────────────────┘
        │
  ┌─────┼────────────────┐
  │     │                  │
┌─┴───┐ ┌─┴────┐ ┌─────┴────┐
│ LLM │ │Safety│ │Performance│
│ Code│ │Valid-│ │  Monitor   │
│Asst.│ │ator  │ └───┬───────┘
└──┬──┘ └─┬───┘      │
   │      │           │
   └───┬──┴───────┬──┘
       │            │
  ┌────┴────┐  ┌──┴─────┐
  │Evolution │  │  Auto   │
  │ Sandbox  │  │Rollback │
  └─────────┘  └─────────┘
```

## Components

### 1. SelfEvolutionManager
**Main orchestrator** that coordinates the entire evolution process.

**Features:**
- Three evolution modes: `supervised`, `semi_autonomous`, `autonomous`
- Change proposal workflow
- Backup/restore system
- Change history tracking
- Approval management

**Usage:**
```python
from core.self_evolution import SelfEvolutionManager, EvolutionMode, ChangeType

manager = SelfEvolutionManager(
    storage_dir=Path("memory"),
    mode=EvolutionMode.SUPERVISED
)

# Propose a change
result = await manager.propose_change(
    change_type=ChangeType.OPTIMIZATION,
    description="Optimize vector memory search",
    module_name="vector_memory_optimized",
    reasoning="Current search is O(n), can be improved with indexing"
)

# Approve if in supervised mode
if result["success"]:
    manager.approve_change(result["proposal_id"])
```

### 2. LLMCodeAssistant ✨ NEW
**AI-powered code generation** using Ollama LLM.

**Features:**
- Context-aware code generation
- Bug fix suggestions
- Optimization recommendations
- Syntax validation
- Markdown code extraction

**Usage:**
```python
from core.self_evolution import LLMCodeAssistant

assistant = LLMCodeAssistant(ollama_client)

# Generate new module
result = await assistant.generate_module_code(
    module_name="advanced_planner",
    description="Plan multi-step tasks with resource allocation",
    requirements=[
        "Support priority-based scheduling",
        "Handle dependencies between tasks",
        "Implement resource constraints"
    ]
)

if result["success"]:
    code = result["code"]
```

### 3. SafetyValidator 🛡️ NEW
**Security-focused code validation** before execution.

**Features:**
- AST-based security analysis
- Dangerous pattern detection (eval, exec, os.system)
- Import restrictions
- Risk scoring (0.0 - 1.0)
- File/network operation detection

**Usage:**
```python
from core.self_evolution import SafetyValidator

validator = SafetyValidator()

result = validator.validate_code(code, module_name)

if result["safe"]:
    print(f"Risk level: {result['risk_level']}")
else:
    print(f"Issues found: {result['issues']}")
```

**Risk Levels:**
- `low` (0.0 - 0.3): Safe to execute
- `medium` (0.3 - 0.5): Requires review
- `high` (0.5 - 0.7): Dangerous, needs approval
- `critical` (0.7 - 1.0): Block execution

### 4. PerformanceMonitor 📊 NEW
**Tracks performance metrics** before and after changes.

**Features:**
- Baseline capture
- Post-change comparison
- Regression detection (>10% threshold)
- Execution time/memory tracking
- Automated rollback triggers

**Usage:**
```python
from core.self_evolution import PerformanceMonitor

monitor = PerformanceMonitor(storage_path)

# Capture baseline
monitor.capture_baseline("vector_memory", {
    "execution_time": 0.05,
    "memory_usage": 12.5,
    "throughput": 1000
})

# After change
result = monitor.capture_post_change(
    "vector_memory",
    change_id="change_123",
    metrics={
        "execution_time": 0.03,  # 40% improvement!
        "memory_usage": 10.0,
        "throughput": 1200
    }
)

if result["comparison"]["has_improvement"]:
    print("Performance improved!")
```

### 5. AutoRollbackHandler 🔄 NEW
**Automatically rolls back** problematic changes.

**Features:**
- Error threshold monitoring (default: 3 errors)
- Performance regression detection (>25%)
- Timeout detection (>30s)
- Health check integration
- Rollback history

**Usage:**
```python
from core.self_evolution import AutoRollbackHandler

rollback = AutoRollbackHandler()

# Start monitoring
rollback.monitor_change(
    change_id="change_123",
    module_name="vector_memory"
)

# Report errors
result = rollback.report_error(
    change_id="change_123",
    error="IndexError: list index out of range"
)

if result["should_rollback"]:
    # Trigger rollback in manager
    manager.rollback_change("change_123")
```

## Evolution Workflow

### Complete Example

```python
import asyncio
from pathlib import Path
from core.self_evolution import (
    SelfEvolutionManager,
    EvolutionMode,
    ChangeType,
    LLMCodeAssistant,
    SafetyValidator,
    PerformanceMonitor,
    AutoRollbackHandler
)

async def evolve_module():
    # Initialize components
    manager = SelfEvolutionManager(
        storage_dir=Path("memory"),
        mode=EvolutionMode.SEMI_AUTONOMOUS
    )
    
    assistant = LLMCodeAssistant(ollama_client)
    validator = SafetyValidator()
    monitor = PerformanceMonitor(Path("memory"))
    rollback = AutoRollbackHandler()
    
    # 1. Generate code with LLM
    gen_result = await assistant.generate_module_code(
        module_name="optimized_search",
        description="Fast vector search with FAISS",
        requirements=["Sub-millisecond search", "Handle 100k vectors"]
    )
    
    if not gen_result["success"]:
        return {"error": "Code generation failed"}
    
    code = gen_result["code"]
    
    # 2. Validate safety
    safety = validator.validate_code(code, "optimized_search")
    
    if not safety["safe"]:
        return {"error": f"Safety check failed: {safety['issues']}"}
    
    # 3. Capture baseline performance
    baseline = {"execution_time": 0.5, "memory_usage": 50}
    monitor.capture_baseline("optimized_search", baseline)
    
    # 4. Propose change
    proposal = manager.propose_change(
        change_type=ChangeType.OPTIMIZATION,
        description="FAISS-based vector search",
        module_name="optimized_search",
        reasoning="Current numpy search is too slow"
    )
    
    if not proposal["success"]:
        return {"error": "Proposal failed"}
    
    change_id = proposal["proposal_id"]
    
    # 5. Start monitoring
    rollback.monitor_change(change_id, "optimized_search")
    
    # 6. Apply change (in semi-autonomous, auto-approved if safe)
    # ... code is applied ...
    
    # 7. Measure performance
    new_metrics = {"execution_time": 0.001, "memory_usage": 45}
    perf_result = monitor.capture_post_change(
        "optimized_search",
        change_id,
        new_metrics
    )
    
    # 8. Check for rollback
    rollback_check = rollback.check_performance(change_id, perf_result)
    
    if rollback_check["should_rollback"]:
        manager.rollback_change(change_id)
        return {"status": "rolled_back", "reason": rollback_check["reason"]}
    
    # 9. Stop monitoring (change is stable)
    rollback.stop_monitoring(change_id)
    
    return {"status": "success", "change_id": change_id}

# Run
result = asyncio.run(evolve_module())
```

## Evolution Modes

### Supervised Mode
- **All changes require human approval**
- Safest mode for production
- Best for critical systems

### Semi-Autonomous Mode
- **Auto-approves low-risk changes** (bug fixes, optimizations)
- Requires approval for new features/modules
- Good balance of safety and autonomy

### Autonomous Mode
- **Fully autonomous** (if tests pass)
- Highest evolution speed
- Use only with comprehensive monitoring

## Safety Guarantees

1. **✅ All code is validated** before execution
2. **✅ Backups created** for all file modifications
3. **✅ Sandbox testing** before deployment
4. **✅ Performance monitoring** with auto-rollback
5. **✅ Change history** for audit trail

## Configuration

```yaml
# config.yaml
self_evolution:
  mode: "semi_autonomous"  # supervised | semi_autonomous | autonomous
  
  safety:
    max_risk_score: 0.5  # Block changes above this risk
    require_approval_above: 0.3
  
  performance:
    regression_threshold: 20.0  # % threshold for rollback
    improvement_threshold: 5.0   # % to consider improvement
  
  rollback:
    error_threshold: 3           # Errors before auto-rollback
    timeout_threshold: 30.0      # Seconds
  
  limits:
    max_changes_per_day: 10
    min_interval_between_changes: 300  # seconds
```

## Statistics & Monitoring

```python
# Get comprehensive stats
stats = manager.get_stats()

print(f"Evolution cycles: {stats['evolution_cycles']}")
print(f"Approval rate: {stats['approval_rate']:.1%}")
print(f"Pending approvals: {stats['pending_approvals']}")
print(f"Rollbacks: {stats['rollbacks']}")

# Component stats
print(f"LLM generations: {stats['code_generator']['generations']}")
print(f"Safety validations: {stats['sandbox']['validations']}")
```

## Best Practices

1. **Start with supervised mode** until confident
2. **Always validate safety** before applying changes
3. **Monitor performance** for regressions
4. **Set conservative rollback thresholds**
5. **Review rollback history** regularly
6. **Test in sandbox** before production
7. **Keep backups** of all critical files
8. **Log all changes** for debugging

## Roadmap

### Completed ✅
- LLM-powered code generation
- Safety validation system
- Performance monitoring
- Auto-rollback handler

### Future Enhancements
- 📅 Dependency analyzer
- 📅 Priority queue for changes
- 📅 Canary deployment (gradual rollout)
- 📅 A/B testing framework
- 📅 Genetic algorithm optimization
- 📅 Multi-agent evolution coordination

## License

Part of the Digital Being project.
