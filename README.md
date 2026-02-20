# Digital Being

Autonomous AI agent system that lives on a computer 24/7, sets its own goals, makes decisions, and evolves over time.

## Project Structure

```
digital-being/
├── main.py              # Entry point
├── config.yaml          # System configuration
├── seed.yaml            # First-run seed values
├── requirements.txt     # Python dependencies
├── core/                # Core modules (Phase 2+)
│   └── __init__.py
├── memory/              # Persistent memory (auto-created at runtime)
│   ├── episodic.db      # SQLite episodic memory
│   └── semantic_lance/  # LanceDB semantic memory
└── logs/                # Log files (auto-created at runtime)
```

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

On **first run**, the system bootstraps its identity and initial state from `seed.yaml`  
and writes `memory/state.json`. Subsequent runs resume from the saved state.

Stop cleanly with `Ctrl+C` (SIGINT).

## Phase Roadmap

- [x] **Phase 1** — File structure, config.yaml, seed.yaml, main.py
- [ ] **Phase 2** — Tick engine + score system
- [ ] **Phase 3** — Memory system (episodic SQLite + semantic LanceDB)
- [ ] **Phase 4** — Ollama LLM integration (strategy + embed)
- [ ] **Phase 5** — Goal system + autonomous decision making
- [ ] **Phase 6** — Self-evolution and reflection mechanisms
