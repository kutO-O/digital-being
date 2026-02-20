# Complete Integration Guide: Stage 22-24

## 🛠️ Quick Start

**Run automated checker:**
```bash
python apply_stages_22_24.py
```

This will:
- ✅ Add missing imports automatically
- 🔍 Check if methods exist
- 🔍 Check if methods are called in `_run_tick()`
- 🔍 Check if context is added to prompts

---

## 📝 Manual Integration Steps

### 1. Add Imports (Top of file)

**Location:** After `from core.memory.vector_memory import VectorMemory`

```python
from core.memory.vector_memory import VectorMemory
from core.time_perception import TimePerception  # Stage 22
from core.social_layer import SocialLayer  # Stage 23
from core.meta_cognition import MetaCognition  # Stage 24
```

---

### 2. Update `__init__` Parameters

**Add these parameters:**
```python
def __init__(
    self,
    cfg: dict,
    ollama: "OllamaClient",
    world: "WorldModel",
    mem: "EpisodicMemory",
    vec: "VectorMemory",
    values: "ValueEngine",
    self_model: "SelfModel",
    strategy: "StrategyEngine",
    milestones: "Milestones",
    # ... other parameters ...
    shell_executor: "ShellExecutor | None" = None,
    time_perception: "TimePerception | None" = None,  # ← Stage 22
    social_layer: "SocialLayer | None" = None,       # ← Stage 23
    meta_cognition: "MetaCognition | None" = None,   # ← Stage 24
) -> None:
```

**Store them:**
```python
self._shell = shell_executor
self._time_perc = time_perception  # Stage 22
self._social = social_layer        # Stage 23
self._meta_cog = meta_cognition    # Stage 24
```

---

### 3. Add Stage 22 Method: `_step_time_perception()`

**Location:** After `_step_shell_executor()` method

```python
# ────────────────────────────────────────────────────────────────
# Stage 22: Time Perception
# ────────────────────────────────────────────────────────────────
async def _step_time_perception(self, n: int) -> None:
    """Stage 22: Update temporal context and detect time-based patterns."""
    if self._time_perc is None:
        return

    loop = asyncio.get_event_loop()

    # Update current temporal context every tick
    self._time_perc.update_context()

    # Detect patterns periodically (every 10 ticks)
    if n % 10 == 0:
        log.info(f"[HeavyTick #{n}] TimePerception: detecting temporal patterns.")
        try:
            episodes = self._mem.get_recent_episodes(50)
            await loop.run_in_executor(
                None,
                lambda: self._time_perc.detect_patterns(episodes, self._ollama),
            )
        except Exception as e:
            log.error(f"[HeavyTick #{n}] TimePerception error: {e}")
```

---

### 4. Add Stage 23 Method: `_step_social_interaction()`

**Location:** After `_step_time_perception()` method

```python
# ────────────────────────────────────────────────────────────────
# Stage 23: Social Layer
# ────────────────────────────────────────────────────────────────
async def _step_social_interaction(self, n: int) -> None:
    """Stage 23: Check for user messages and respond if needed."""
    if self._social is None:
        return

    loop = asyncio.get_event_loop()

    # Check for new messages
    msg = self._social.check_inbox()
    if msg:
        log.info(f"[HeavyTick #{n}] SocialLayer: received message from user.")
        try:
            # Build context for response
            context = self._build_social_context()

            # Generate response
            response = await loop.run_in_executor(
                None,
                lambda: self._social.respond_to_message(msg, context, self._ollama),
            )

            if response:
                log.info(f"[HeavyTick #{n}] SocialLayer: sent response.")
        except Exception as e:
            log.error(f"[HeavyTick #{n}] SocialLayer error: {e}")

    # Check if should initiate conversation
    should_init = self._social.should_initiate_conversation(
        self._mem, self._emotions, self._curiosity
    )

    if should_init:
        log.info(f"[HeavyTick #{n}] SocialLayer: initiating conversation.")
        try:
            context = self._build_social_context()
            await loop.run_in_executor(
                None,
                lambda: self._social.initiate_conversation(context, self._ollama),
            )
        except Exception as e:
            log.error(f"[HeavyTick #{n}] SocialLayer error during initiation: {e}")
```

---

### 5. Add Stage 24 Method: `_step_meta_cognition()`

**Location:** After `_step_social_interaction()` method

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
                None,
                lambda: self._meta_cog.analyze_decision_quality(
                    episodes, self._ollama
                ),
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
                    ),
                )

                for ins in insights[:2]:
                    self._meta_cog.add_insight(
                        ins["insight_type"],
                        ins["description"],
                        ins.get("confidence", 0.5),
                        ins.get("impact", "medium"),
                    )

                if insights:
                    log.info(
                        f"[HeavyTick #{n}] MetaCognition: "
                        f"{len(insights)} insight(s) discovered."
                    )

        except Exception as e:
            log.error(f"[HeavyTick #{n}] MetaCognition error: {e}")
```

---

### 6. Update `_run_tick()` Method

**Location:** Inside `async def _run_tick(self, n: int)` method

**Add these calls in order:**

```python
await self._step_contradiction_resolver(n)
await self._step_shell_executor(n)  # Stage 21
await self._step_time_perception(n)  # Stage 22 ← ADD THIS
await self._step_social_interaction(n)  # Stage 23 ← ADD THIS
await self._step_meta_cognition(n)  # Stage 24 ← ADD THIS
```

**Full context:**
```python
async def _run_tick(self, n: int) -> None:
    """Heavy Tick: observe, reflect, decide, act."""
    log.info(f"[HeavyTick #{n}] Start")

    await self._step_observe(n)
    await self._step_goal_check(n)
    await self._step_emotion(n)
    await self._step_attention(n)
    await self._step_reflection(n)
    await self._step_dream(n)
    await self._step_strategy(n)
    await self._step_action(n)
    await self._step_monologue(n)
    await self._step_narrative(n)
    await self._step_curiosity(n)
    await self._step_belief(n)
    await self._step_contradiction_resolver(n)
    await self._step_shell_executor(n)  # Stage 21
    await self._step_time_perception(n)  # Stage 22
    await self._step_social_interaction(n)  # Stage 23
    await self._step_meta_cognition(n)  # Stage 24

    log.info(f"[HeavyTick #{n}] End")
```

---

### 7. Update `_build_social_context()` Method

**Location:** Find `def _build_social_context(self) -> str:`

**Add at the end (before `return`):**

```python
def _build_social_context(self) -> str:
    """Build context for social interactions."""
    parts = []

    # ... existing context building ...

    # Add Stage 22-24 contexts
    if self._time_perc:
        parts.append(self._time_perc.to_prompt_context(2))

    if self._meta_cog:
        parts.append(self._meta_cog.to_prompt_context(2))

    return "\n".join(parts)
```

---

### 8. Update `_step_monologue()` Method

**Location:** Find `async def _step_monologue(self, n: int)` and the context building section

**Add Stage 22-24 contexts:**

```python
async def _step_monologue(self, n: int) -> None:
    """Internal monologue."""
    # ... existing code ...

    parts = []
    # ... existing context parts ...

    # Add Stage 22-24 contexts
    if self._time_perc:
        parts.append(self._time_perc.to_prompt_context(2))

    if self._meta_cog:
        parts.append(self._meta_cog.to_prompt_context(2))

    context = "\n".join(parts)
    # ... rest of method ...
```

---

## ✅ Verification Checklist

After making changes, verify:

```bash
# 1. Run the checker
python apply_stages_22_24.py

# 2. Check syntax
python -m py_compile core/heavy_tick.py

# 3. Run the system
python main.py
```

**Expected output:**
```
TimePerception ready. patterns=0
SocialLayer ready. conversations=0
MetaCognition ready. insights=0 decisions_logged=0 calibration=0.50
```

**After running:**
- Tick #10: TimePerception detects patterns
- Every tick: SocialLayer checks inbox
- Tick #50: MetaCognition analyzes decisions

---

## 📝 Summary

**7 changes needed:**
1. ✅ Add 3 imports (automated)
2. ✅ Add 3 parameters to `__init__`
3. ✅ Store 3 components as instance variables
4. ✅ Add 3 methods: `_step_time_perception`, `_step_social_interaction`, `_step_meta_cognition`
5. ✅ Call 3 methods in `_run_tick()`
6. ✅ Add context to `_build_social_context()`
7. ✅ Add context to `_step_monologue()`

**Total lines to add:** ~150 lines
**Estimated time:** 10-15 minutes

---

## 🛠️ Troubleshooting

**Problem:** `AttributeError: 'HeavyTick' object has no attribute '_time_perc'`
**Solution:** Add to `__init__`: `self._time_perc = time_perception`

**Problem:** Method not called
**Solution:** Add `await self._step_xxx(n)` to `_run_tick()`

**Problem:** Context not in LLM prompts
**Solution:** Add `if self._xxx: parts.append(self._xxx.to_prompt_context(2))` to both context methods

---

**Need help?** See [STAGE24_HEAVY_TICK_PATCH.md](./STAGE24_HEAVY_TICK_PATCH.md) for Stage 24 specifics.
