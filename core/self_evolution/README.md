# Self-Evolution System 🧠✨

**Stage 30 Complete**: Production-ready autonomous code evolution with enterprise-grade safety.

## Overview

The Self-Evolution system enables Digital Being to propose, test, and apply code changes to improve itself over time. This complete version includes **8 advanced components** for intelligent, safe, and controlled code evolution.

## Architecture

```
         ┌─────────────────────────────┐
         │  Self Evolution Manager    │
         │       (Orchestrator)         │
         └─────────┬───────────────────┘
                  │
    ┌─────────┼─────────────┐
    │             │              │
┌───┴────┐  ┌────┴─────┐  ┌─┴──────┐
│Priority │  │ Rate      │  │ Canary  │
│ Queue   │  │ Limiter   │  │ Deploy  │
└───┬────┘  └────┬─────┘  └─┬──────┘
    │           │            │
    └────┬──────┼────────┬───┘
         │       │         │
    ┌────┴────┬─┴────┬──┴───┐
    │           │        │      │
┌───┴────┐  ┌─┴─────┐ ┌┴─────┐ ┌┴────────┐
│   LLM   │  │Safety │ │ Perf. │ │   Auto   │
│  Code   │  │Valid- │ │Monitor│ │ Rollback │
│Assistant│  │ator   │ └───────┘ └──────────┘
└─────────┘  └───┬────┘
               │
          ┌────┴─────────┐
          │  Dependency   │
          │   Analyzer    │
          └──────────────┘
```

## Components

### **Priority 1: Critical Safety & Intelligence**

#### 1. SelfEvolutionManager (Core Orchestrator)
**Main coordinator** of the entire evolution process.

**Features:**
- Three evolution modes: `supervised`, `semi_autonomous`, `autonomous`
- Change proposal workflow
- Backup/restore system
- Change history tracking
- Approval management

#### 2. LLMCodeAssistant ✨
**AI-powered code generation** using Ollama LLM.

**Features:**
- Context-aware code generation
- Bug fix suggestions
- Optimization recommendations
- Syntax validation

**Example:**
```python
assistant = LLMCodeAssistant(ollama_client)
result = await assistant.generate_module_code(
    module_name="advanced_planner",
    description="Multi-step task planner",
    requirements=["Priority scheduling", "Resource constraints"]
)
```

#### 3. SafetyValidator 🛡️
**Security-focused validation** before execution.

**Risk Levels:** low (0.0-0.3), medium (0.3-0.5), high (0.5-0.7), critical (0.7-1.0)

**Checks:**
- Dangerous imports (subprocess, eval, exec)
- File/network operations
- Code complexity
- AST-based analysis

#### 4. PerformanceMonitor 📊
**Tracks metrics** before and after changes.

**Features:**
- Baseline capture
- Regression detection (>10%)
- Execution time/memory tracking
- Automated rollback triggers

#### 5. AutoRollbackHandler 🔄
**Automatic rollback** for problematic changes.

**Triggers:**
- Error threshold (default: 3 errors)
- Performance regression (>25%)
- Timeout (>30s)
- Health check failures

---

### **Priority 2: Advanced Features**

#### 6. DependencyAnalyzer 🕵️ NEW
**Analyzes code dependencies** to assess change impact.

**Features:**
- Import dependency mapping
- Impact assessment (what will break)
- Circular dependency detection
- Risk scoring based on dependents
- Dependency graph visualization

**Usage:**
```python
analyzer = DependencyAnalyzer(project_root)

# Analyze module
result = analyzer.analyze_module_dependencies(
    module_name="core.vector_memory"
)

# Assess impact of change
impact = analyzer.assess_change_impact(
    module_name="core.vector_memory",
    change_type="update"
)

print(f"Affects {impact['dependent_count']} modules")
print(f"Risk: {impact['risk_level']}")
```

**Key Metrics:**
- Direct dependents
- Impact depth (cascade levels)
- Importance score
- Risk level: low, medium, high, critical

#### 7. PriorityQueue 📈 NEW
**Manages prioritized queue** of code changes.

**Features:**
- Priority-based scheduling
- Urgency levels (critical, high, normal, low)
- Dynamic priority adjustment
- Queue persistence
- Conflict detection

**Usage:**
```python
queue = PriorityQueue(storage_path)

# Add to queue
queue.enqueue(
    change_id="change_123",
    module_name="vector_memory",
    change_type="optimization",
    description="Add FAISS indexing",
    urgency="high"
)

# Get next change
request = queue.dequeue()
```

**Priority Calculation:**
- Change type (bug_fix=0.8, security=1.0, optimization=0.6)
- Urgency multiplier (critical=1.5x, high=1.2x)
- Risk factor (lower risk = higher priority)
- Impact factor (higher impact = higher priority)

#### 8. EvolutionRateLimiter ⏱️ NEW
**Controls evolution speed** to prevent instability.

**Features:**
- Time-based limits (per hour/day)
- Module-specific cooldowns
- Exponential backoff after failures
- Burst protection

**Usage:**
```python
limiter = EvolutionRateLimiter(
    storage_path=Path("memory"),
    max_per_hour=5,
    max_per_day=20,
    min_interval=300  # 5 minutes
)

# Check if can proceed
result = limiter.can_proceed(
    module_name="vector_memory",
    change_type="update"
)

if result["allowed"]:
    # Apply change
    limiter.record_change("vector_memory", "change_123", success=True)
```

**Cooldown Schedule:**
- 1st failure: 5 minutes
- 2nd failure: 15 minutes
- 3rd failure: 30 minutes
- 4th+ failure: 1-4 hours

#### 9. CanaryDeployment 🐥 NEW
**Gradual rollout** of changes to minimize risk.

**Deployment Stages:**
1. **Validation** (0%) - Testing phase
2. **Canary** (10%) - Small rollout, 5 min minimum
3. **Pilot** (30%) - Expanded rollout, 10 min minimum
4. **Production** (100%) - Full deployment

**Usage:**
```python
canary = CanaryDeployment(storage_path)

# Start deployment
canary.start_deployment(
    change_id="change_123",
    module_name="vector_memory",
    description="FAISS optimization",
    success_criteria={
        "min_success_rate": 0.95,
        "max_error_rate": 0.05
    }
)

# Record metrics
canary.record_metrics("change_123", {
    "success": 1,
    "error": 0,
    "latency": 0.03
})

# Auto-progresses or rolls back based on criteria
```

**Success Criteria:**
- Success rate ≥ 95%
- Error rate ≤ 5%
- Latency ≤ threshold

---

## Complete Evolution Workflow

```python
import asyncio
from pathlib import Path
from core.self_evolution import *

async def evolve_with_all_features():
    # Initialize all components
    manager = SelfEvolutionManager(Path("memory"), EvolutionMode.SEMI_AUTONOMOUS)
    assistant = LLMCodeAssistant(ollama_client)
    validator = SafetyValidator()
    monitor = PerformanceMonitor(Path("memory"))
    rollback = AutoRollbackHandler()
    analyzer = DependencyAnalyzer(Path("."))
    queue = PriorityQueue(Path("memory"))
    limiter = EvolutionRateLimiter(Path("memory"))
    canary = CanaryDeployment(Path("memory"))
    
    # 1. Generate code
    gen_result = await assistant.generate_module_code(
        module_name="optimized_search",
        description="Fast vector search"
    )
    code = gen_result["code"]
    
    # 2. Validate safety
    safety = validator.validate_code(code, "optimized_search")
    if not safety["safe"]:
        return {"error": "Safety check failed"}
    
    # 3. Analyze dependencies & impact
    impact = analyzer.assess_change_impact("optimized_search", "update")
    print(f"Impact: {impact['dependent_count']} modules, risk={impact['risk_level']}")
    
    # 4. Add to priority queue
    queue.enqueue(
        change_id="change_123",
        module_name="optimized_search",
        change_type="optimization",
        description="FAISS integration",
        urgency="high",
        metadata={"risk_score": safety["risk_score"], "impact_score": impact["risk_score"]}
    )
    
    # 5. Check rate limits
    rate_check = limiter.can_proceed("optimized_search")
    if not rate_check["allowed"]:
        return {"error": f"Rate limited: {rate_check['message']}"}
    
    # 6. Start canary deployment
    canary.start_deployment(
        change_id="change_123",
        module_name="optimized_search",
        description="Performance optimization"
    )
    
    # 7. Start monitoring
    rollback.monitor_change("change_123", "optimized_search")
    
    # 8. Progressive deployment with metrics
    while True:
        # Route traffic based on canary stage
        use_new = canary.should_use_new_version("change_123")
        
        # Measure performance
        exec_result = monitor.measure_execution(test_function)
        
        # Record metrics
        decision = canary.record_metrics("change_123", {
            "success": 1 if exec_result["metrics"]["success"] else 0,
            "latency": exec_result["metrics"]["execution_time"]
        })
        
        # Check decision
        if decision["action"] == "rollback":
            canary.rollback("change_123", decision["reason"])
            manager.rollback_change("change_123")
            return {"status": "rolled_back"}
        elif decision["action"] == "progress":
            canary.progress_stage("change_123")
            if decision["stage"] == "production":
                break
    
    # 9. Record success
    limiter.record_change("optimized_search", "change_123", success=True)
    rollback.stop_monitoring("change_123")
    canary.complete("change_123")
    
    return {"status": "success"}
```

## Configuration

```yaml
self_evolution:
  mode: "semi_autonomous"
  
  safety:
    max_risk_score: 0.5
    require_approval_above: 0.3
  
  performance:
    regression_threshold: 20.0
    improvement_threshold: 5.0
  
  rollback:
    error_threshold: 3
    timeout_threshold: 30.0
    performance_threshold: 25.0
  
  rate_limits:
    max_per_hour: 5
    max_per_day: 20
    min_interval: 300
  
  canary:
    validation_duration: 60
    canary_duration: 300
    pilot_duration: 600
    min_success_rate: 0.95
```

## Statistics Dashboard

```python
# Get comprehensive statistics
stats = {
    "manager": manager.get_stats(),
    "validator": validator.get_stats(),
    "monitor": monitor.get_stats(),
    "rollback": rollback.get_stats(),
    "analyzer": analyzer.get_stats(),
    "queue": queue.get_stats(),
    "limiter": limiter.get_stats(),
    "canary": canary.get_stats()
}

print(f"""
📊 Self-Evolution Statistics:
  Evolution Cycles: {stats['manager']['evolution_cycles']}
  Approval Rate: {stats['manager']['approval_rate']:.1%}
  Rollbacks: {stats['manager']['rollbacks']}
  
  Safety:
    Validations: {stats['validator']['validations']}
    Pass Rate: {stats['validator']['pass_rate']:.1%}
  
  Performance:
    Monitored Modules: {stats['monitor']['monitored_modules']}
  
  Dependencies:
    Modules Tracked: {stats['analyzer']['modules_tracked']}
    Circular Deps: {stats['analyzer']['circular_dependencies']}
  
  Queue:
    Pending: {stats['queue']['pending_requests']}
    Success Rate: {stats['queue']['success_rate']:.1%}
  
  Rate Limiting:
    Block Rate: {stats['limiter']['block_rate']:.1%}
    Changes (24h): {stats['limiter']['changes_last_24h']}
  
  Canary:
    Active Deployments: {stats['canary']['active']}
    Success Rate: {stats['canary']['success_rate']:.1%}
""")
```

## Best Practices

1. ✅ **Start supervised** until system proven
2. ✅ **Validate safety** always before deployment
3. ✅ **Analyze dependencies** before major changes
4. ✅ **Use priority queue** for organized evolution
5. ✅ **Respect rate limits** to prevent instability
6. ✅ **Deploy gradually** with canary rollouts
7. ✅ **Monitor metrics** continuously
8. ✅ **Review rollbacks** to learn from failures

## Roadmap

### ✅ Completed
- **Priority 1**: LLM, Safety, Performance, Auto-Rollback
- **Priority 2**: Dependencies, Priority Queue, Rate Limiter, Canary

### 📅 Future (Priority 3)
- A/B testing framework
- Genetic algorithm optimization
- Multi-agent coordination
- Visual dependency graphs
- ML-based risk prediction

## License

Part of the Digital Being project.
