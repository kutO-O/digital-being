# Stage 24: HeavyTick Integration Instructions

## Why Manual?

`core/heavy_tick.py` is too large (~15000+ lines) for GitHub API to return fully. Below are **exact changes** needed.

---

## Changes Required

### 1. Add Import (Line ~30, after other imports)

**Location:** Top of file, in imports section

**Add:**
```python
from core.meta_cognition import MetaCognition
```

**Full imports block should look like:**
```python
from core.attention_system import AttentionSystem
from core.belief_system import BeliefSystem
from core.contradiction_resolver import ContradictionResolver
from core.curiosity_engine import CuriosityEngine
from core.emotion_engine import EmotionEngine
from core.goal_persistence import GoalPersistence
from core.memory.episodic import EpisodicMemory
from core.memory.vector_memory import VectorMemory
from core.meta_cognition import MetaCognition  # ← ADD THIS
from core.milestones import Milestones
# ... rest of imports
```

---

### 2. Update `__init__` Signature (Line ~60-90)

**Location:** Inside `class HeavyTick`, `__init__` method parameters

**Add parameter:**
```python
meta_cognition: "MetaCognition | None" = None,
```

**And store it:**
```python
self._meta_cog = meta_cognition  # Stage 24
```

**Full `__init__` signature should include:**
```python
def __init__(
    self,
    cfg:          dict,
    ollama:       "OllamaClient",
    world:        "WorldModel",
    # ... many other parameters ...
    time_perception:   "TimePerception | None"   = None,
    social_layer:      "SocialLayer | None"      = None,  # Stage 23
    meta_cognition:    "MetaCognition | None"    = None,  # ← ADD THIS
) -> None:
```

**And in the body:**
```python
self._time_perc    = time_perception
self._social       = social_layer  # Stage 23
self._meta_cog     = meta_cognition  # ← ADD THIS
```

---

### 3. Add `_step_meta_cognition()` Method

**Location:** After `_step_social_interaction()` method (around line 350)

**Add this complete method:**

```python
# ────────────────────────────────────────────────────────────────
# Stage 24: Meta-Cognition
# ────────────────────────────────────────────────────────────────
async def _step_meta_cognition(self, n: int) -> None:
    """Stage 24: Analyze decision quality and discover cognitive patterns."""
    if self._meta_cog is None:
        return
    
    loop = asyncio.get_event_loop()
    
    # Periodic analysis
    if self._meta_cog.should_analyze(n):
        log.info(f"[HeavyTick #{n}] MetaCognition: analyzing decision quality.")
        try:
            episodes = self._mem.get_recent_episodes(20)
            quality = await loop.run_in_executor(
                None, lambda: self._meta_cog.analyze_decision_quality(episodes, self._ollama)
            )
            
            if quality:
                log.info(
                    f"[HeavyTick #{n}] MetaCognition: "
                    f"reasoning={quality.get('reasoning_quality', 0):.2f}, "
                    f"confusion={quality.get('confusion_level', 0):.2f}"
                )
                
                # Detect cognitive patterns
                beliefs = self._beliefs.get_beliefs() if self._beliefs else []
                insights = await loop.run_in_executor(
                    None,
                    lambda: self._meta_cog.detect_cognitive_patterns(
                        episodes, beliefs, self._ollama
                    )
                )
                
                # Add insights (signature: insight_type, description, confidence, impact)
                for ins in insights[:2]:
                    self._meta_cog.add_insight(
                        ins["insight_type"],
                        ins["description"],
                        ins.get("confidence", 0.5),
                        ins.get("impact", "medium")
                    )
                
                if insights:
                    log.info(f"[HeavyTick #{n}] MetaCognition: {len(insights)} insight(s) discovered.")
        
        except Exception as e:
            log.error(f"[HeavyTick #{n}] MetaCognition error: {e}")
```

**Note:** `add_insight()` signature changed — removed unused `evidence` parameter.

---

### 4. Call in `_run_tick()` Method

**Location:** Inside `async def _run_tick(self, n: int)`, after `await self._step_social_interaction(n)`

**Find this line:**
```python
await self._step_social_interaction(n)  # Stage 23
```

**Add after it:**
```python
await self._step_meta_cognition(n)  # Stage 24
```

**Should look like:**
```python
await self._step_contradiction_resolver(n)
await self._step_time_perception(n)
await self._step_social_interaction(n)  # Stage 23
await self._step_meta_cognition(n)  # ← ADD THIS
```

---

### 5. Update `_build_social_context()` Method

**Location:** Inside `def _build_social_context(self) -> str:` method

**Find the end of the method (before `return` statement):**
```python
if self._time_perc:
    parts.append(self._time_perc.to_prompt_context(2))

return "\n".join(parts)
```

**Change to:**
```python
if self._time_perc:
    parts.append(self._time_perc.to_prompt_context(2))

if self._meta_cog:  # ← ADD THIS
    parts.append(self._meta_cog.to_prompt_context(2))

return "\n".join(parts)
```

---

### 6. Update `_step_monologue()` Method

**Location:** Inside `async def _step_monologue(self, n: int)` method, where context is built

**Find the context building section:**
```python
if self._time_perc:
    parts.append(self._time_perc.to_prompt_context(2))

context = "\n".join(parts)
```

**Change to:**
```python
if self._time_perc:
    parts.append(self._time_perc.to_prompt_context(2))

if self._meta_cog:  # ← ADD THIS
    parts.append(self._meta_cog.to_prompt_context(2))

context = "\n".join(parts)
```

---

## Summary of Changes

1. ✅ Import `MetaCognition`
2. ✅ Add `meta_cognition` parameter to `__init__`
3. ✅ Store as `self._meta_cog`
4. ✅ Add `_step_meta_cognition()` method
5. ✅ Call it in `_run_tick()`
6. ✅ Add context to `_build_social_context()`
7. ✅ Add context to `_step_monologue()`

---

## Key Fix (Feb 21, 2026)

✅ **Fixed calibration tracking:**
- `log_decision()` now updates `high_confidence_correct` and `high_confidence_wrong`
- Threshold: `reasoning_quality > 0.75` = high confidence
- Calibration will now accurately reflect system's confidence estimation

✅ **Removed unused `evidence` parameter:**
- `add_insight()` signature: `(insight_type, description, confidence, impact)`
- Simpler API, no unused tracking

---

## Testing

After making changes:

```bash
python main.py
```

**Expected output:**
```
MetaCognition ready. insights=0 decisions_logged=0 calibration=0.50
```

**After 50 ticks (~1 hour):**
```
[HeavyTick #50] MetaCognition: analyzing decision quality.
[HeavyTick #50] MetaCognition: reasoning=0.72, confusion=0.25
[HeavyTick #50] MetaCognition: 1 insight(s) discovered.
```

**Calibration will evolve:**
- Initial: `0.50` (no data)
- After decisions: `0.65 - 0.85` (good calibration)
- Or: `0.3 - 0.5` (overconfident, needs adjustment)

**API test:**
```bash
curl http://127.0.0.1:8765/meta-cognition | jq
```

---

## Alternative: Use Script

If you prefer, create `apply_stage24.py` in project root:

```python
import re
from pathlib import Path

file_path = Path("core/heavy_tick.py")
content = file_path.read_text(encoding="utf-8")

# 1. Add import
if "from core.meta_cognition import MetaCognition" not in content:
    content = content.replace(
        "from core.memory.vector_memory import VectorMemory",
        "from core.memory.vector_memory import VectorMemory\nfrom core.meta_cognition import MetaCognition  # Stage 24"
    )
    print("✅ Added MetaCognition import")

# 2. Add parameter (simplified - check manually)
print("⚠️  Manually add 'meta_cognition' parameter to __init__")

# 3. Add method after _step_social_interaction
# (Complex - do manually)

print("⚠️  Manually add _step_meta_cognition() method")
print("⚠️  Manually add call in _run_tick()")
print("⚠️  Manually add context in _build_social_context() and _step_monologue()")

file_path.write_text(content, encoding="utf-8")
print("✅ Partial automation complete. See instructions for remaining steps.")
```

Run: `python apply_stage24.py`

---

**Note:** Due to file size, manual editing is most reliable. Use your IDE's search (Ctrl+F) to find exact locations.
