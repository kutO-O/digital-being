# 🧠 Stage 28-30: Full Cognitive Architecture

## Overview

This document covers the final three stages of Digital Being's cognitive architecture:

- **Stage 28**: Advanced Multi-Agent Coordination
- **Stage 29**: Long-term Memory Systems  
- **Stage 30**: Self-Evolution Framework

Together, these stages complete the full 8-layer cognitive architecture with advanced collaboration, persistent knowledge, and self-modification capabilities.

---

## 🤝 Stage 28: Advanced Multi-Agent Coordination

### Features

#### 1. AgentRoles - Dynamic Role Management

**Purpose**: Assign and manage specialized roles for agents in a multi-agent network.

**Available Roles**:
- `coordinator` - Orchestrates tasks, makes high-level decisions
- `specialist` - Domain expert (research, coding, testing, etc.)
- `worker` - Executes assigned tasks

**Key Capabilities**:
```python
from core.multi_agent.agent_roles import AgentRoles

roles = AgentRoles(storage_dir)

# Assign role to agent
roles.assign_role(agent_id="agent_123", role="specialist")

# Update capabilities
roles.update_capabilities(
    agent_id="agent_123",
    capabilities=["python", "data_analysis", "machine_learning"]
)

# Get best agent for task
best_agent = roles.get_best_agent_for_task(
    required_capabilities=["python", "data_analysis"]
)
```

**Configuration**:
```yaml
advanced_multi_agent:
  roles:
    enabled: true
    auto_assign: true
    reassign_on_failure: true
```

---

#### 2. TaskDelegation - Intelligent Task Routing

**Purpose**: Automatically delegate tasks to the most suitable agent.

**Task Selection Strategies**:
- `best_match` - Match task requirements to agent capabilities
- `round_robin` - Distribute tasks evenly
- `load_balanced` - Consider current agent workload

**Key Capabilities**:
```python
from core.multi_agent.task_delegation import TaskDelegation

delegation = TaskDelegation(storage_dir)

# Create and delegate task
task_id = delegation.create_task(
    task_type="analysis",
    description="Analyze sales data for Q4",
    required_capabilities=["data_analysis", "python"],
    priority="high",
    deadline_sec=3600
)

# Delegate to best agent
assignment = delegation.delegate_task(task_id)

# Update task status
delegation.update_task_status(
    task_id=task_id,
    status="completed",
    result={"insights": [...], "charts": [...]}
)
```

**Configuration**:
```yaml
advanced_multi_agent:
  task_delegation:
    enabled: true
    auto_delegate: false
    selection_strategy: "best_match"
    default_timeout_sec: 120
    max_retries: 2
```

---

#### 3. ConsensusBuilder - Democratic Decision Making

**Purpose**: Enable multi-agent voting and consensus on important decisions.

**Proposal Types**:
- `system_change` - Modify system configuration
- `resource_allocation` - Allocate shared resources
- `task_priority` - Change task priorities
- `agent_action` - Agent should take specific action

**Key Capabilities**:
```python
from core.multi_agent.consensus_builder import ConsensusBuilder

consensus = ConsensusBuilder(storage_dir)

# Create proposal
proposal_id = consensus.create_proposal(
    proposal_type="system_change",
    title="Increase memory consolidation frequency",
    description="Change from 2h to 1h for better retention",
    proposed_by="agent_coordinator",
    proposed_changes={
        "config_key": "longterm_memory.consolidation.interval_hours",
        "old_value": 2,
        "new_value": 1
    }
)

# Agents cast votes
consensus.cast_vote(proposal_id, "agent_specialist_1", vote=True)
consensus.cast_vote(proposal_id, "agent_specialist_2", vote=True)
consensus.cast_vote(proposal_id, "agent_worker_1", vote=False)

# Check result
result = consensus.get_result(proposal_id)
if result["approved"]:
    print(f"Proposal approved: {result['votes_for']}/{result['total_votes']}")
```

**Configuration**:
```yaml
advanced_multi_agent:
  consensus:
    enabled: true
    quorum_percentage: 0.5
    approval_threshold: 0.6
    use_weighted_voting: true
    auto_resolve: true
    proposal_timeout_sec: 60
```

---

## 🧠 Stage 29: Long-term Memory Systems

### Features

#### 1. MemoryConsolidation - Sleep-Cycle Consolidation

**Purpose**: Consolidate episodic memories into long-term storage, simulating sleep cycles.

**Key Concepts**:
- **Importance Scoring**: Rank memories by recency, frequency, emotional significance
- **Forgetting Curve**: Gradually forget low-importance memories
- **Consolidation Cycles**: Periodic background processing

**Key Capabilities**:
```python
from core.memory.memory_consolidation import MemoryConsolidation

consolidation = MemoryConsolidation(storage_path)

# Run consolidation cycle
recent_episodes = episodic_memory.get_recent_episodes(100)
result = consolidation.run_consolidation_cycle(recent_episodes)

print(f"Consolidated: {result['consolidated']}")
print(f"Forgotten: {result['forgotten']}")
print(f"Total memories: {result['total_memories']}")

# Get important memories
important = consolidation.get_important_memories(limit=20)
```

**Configuration**:
```yaml
longterm_memory:
  consolidation:
    enabled: true
    interval_hours: 2
    importance_weights:
      recency: 0.3
      frequency: 0.25
      emotion: 0.25
      relevance: 0.2
    forgetting_enabled: true
    min_importance: 0.3
    max_memories: 5000
```

---

#### 2. SemanticMemory - Concept & Fact Extraction

**Purpose**: Build a semantic knowledge graph from experiences.

**Key Concepts**:
- **Concepts**: Abstract ideas extracted from experiences (e.g., "Python", "collaboration")
- **Facts**: Concrete statements (e.g., "Python is a programming language")
- **Relationships**: Connections between concepts (e.g., "Python" -> "used_for" -> "data_analysis")

**Key Capabilities**:
```python
from core.memory.semantic_memory import SemanticMemory

semantic = SemanticMemory(storage_path)

# Extract knowledge from episode
episode = {"event_type": "learning", "description": "Learned about async programming in Python"}
semantic.extract_knowledge_from_episode(episode)

# Add concept manually
semantic.add_concept(
    concept="async_programming",
    concept_type="technology",
    confidence=0.9,
    context="Python concurrency model"
)

# Add fact
semantic.add_fact(
    subject="async_programming",
    predicate="enables",
    object="concurrent_execution",
    confidence=0.85
)

# Search concepts
concepts = semantic.search_concepts(query="programming", concept_type="technology")

# Get facts about concept
facts = semantic.get_facts_about("async_programming")
```

**Configuration**:
```yaml
longterm_memory:
  semantic:
    enabled: true
    extract_concepts: true
    min_concept_confidence: 0.6
    max_concepts: 1000
    extract_facts: true
    max_facts: 2000
    build_relationships: true
    min_relationship_strength: 0.4
```

---

#### 3. MemoryRetrieval - Multi-Level Intelligent Search

**Purpose**: Efficiently search across episodic, semantic, and consolidated memories.

**Search Strategy**:
1. **Episodic**: Recent raw experiences
2. **Semantic**: Concepts and facts
3. **Consolidated**: Important long-term memories

**Key Capabilities**:
```python
from core.memory.memory_retrieval import MemoryRetrieval

retrieval = MemoryRetrieval(storage_path)

# Search across all levels
results = retrieval.search(
    query="Python async programming",
    max_results=10,
    min_relevance=0.5
)

for result in results:
    print(f"[{result['source']}] Score: {result['score']:.2f}")
    print(f"Content: {result['content'][:100]}...")

# Context-aware search
results = retrieval.search_with_context(
    query="What have I learned about Python?",
    context={"time_range": "last_week", "event_type": "learning"},
    max_results=5
)
```

**Configuration**:
```yaml
longterm_memory:
  retrieval:
    enabled: true
    search_levels:
      - "episodic"
      - "semantic"
      - "consolidated"
    cache_enabled: true
    cache_size: 100
    cache_ttl_sec: 300
    ranking_weights:
      relevance: 0.4
      recency: 0.3
      importance: 0.3
```

---

## 🧬 Stage 30: Self-Evolution Framework

### Features

#### Evolution Modes

**Supervised** (Default):
- All changes require human approval
- Full audit trail
- Maximum safety

**Semi-Autonomous**:
- Minor changes (optimizations, bug fixes) auto-approved if confidence > threshold
- Major changes require approval
- Balanced safety/autonomy

**Autonomous**:
- System evolves independently
- All changes applied automatically
- Rollback on failure
- Use with caution!

---

#### 1. SelfEvolutionManager - Evolution Orchestration

**Purpose**: Manage the self-modification lifecycle.

**Key Capabilities**:
```python
from core.self_evolution.self_evolution_manager import (
    SelfEvolutionManager, 
    EvolutionMode, 
    ChangeType
)

manager = SelfEvolutionManager(
    storage_dir=Path("memory"),
    mode=EvolutionMode.SUPERVISED
)

# Propose a change
proposal_id = manager.propose_change(
    change_type=ChangeType.OPTIMIZATION,
    target_module="core.memory.episodic",
    description="Optimize episode retrieval with indexing",
    generated_code="def get_episodes_indexed(...):",
    justification="50% faster query performance",
    test_results={"performance_gain": 0.5, "tests_passed": True}
)

# Human reviews and approves
result = manager.approve_change(proposal_id)
if result["success"]:
    print(f"Change applied: {result['message']}")

# Or reject
manager.reject_change(proposal_id, reason="Need more testing")

# Rollback if needed
manager.rollback_change(proposal_id)
```

**Configuration**:
```yaml
self_evolution:
  enabled: true
  mode: "supervised"  # supervised | semi_autonomous | autonomous
  
  manager:
    suggest_changes_every_ticks: 100
    max_pending_proposals: 10
    allowed_change_types:
      - "optimization"
      - "bug_fix"
      - "feature_addition"
      - "refactoring"
    
    safety_checks:
      syntax_validation: true
      performance_test: true
      rollback_on_error: true
    
    approval:
      timeout_hours: 24
      require_justification: true
      min_confidence: 0.7
```

---

#### 2. CodeGenerator - LLM-Powered Code Generation

**Purpose**: Generate Python code using LLM.

**Key Capabilities**:
```python
from core.self_evolution.code_generator import CodeGenerator

generator = CodeGenerator(ollama_client)

# Generate function
code = generator.generate_function(
    function_name="calculate_memory_importance",
    purpose="Score memory importance based on multiple factors",
    inputs=[
        {"name": "memory", "type": "dict"},
        {"name": "weights", "type": "dict"}
    ],
    output_type="float",
    constraints=[
        "Return value between 0 and 1",
        "Consider recency, frequency, emotion"
    ]
)

print(code)
# Output: Full Python function with docstring

# Validate syntax
is_valid = generator.validate_syntax(code)

# Get optimization hints
hints = generator.suggest_optimizations(code)
```

**Configuration**:
```yaml
self_evolution:
  code_generator:
    enabled: true
    model: "llama3.2:3b"
    temperature: 0.7
    max_tokens: 2000
    enforce_style: true
    run_linter: false
    optimize_for:
      - "readability"
      - "performance"
      - "maintainability"
```

---

#### 3. EvolutionSandbox - Safe Testing Environment

**Purpose**: Test generated code in isolation before applying to production.

**Key Capabilities**:
```python
from core.self_evolution.evolution_sandbox import EvolutionSandbox

sandbox = EvolutionSandbox(sandbox_dir=Path("sandbox/evolution"))

# Test generated code
test_result = sandbox.test_code(
    code=generated_code,
    test_cases=[
        {"input": {"memory": {...}, "weights": {...}}, "expected_output": 0.75},
        {"input": {"memory": {...}, "weights": {...}}, "expected_output": 0.45}
    ],
    timeout_sec=10
)

if test_result["all_passed"]:
    print(f"All tests passed! Success rate: {test_result['success_rate']:.1%}")

# Benchmark performance
benchmark = sandbox.benchmark_code(
    code=generated_code,
    iterations=100
)

print(f"Avg execution time: {benchmark['avg_time_ms']:.2f}ms")
print(f"Memory usage: {benchmark['memory_mb']:.1f}MB")
```

**Configuration**:
```yaml
self_evolution:
  sandbox:
    enabled: true
    isolated_execution: true
    sandbox_dir: "sandbox/evolution"
    run_tests: true
    test_timeout_sec: 30
    benchmark_enabled: true
    benchmark_iterations: 10
    max_cpu_percent: 50
    max_memory_mb: 512
    max_execution_time_sec: 60
```

---

## 🔌 API Endpoints

### Multi-Agent (Stage 28)

#### `GET /multi-agent/roles`
Get agent role information

```bash
curl http://localhost:8766/multi-agent/roles
```

Response:
```json
{
  "roles": [
    {
      "agent_id": "agent_123",
      "role": "specialist",
      "capabilities": ["python", "data_analysis"],
      "performance_score": 0.87
    }
  ],
  "stats": {
    "total_roles": 3,
    "role_assignments": 5
  }
}
```

#### `GET /multi-agent/tasks`
Get active and completed tasks

```bash
curl http://localhost:8766/multi-agent/tasks
```

#### `GET /multi-agent/proposals`
Get active voting proposals

```bash
curl http://localhost:8766/multi-agent/proposals
```

#### `POST /multi-agent/vote`
Cast vote on proposal

```bash
curl -X POST http://localhost:8766/multi-agent/vote \
  -H "Content-Type: application/json" \
  -d '{
    "proposal_id": "prop_123",
    "agent_id": "agent_456",
    "vote": true
  }'
```

---

### Memory (Stage 29)

#### `GET /memory/consolidated`
Get consolidated long-term memories

```bash
curl "http://localhost:8766/memory/consolidated?limit=20"
```

#### `GET /memory/semantic`
Get semantic memory statistics

```bash
curl http://localhost:8766/memory/semantic
```

#### `GET /memory/concepts`
Search concepts

```bash
curl "http://localhost:8766/memory/concepts?q=programming&type=technology"
```

#### `GET /memory/facts`
Search facts

```bash
curl "http://localhost:8766/memory/facts?q=python"
```

#### `GET /memory/retrieval-stats`
Get memory retrieval statistics

```bash
curl http://localhost:8766/memory/retrieval-stats
```

---

### Evolution (Stage 30)

#### `GET /evolution/stats`
Get self-evolution statistics

```bash
curl http://localhost:8766/evolution/stats
```

Response:
```json
{
  "stats": {
    "mode": "supervised",
    "approved_changes": 5,
    "pending_approvals": 2,
    "rejected_changes": 1,
    "rollbacks": 0,
    "total_proposals": 8
  }
}
```

#### `GET /evolution/proposals`
Get pending evolution proposals

```bash
curl http://localhost:8766/evolution/proposals
```

#### `GET /evolution/history`
Get evolution change history

```bash
curl "http://localhost:8766/evolution/history?limit=20"
```

#### `POST /evolution/approve`
Approve pending change

```bash
curl -X POST http://localhost:8766/evolution/approve \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": "prop_123"}'
```

#### `POST /evolution/reject`
Reject pending change

```bash
curl -X POST http://localhost:8766/evolution/reject \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": "prop_123", "reason": "Needs more testing"}'
```

---

## 🚀 Quick Start

### 1. Enable Stage 28-30 Features

Edit `config.yaml`:

```yaml
# Stage 28: Advanced Multi-Agent
advanced_multi_agent:
  enabled: true  # ← Enable this

# Stage 29: Long-term Memory
longterm_memory:
  enabled: true  # ← Already enabled

# Stage 30: Self-Evolution
self_evolution:
  enabled: true
  mode: "supervised"  # ← Start with supervised mode
```

### 2. Start Digital Being

```bash
python main.py
```

### 3. Check Logs

You should see:

```
⚙️  TaskDelegation ready. active=0 completed=0
🗳️  ConsensusBuilder ready. proposals=0 approved=0
🎭 AgentRoles ready. total_roles=3 assignments=0
🧠 MemoryConsolidation ready. total_memories=0 forgotten=0
📚 SemanticMemory ready. concepts=0 facts=0
🔍 MemoryRetrieval ready. queries=0 cache_hit_rate=0.00%
🧬 SelfEvolution ready. mode=supervised approved=0 pending=0
```

### 4. Test API Endpoints

```bash
# Check multi-agent status
curl http://localhost:8766/multi-agent/roles

# Check memory stats
curl http://localhost:8766/memory/semantic

# Check evolution stats
curl http://localhost:8766/evolution/stats
```

---

## 📈 Architecture Overview

```
┌──────────────────────────────────────────┐
│  Digital Being - Full Cognitive Architecture  │
└──────────────────────────────────────────┘

         ┌──────────────────────────┐
         │  Stage 30: Self-Evolution  │
         │  🧬 Code Generation      │
         │  🧪 Sandbox Testing       │
         └──────────────────────────┘
                    │
         ┌──────────────────────────┐
         │  Stage 29: Long-term Memory │
         │  🧠 Consolidation         │
         │  📚 Semantic Knowledge    │
         │  🔍 Intelligent Retrieval │
         └──────────────────────────┘
                    │
         ┌──────────────────────────┐
         │  Stage 28: Multi-Agent     │
         │  🎭 Agent Roles          │
         │  📦 Task Delegation       │
         │  🗳️ Consensus Building   │
         └──────────────────────────┘
                    │
         ┌──────────────────────────┐
         │  Stages 1-27: Core Systems │
         │  🧠 Episodic Memory       │
         │  🎯 Goal Persistence      │
         │  📚 Skill Library         │
         │  🚀 Proactive Behavior    │
         │  🔬 Meta-Learning         │
         │  ... and more               │
         └──────────────────────────┘
```

---

## 🔒 Safety Guidelines

### Self-Evolution Safety

1. **Start with Supervised Mode**
   - All changes require human approval
   - Review proposals carefully
   - Test in sandbox first

2. **Monitor Change History**
   - Check `/evolution/history` regularly
   - Review rejected changes
   - Look for patterns in failures

3. **Use Rollback When Needed**
   - Keep backups enabled
   - Test rollback procedure
   - Document known issues

4. **Gradual Autonomy**
   - Start: `supervised`
   - After testing: `semi_autonomous`
   - Only if confident: `autonomous`

### Multi-Agent Safety

1. **Role Assignments**
   - Verify agent capabilities
   - Monitor role performance
   - Reassign if needed

2. **Task Delegation**
   - Set appropriate timeouts
   - Monitor task completion rates
   - Review failed tasks

3. **Consensus Decisions**
   - Set reasonable quorum
   - Use weighted voting
   - Audit important decisions

---

## 📊 Performance Considerations

### Memory Systems

- **Consolidation**: Runs every 2 hours by default
- **Semantic Extraction**: CPU-intensive, adjust intervals if needed
- **Retrieval Cache**: Keep enabled for performance

### Self-Evolution

- **Code Generation**: LLM calls are slow, limit frequency
- **Sandbox Testing**: Resource-limited for safety
- **Change History**: Prune old entries periodically

### Multi-Agent

- **Network Communication**: Keep agents on same network
- **Message Polling**: 2-second interval is reasonable
- **Consensus Timeout**: Adjust based on agent count

---

## 🐛 Troubleshooting

### "Evolution proposals not generating"

- Check `self_evolution.enabled = true`
- Verify `suggest_changes_every_ticks` interval
- Check logs for LLM errors

### "Memory consolidation not running"

- Check `longterm_memory.consolidation.enabled = true`
- Verify interval hasn't passed yet
- Check episodic memory has episodes

### "Multi-agent votes not resolving"

- Check quorum percentage
- Verify agents are online
- Check proposal timeout

### "Sandbox tests failing"

- Review resource limits
- Check timeout settings
- Verify test cases are correct

---

## 📚 Further Reading

- [Main README](README.md) - Project overview
- [Stage 1-27 Documentation](ARCHITECTURE.md) - Core systems
- [API Reference](API.md) - Complete API docs
- [Development Guide](DEVELOPMENT.md) - Contributing

---

## ❓ Support

If you encounter issues:

1. Check the logs in `logs/digital_being.log`
2. Review configuration in `config.yaml`
3. Test API endpoints manually
4. Open an issue on GitHub with:
   - Error logs
   - Configuration
   - Steps to reproduce

---

**🎉 Congratulations! You now have a fully operational cognitive architecture with advanced multi-agent coordination, long-term memory, and self-evolution capabilities!**
