# Phase 2: Critical Fixes

> **Goal:** Fix all P0 (critical) issues identified in Phase 1 audit to make the system stable enough for production use.

---

## Context

### Prerequisites
- ✅ Phase 1 audit must be complete
- ✅ Technical Debt Register created
- ✅ P0 issues clearly identified

### What Phase 1 Should Have Identified

Common P0 issues in autonomous AI systems:
1. **Error Recovery:** No graceful degradation when components fail
2. **Resource Leaks:** Memory, file handles, or connections not cleaned up
3. **Race Conditions:** Concurrent access to shared resources
4. **Data Corruption:** Unsafe file/database operations
5. **Crash Loops:** Errors that cause restart cycles

### Expected P0 Count
Typically 5-15 critical issues in a system of this complexity.

---

## Your Task

### For Each P0 Issue:

1. **Understand the Root Cause**
   - Why does this issue exist?
   - What was the original intent?
   - What changed to make it critical?

2. **Design the Fix**
   - What's the minimal safe fix?
   - What's the ideal long-term solution?
   - Are there dependencies or blockers?

3. **Implement Carefully**
   - Write the fixed code
   - Add error handling
   - Include logging for debugging
   - Add comments explaining the fix

4. **Test Thoroughly**
   - Verify the fix works
   - Ensure no regressions
   - Test edge cases
   - Document test procedure

5. **Document Everything**
   - What was changed and why
   - Any trade-offs made
   - Testing performed
   - Remaining risks

---

## Output Format

For each P0 issue fixed:

```markdown
## Issue: [P0-XXX] [Short Description]

**From Audit:** [Link to phase-1-results.md section]
**Priority:** P0
**Component:** `path/to/file.py`
**Lines Affected:** XXX-YYY

### Root Cause Analysis
[Explain why this issue exists and why it's critical]

### Fix Strategy
**Approach:** [Minimal fix / Refactor / Rewrite]
**Dependencies:** [None / Requires X to be fixed first]
**Risk:** [Low / Medium / High]

### Implementation

**Files Changed:**
- `path/to/file.py` (lines XXX-YYY)
- `path/to/other.py` (lines AAA-BBB)

**Code Diff:**
```python
# BEFORE (problematic code)
old_code_here

# AFTER (fixed code)
new_code_here
```

**Key Changes:**
1. Added error handling for X
2. Fixed race condition with lock
3. Ensured resource cleanup with context manager

### Testing

**Test Procedure:**
1. Step 1
2. Step 2
3. Expected result: ...

**Test Results:**
- ✅ Basic functionality works
- ✅ Edge case A handled
- ✅ No regression in component B
- ⚠️ Known limitation: ...

### Documentation Updates
- [ ] Added docstring explaining fix
- [ ] Updated ARCHITECTURE_MASTER.md if architecture changed
- [ ] Added logging for debugging
- [ ] Commented complex logic

### Remaining Risks
[Any concerns or limitations of this fix]

### Recommendations for Phase 3
[If this was a minimal fix, what's the ideal long-term solution?]

---
```

---

## Requirements

### Mandatory
- ✅ Fix ALL P0 issues from Phase 1
- ✅ No new bugs introduced
- ✅ System must start successfully
- ✅ Add comprehensive error logging
- ✅ All changes documented

### Code Quality
- ✅ Type hints added for new code
- ✅ Docstrings for new functions
- ✅ Follows project style guide
- ✅ Error messages are clear and actionable

### Testing
- ✅ Manual test procedure documented
- ✅ Edge cases considered
- ✅ No regressions verified

---

## Success Criteria

**Phase 2 is complete when:**

1. ✅ All P0 issues have documented fixes
2. ✅ System runs for 24 hours without crashes
3. ✅ Error logs show graceful degradation, not crashes
4. ✅ All changes committed to git
5. ✅ ARCHITECTURE_MASTER.md "Known Problems" section updated
6. ✅ Technical Debt Register shows P0 items as "Fixed"

**Quality Gate:**
Run the system for 24 hours with:
- Regular interactions (messages sent)
- Component stress (multiple goals active)
- Error injection (kill Ollama temporarily, fill disk, etc.)

System should:
- ✅ Recover gracefully from errors
- ✅ Log issues clearly
- ✅ Not lose data
- ✅ Continue functioning (degraded OK, crash NOT OK)

---

## Common P0 Fixes

### 1. Adding Error Recovery

**Before:**
```python
def heavy_tick():
    while True:
        process_goals()  # If this crashes, system dies
        time.sleep(1)
```

**After:**
```python
def heavy_tick():
    while True:
        try:
            process_goals()
        except Exception as e:
            logger.error(f"Goal processing failed: {e}", exc_info=True)
            # Continue running, goals will be retried
        time.sleep(1)
```

### 2. Fixing Resource Leaks

**Before:**
```python
def save_memory(data):
    f = open("memory.json", "w")
    json.dump(data, f)  # If this fails, file not closed
```

**After:**
```python
def save_memory(data):
    try:
        with open("memory.json", "w") as f:
            json.dump(data, f)
    except IOError as e:
        logger.error(f"Failed to save memory: {e}")
        raise MemorySaveError("Could not persist memory") from e
```

### 3. Fixing Race Conditions

**Before:**
```python
class MessageQueue:
    def __init__(self):
        self.messages = []
    
    def add(self, msg):
        self.messages.append(msg)  # Not thread-safe
```

**After:**
```python
import threading

class MessageQueue:
    def __init__(self):
        self.messages = []
        self._lock = threading.Lock()
    
    def add(self, msg):
        with self._lock:
            self.messages.append(msg)
```

---

## Execution Strategy

### Option A: Fix All at Once (Risky)
1. Fix all P0 issues in one session
2. Test everything together
3. Commit once

**Pros:** Fast  
**Cons:** Hard to debug if something breaks

### Option B: Fix One-by-One (Recommended)
1. Fix one P0 issue
2. Test that specific fix
3. Commit
4. Move to next P0

**Pros:** Safe, easy to rollback  
**Cons:** More commits

**Recommendation:** Use Option B unless P0 issues are interdependent.

---

## Git Workflow

For each fix:

```bash
# Create feature branch
git checkout -b fix/p0-xxx-description

# Make changes
# Test thoroughly

# Commit with detailed message
git add path/to/fixed/file.py
git commit -m "Fix: [P0-XXX] Description

Root Cause: ...
Fix: ...
Tested: ...

Closes TD-XXX from Technical Debt Register"

# Merge to main
git checkout main
git merge fix/p0-xxx-description
git push
```

---

## Risk Mitigation

### Before Making Changes
1. ✅ Create a backup branch: `git checkout -b backup-before-phase2`
2. ✅ Document current behavior (even if broken)
3. ✅ Identify rollback procedure

### During Changes
1. ✅ Test each fix independently
2. ✅ Keep changes minimal
3. ✅ Don't fix non-P0 issues yet (resist temptation!)

### After Changes
1. ✅ Run extended test (24 hours)
2. ✅ Monitor logs for new errors
3. ✅ Validate with owner that system feels more stable

---

## Deliverables

1. **Phase 2 Results Document**
   - Save as: `docs/prompts/phase-2-results.md`
   - Include all fix documentation
   - Summarize overall improvements

2. **Updated Code**
   - All P0 fixes committed
   - Descriptive commit messages
   - No merge conflicts

3. **Updated Documentation**
   - ARCHITECTURE_MASTER.md "Known Problems" section
   - Technical Debt Register (P0 items marked "Fixed")
   - Any new decisions in Decision Log

4. **Test Report**
   - Document 24-hour stability test results
   - List any new issues discovered
   - Confirm success criteria met

---

## What NOT to Do

❌ **Don't:** Fix P1/P2/P3 issues yet  
✅ **Do:** Focus only on P0

❌ **Don't:** Refactor while fixing  
✅ **Do:** Minimal safe fix first, refactor in Phase 3

❌ **Don't:** Skip testing  
✅ **Do:** Thorough testing for each fix

❌ **Don't:** Commit untested code  
✅ **Do:** Verify before committing

❌ **Don't:** Change architecture  
✅ **Do:** Work within current structure

---

## Emergency Procedures

### If a Fix Makes Things Worse

```bash
# Rollback immediately
git revert [commit-sha]

# Document what happened
# Re-analyze the issue
# Try a different approach
```

### If You Can't Fix a P0

1. Document why it's hard to fix
2. Propose a workaround or mitigation
3. Escalate to owner for decision
4. Consider if it's truly P0 or can be downgraded

### If New P0 Discovered

1. Add to Technical Debt Register
2. Assess if it blocks Phase 2 completion
3. Fix immediately if blocking
4. Otherwise defer to separate fix cycle

---

## Estimated Time

- **Per P0 Issue:** 2-6 hours (understand, fix, test, document)
- **Total for 10 P0 issues:** 1-2 weeks
- **24-hour stability test:** 1 day

**Total Phase 2:** 2-3 weeks

---

## Questions Before Starting?

1. Do you have the Phase 1 audit results?
2. Are P0 issues clearly identified and prioritized?
3. Do you have backup/rollback procedure ready?
4. Any questions about specific P0 issues?

---

**When ready, start with the highest priority P0 issue and work systematically through the list.**
