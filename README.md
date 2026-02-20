# Digital Being

Autonomous AI agent system that lives on a computer 24/7, sets its own goals, makes decisions, and evolves over time.

## Current Status: Stage 21 Complete

**Latest addition:** ShellExecutor - safe shell command execution for active environment exploration.

## Features

✅ **Episodic & Vector Memory** - SQLite + numpy embeddings  
✅ **Value Engine** - Dynamic value scores, mode adaptation, drift detection  
✅ **Strategy Engine** - Three planning horizons (daily, weekly, long-term)  
✅ **World Model** - File monitoring, anomaly detection  
✅ **Self Model** - Identity, principles, drift detection  
✅ **Milestones** - Achievement tracking  
✅ **Dream Mode** - Background consolidation & insight generation  
✅ **Introspection API** - HTTP REST API for system state inspection  
✅ **Emotion Engine** - Dynamic emotional state with tone modifiers  
✅ **Reflection Engine** - Periodic self-analysis and principle formation  
✅ **Narrative Engine** - Diary generation with markdown formatting  
✅ **Goal Persistence** - Resume interrupted goals after restart  
✅ **Attention System** - Focus-based episode filtering  
✅ **Curiosity Engine** - Question generation and answer seeking  
✅ **Self-Modification** - Autonomous config changes with validation  
✅ **Belief System** - Form, validate, and track beliefs about the world  
✅ **Contradiction Resolver** - Detect and resolve contradictions between beliefs/principles  
✅ **Shell Executor** - Safe, whitelisted shell command execution for environment exploration  

## Project Structure

```
digital-being/
├── main.py              # Entry point
├── config.yaml          # System configuration
├── seed.yaml            # First-run seed values
├── requirements.txt     # Python dependencies
├── core/                # Core modules
│   ├── event_bus.py
│   ├── file_monitor.py
│   ├── light_tick.py
│   ├── heavy_tick.py
│   ├── world_model.py
│   ├── value_engine.py
│   ├── self_model.py
│   ├── milestones.py
│   ├── ollama_client.py
│   ├── strategy_engine.py
│   ├── dream_mode.py
│   ├── introspection_api.py
│   ├── emotion_engine.py
│   ├── reflection_engine.py
│   ├── narrative_engine.py
│   ├── goal_persistence.py
│   ├── attention_system.py
│   ├── curiosity_engine.py
│   ├── self_modification.py
│   ├── belief_system.py
│   ├── contradiction_resolver.py
│   ├── shell_executor.py     # Stage 21: Safe shell execution
│   └── memory/
│       ├── episodic.py
│       └── vector_memory.py
├── memory/              # Persistent memory (auto-created)
│   ├── episodic.db
│   ├── vector_memory.db
│   ├── beliefs.json
│   ├── contradictions.json
│   └── shell_stats.json
├── logs/                # Log files (auto-created)
├── sandbox/             # Write output (auto-created)
└── milestones/          # Achievement tracking (auto-created)
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally with models:
  - `llama3.2:3b` (strategy/chat)
  - `nomic-embed-text` (embeddings)

### Installation

```bash
pip install -r requirements.txt
python main.py
```

On **first run**, the system bootstraps its identity and initial state from `seed.yaml`  
and writes `memory/state.json`. Subsequent runs resume from the saved state.

Stop cleanly with `Ctrl+C` (SIGINT).

## Introspection API

When running, access the HTTP API at `http://127.0.0.1:8765`:

- `GET /status` - Uptime, tick count, mode, current goal
- `GET /memory` - Episode and vector counts, recent episodes
- `GET /values` - Value scores, mode, conflicts
- `GET /strategy` - Three planning horizons
- `GET /milestones` - Achieved and pending milestones
- `GET /dream` - Dream mode state and next-run ETA
- `GET /episodes?limit=20&event_type=...` - Filtered episode search
- `GET /search?q=text&top_k=5` - Semantic search via vector memory
- `GET /emotions` - Current emotional state, dominant emotion
- `GET /reflection` - Last 5 reflections + total count
- `GET /diary?limit=5` - Last N diary entries
- `GET /diary/raw` - Full diary.md as text
- `GET /curiosity` - Open questions + stats
- `GET /modifications` - Config modification history
- `GET /beliefs` - Active and strong beliefs + stats
- `GET /contradictions` - Pending and resolved contradictions
- `GET /shell/stats` - Shell execution statistics
- `POST /shell/execute` - Execute safe shell command (JSON: `{"command": "ls -la"}`)

## Shell Executor (Stage 21)

Safe, whitelisted shell command execution for active environment exploration.

**Allowed commands (read-only):**
- `ls`, `cat`, `head`, `tail`, `wc`, `du`, `find`, `grep`
- `date`, `pwd`, `whoami`, `echo`

**Security features:**
- Strict whitelist validation
- Path traversal protection (restricted to `allowed_dir`)
- No pipes, redirects, or command chaining (`|`, `>`, `<`, `&`, `;`, `&&`, `||`)
- Timeout enforcement per command
- Output truncation (configurable)
- All commands logged to episodic memory

**Configuration (`config.yaml`):**
```yaml
shell:
  enabled: true
  allowed_dir: "."  # Relative to project root
  max_output_chars: 2000
```

**Usage by system:**
The system can autonomously choose `action_type: "shell"` during goal selection:
```json
{
  "goal": "проверить есть ли файл config.yaml",
  "action_type": "shell",
  "shell_command": "ls config.yaml"
}
```

## Architecture

### Tick System

- **Light Tick** (5s): File monitoring, quick state checks
- **Heavy Tick** (60s): LLM-driven decision making, 8-step process:
  1. Internal Monologue (внутренний монолог)
  2. Goal Selection (via StrategyEngine or legacy mode)
  3. Action Execution (observe | analyze | write | reflect | shell)
  4. After-action (emotions, reflection, narrative triggers)
  5. Curiosity (generate questions / seek answers)
  6. Self-Modification (suggest and apply config changes)
  7. Belief System (form and validate beliefs)
  8. Contradiction Resolver (detect and resolve contradictions)

### Value Engine

Dynamic value scores with drift detection and mode adaptation:
- **Modes**: curious, normal, defensive
- **Conflicts**: exploration_vs_stability, action_vs_caution
- **Drift detection**: weekly snapshots, threshold alerts

### Strategy Engine

Three planning horizons:
- **Daily direction** (ежедневное направление) - updated every 24h
- **Weekly direction** (недельное направление) - updated every 7 days
- **Long-term vector** (долгосрочный вектор) - updated every 30 days

### Memory System

- **Episodic Memory**: SQLite database of events with metadata
- **Vector Memory**: Numpy embeddings for semantic search
- **Semantic Context**: Used for goal selection to inform decisions

### Dream Mode

Background consolidation process (runs every 6h by default):
- Analyzes recent episodes with LLM
- Generates insights
- Updates long-term strategic vector
- Forms new principles

### Belief System (Stage 19)

- Forms beliefs from observations (patterns, cause-effect, world state)
- Validates beliefs against new evidence
- Tracks confidence scores (0.0-1.0)
- Status transitions: active → strong (confidence ≥ 0.85) or rejected (confidence < 0.2)
- Max 100 beliefs, prunes oldest rejected when full

### Contradiction Resolver (Stage 20)

- Detects contradictions between beliefs and principles
- Three-step resolution dialogue with LLM:
  1. **Deliberation**: List relevant facts
  2. **Synthesis**: Integrate perspectives
  3. **Verdict**: Choose A, choose B, synthesis, or both valid
- Applies verdict: updates confidence scores or creates new beliefs/principles
- Automatic detection every 30 ticks, resolution every 15 ticks

## Development Stages (Completed)

1. ✅ EventBus
2. ✅ FileMonitor
3. ✅ LightTick
4. ✅ EpisodicMemory
5. ✅ VectorMemory
6. ✅ WorldModel
7. ✅ ValueEngine
8. ✅ SelfModel
9. ✅ Milestones
10. ✅ OllamaClient
11. ✅ HeavyTick
12. ✅ StrategyEngine
13. ✅ DreamMode
14. ✅ IntrospectionAPI
15. ✅ EmotionEngine
16. ✅ ReflectionEngine
17. ✅ NarrativeEngine
18. ✅ GoalPersistence
19. ✅ AttentionSystem
20. ✅ CuriosityEngine
21. ✅ SelfModificationEngine
22. ✅ BeliefSystem
23. ✅ ContradictionResolver
24. ✅ **ShellExecutor** (Stage 21)

## License

MIT
