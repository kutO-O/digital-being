# CRITICAL FIX: Correctly Indented Methods for Stage 22-24

## ⚠️ WARNING

The previous guide had **incorrect indentation**. Methods were shown as module-level functions instead of class methods. This would cause **syntax errors**.

This file contains **properly indented** methods ready to copy-paste into `class HeavyTick`.

---

## ✅ Stage 22: Time Perception Method

**Location:** Inside `class HeavyTick`, after `_step_shell_executor()` method

**Copy this ENTIRE block:**

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

**Note:** Notice the **4-space indent** at the beginning — this makes it a class method.

---

## ✅ Stage 23: Social Interaction Method

**Location:** Inside `class HeavyTick`, after `_step_time_perception()` method

**Copy this ENTIRE block:**

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

**Note:** This method contains **ONLY social layer logic** — inbox checking, message responses, conversation initiation.

---

## ✅ Stage 24: Meta-Cognition Method

**Location:** Inside `class HeavyTick`, after `_step_social_interaction()` method

**Copy this ENTIRE block:**

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

**Note:** This method contains **ONLY meta-cognition logic** — decision quality analysis, cognitive pattern detection, insight discovery.

---

## ✅ Update `_build_social_context()` Method

**Find existing method (should already exist in heavy_tick.py):**

```python
    def _build_social_context(self) -> str:
        """Build context for social interactions."""
        parts = []

        # Existing context building code...
        # ...

        # ADD THESE LINES AT THE END (before return):
        if self._time_perc:
            parts.append(self._time_perc.to_prompt_context(2))

        if self._meta_cog:
            parts.append(self._meta_cog.to_prompt_context(2))

        return "\n".join(parts)
```

**Note:** Only add the new `if` blocks if they don't already exist.

---

## ✅ Update `_step_monologue()` Method

**Find the context building section in this method:**

```python
    async def _step_monologue(self, n: int) -> None:
        """Internal monologue."""
        # ... existing code ...

        parts = []
        # ... existing parts.append() calls ...

        # ADD THESE LINES (before context = "\n".join(parts)):
        if self._time_perc:
            parts.append(self._time_perc.to_prompt_context(2))

        if self._meta_cog:
            parts.append(self._meta_cog.to_prompt_context(2))

        context = "\n".join(parts)
        # ... rest of method ...
```

---

## ✅ Call Methods in `_run_tick()`

**Find `async def _run_tick(self, n: int)` and add these lines:**

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
        await self._step_time_perception(n)  # ← ADD THIS (Stage 22)
        await self._step_social_interaction(n)  # ← ADD THIS (Stage 23)
        await self._step_meta_cognition(n)  # ← ADD THIS (Stage 24)

        log.info(f"[HeavyTick #{n}] End")
```

---

## ⚠️ CRITICAL: Indentation Rules

**ALL methods inside `class HeavyTick` must:**
1. Start with **4 spaces** (one indent level)
2. Method body has **8 spaces** (two indent levels)
3. Nested blocks add **4 more spaces** each level

**Example:**
```python
class HeavyTick:  # 0 spaces
    def method(self):  # 4 spaces
        if condition:  # 8 spaces
            do_something()  # 12 spaces
```

---

## ✅ Verification

After making changes:

```bash
# 1. Check syntax
python -m py_compile core/heavy_tick.py

# 2. If no errors, run system
python main.py
```

**Expected output:**
```
TimePerception ready. patterns=0
SocialLayer ready. conversations=0
MetaCognition ready. insights=0 decisions_logged=0 calibration=0.50
```

---

## 🛠️ Troubleshooting

**Error:** `IndentationError: expected an indented block`
**Solution:** Methods must be indented 4 spaces from `class HeavyTick:`

**Error:** `AttributeError: 'HeavyTick' object has no attribute '_time_perc'`
**Solution:** Add to `__init__`: `self._time_perc = time_perception`

**Error:** `NameError: name 'asyncio' is not defined`
**Solution:** Ensure `import asyncio` is at top of file

---

## 📋 Summary

**3 methods to add (with correct indentation):**
- `_step_time_perception()` — 24 lines
- `_step_social_interaction()` — 46 lines  
- `_step_meta_cognition()` — 58 lines

**2 methods to update:**
- `_build_social_context()` — add 4 lines
- `_step_monologue()` — add 4 lines

**1 method to update:**
- `_run_tick()` — add 3 calls

**Total:** ~140 lines of code

**All code blocks in this file have CORRECT indentation and are ready to copy-paste.**
