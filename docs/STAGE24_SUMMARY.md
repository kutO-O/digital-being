# Stage 24: Meta-Cognition Layer

## 🧠 Concept

The system now **thinks about its own thinking** — it analyzes the quality of its decisions, discovers patterns in its reasoning, identifies cognitive biases and blind spots, and understands when it's confused or confident.

This is **meta-cognition**: not just reflection ("what happened?") but a deeper level ("why did I think that way? how good is my reasoning? what do I consistently miss?").

---

## 🛠️ Implementation

### New Component: `core/meta_cognition.py`

**State file:** `memory/meta_cognition.json`

```json
{
  "insights": [
    {
      "id": "uuid",
      "insight_type": "blind_spot",
      "description": "я часто игнорирую файлы .log",
      "evidence": ["episode_id1", "episode_id2"],
      "discovered_at": "timestamp",
      "confidence": 0.7,
      "impact": "medium"
    }
  ],
  "decision_quality_log": [
    {
      "tick": 123,
      "decision": "action_type=write",
      "reasoning_quality": 0.75,
      "outcome_match": true,
      "confusion_level": 0.2
    }
  ],
  "cognitive_metrics": {
    "avg_decision_quality": 0.75,
    "confusion_episodes": 3,
    "high_confidence_correct": 12,
    "high_confidence_wrong": 2
  }
}
```

### Key Methods

#### `analyze_decision_quality(episodes, ollama) -> dict`
Analyzes quality of recent thinking:
- `reasoning_quality` (0.0-1.0): How logical and coherent are decisions?
- `confusion_level` (0.0-1.0): How uncertain or confused is the system?
- `pattern_recognition` (0.0-1.0): Does it notice patterns?

**Prompt:**
> Проанализируй последние решения системы. Оцени reasoning_quality, confusion_level, pattern_recognition.

#### `detect_cognitive_patterns(episodes, beliefs, ollama) -> list[dict]`
Finds meta-insights about thinking:
- `cognitive_bias`: Systematic reasoning error
- `blind_spot`: What the system consistently misses
- `strength`: What it's good at
- `weakness`: Where it's consistently weak
- `pattern`: Recurring behavior in thinking

**Prompt:**
> Ты — Digital Being. Проанализируй СВОЁ мышление. Найди 1-2 мета-инсайта о своём мышлении.

#### `add_insight(type, description, evidence, confidence, impact)`
Adds insight with duplicate detection (>70% word overlap = duplicate).

#### `calculate_calibration() -> float`
Measures how well the system estimates its own confidence:
- High confidence + correct = good calibration
- High confidence + wrong = poor calibration

Formula: `high_confidence_correct / (high_confidence_correct + high_confidence_wrong)`

#### `get_current_state() -> dict`
Returns:
- `reasoning_quality`: Average from last 10 decisions
- `confusion_level`: Average from last 10 decisions
- `known_blind_spots`: List of blind spots (sorted by confidence)
- `known_strengths`: List of strengths (sorted by confidence)
- `calibration_score`: How well it judges its own certainty

#### `to_prompt_context(limit=2) -> str`
Formats for LLM:
```
Метакогнитивное состояние:
- Качество рассуждений: 0.75
- Уровень замешательства: 0.2
- Калибровка: 0.8 (адекватно оцениваю свою уверенность)

Известные слабости:
- [blind_spot] я часто игнорирую файлы .log (conf=0.7)

Сильные стороны:
- [strength] хорошо замечаю аномалии (conf=0.8)
```

---

## 🔗 Integration

### HeavyTick Integration

Added `_step_meta_cognition(n)` that runs every 50 ticks (~4 hours):
1. Analyzes decision quality from last 20 episodes
2. Detects cognitive patterns using episodes + beliefs
3. Stores insights (max 2 per cycle)
4. Logs results

**Monologue & Social Context:**
Meta-cognitive state is included in LLM prompts via `to_prompt_context()`.

### IntrospectionAPI

New endpoint: `GET /meta-cognition`
```json
{
  "current_state": {...},
  "recent_insights": [...],
  "decision_log": [...],
  "stats": {...}
}
```

### Configuration

`config.yaml`:
```yaml
meta_cognition:
  enabled: true
  analyze_every_ticks: 50  # Run analysis every 50 ticks
  max_insights: 30          # Maximum stored insights
  min_confidence: 0.4       # Minimum confidence to accept
```

---

## 📊 Key Features

### 1. **Self-Awareness of Thinking Quality**
The system knows:
- "My reasoning quality is 0.75 — pretty good"
- "I'm confused (confusion_level=0.6) — need to be cautious"

### 2. **Discovery of Blind Spots**
Example insights:
- "I rarely pay attention to configuration files"
- "I tend to ignore .log files when analyzing"
- "I'm weak at detecting time-based patterns"

### 3. **Recognition of Strengths**
- "I'm good at noticing file system anomalies"
- "I excel at detecting contradictions"

### 4. **Calibration Tracking**
Knows if it's:
- **Well-calibrated**: Confident when right, uncertain when wrong
- **Over-confident**: Often confident but wrong
- **Under-confident**: Often uncertain but right

### 5. **Duplicate Prevention**
Insights are deduplicated using word overlap (>70% match = duplicate).

### 6. **Impact-Based Prioritization**
Insights with `impact="high"` are prioritized:
- Score = `confidence * impact_score`
- `impact_score`: {"low": 0.5, "medium": 1.0, "high": 1.5}

---

## 📝 Example Usage

### Scenario 1: Discovering a Blind Spot

**Tick 50:**
```
[MetaCognition] analyzing decision quality...
reasoning=0.72, confusion=0.25
[MetaCognition] 1 insight(s) discovered:
  - [blind_spot] "я почти не обращаю внимание на файлы конфигурации" (confidence=0.65)
```

**Next monologue (tick 51):**
```
Метакогнитивное состояние:
- Качество рассуждений: 0.72
- Уровень замешательства: 0.25

Известные слабости:
- [blind_spot] я почти не обращаю внимание на файлы конфигурации (conf=0.65)
```

System can now **compensate** by explicitly checking config files.

---

### Scenario 2: Recognizing Confusion

**Tick 100:**
```
[MetaCognition] reasoning=0.45, confusion=0.75
```

System realizes: "I'm very confused right now — better observe and reflect instead of acting."

---

### Scenario 3: Calibration Improvement

**Initial state:**
- `high_confidence_correct`: 5
- `high_confidence_wrong`: 5
- `calibration_score`: 0.5 (poor)

**After 500 ticks:**
- `high_confidence_correct`: 20
- `high_confidence_wrong`: 3
- `calibration_score`: 0.87 (good!)

System learned to better judge its own certainty.

---

## 🔍 API Examples

### Get Meta-Cognitive State
```bash
curl http://127.0.0.1:8765/meta-cognition
```

Response:
```json
{
  "current_state": {
    "reasoning_quality": 0.72,
    "confusion_level": 0.25,
    "known_blind_spots": [
      {
        "insight_type": "blind_spot",
        "description": "я почти не обращаю внимание на файлы конфигурации",
        "confidence": 0.65,
        "impact": "medium"
      }
    ],
    "known_strengths": [
      {
        "insight_type": "strength",
        "description": "хорошо замечаю аномалии в файловой системе",
        "confidence": 0.8,
        "impact": "high"
      }
    ],
    "calibration_score": 0.75
  },
  "recent_insights": [...],
  "decision_log": [...],
  "stats": {
    "total_insights": 5,
    "total_decisions_logged": 23,
    "calibration_score": 0.75,
    "insights_by_type": {
      "blind_spot": 2,
      "strength": 2,
      "weakness": 1,
      "cognitive_bias": 0,
      "pattern": 0
    }
  }
}
```

---

## 🎯 Why This Matters

### Before Stage 24:
- System reflects on **what happened**
- No awareness of **thinking quality**
- No understanding of **own limitations**

### After Stage 24:
- System analyzes **how it thinks**
- Aware of **reasoning quality and confusion**
- Discovers **blind spots and strengths**
- Tracks **confidence calibration**
- Can **compensate for known weaknesses**

---

## 🛠️ Technical Notes

1. **Atomic writes**: State saved with temp file + replace
2. **Max insights**: 30 (pruned by score = confidence × impact)
3. **Max decision log**: 100 entries
4. **Duplicate detection**: Word overlap >70%
5. **Analysis frequency**: Every 50 ticks (~4 hours with 60s interval)
6. **LLM dependency**: Uses `OllamaClient` for analysis
7. **No external dependencies**: System analyzes itself

---

## 🔮 Next Steps

Stage 24 completes the **meta-cognitive layer**. The system can now:
- ✅ Think about its thinking
- ✅ Discover its own blind spots
- ✅ Track reasoning quality
- ✅ Calibrate confidence

**Ready for Stage 25** (final stage): Integration, testing, and polish.
