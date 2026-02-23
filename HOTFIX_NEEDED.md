# 🔥 HOTFIX REQUIRED

## Issue:
```
[ERROR] CircuitBreaker.call() got an unexpected keyword argument 'fallback'
```

## Status:
- ✅ **Code is FIXED** in repository
- ❌ **Running instance has OLD code**
- 🔄 **Restart required** to apply fix

## What happened:
- Old code called `circuit_breaker.call(_call, fallback=value)`
- CircuitBreaker doesn't support `fallback` parameter
- Fixed by moving fallback handling to except block

## Current code (CORRECT):
```python
try:
    result = await self.chat_breaker.call(_call)  # No fallback param
    return result
except Exception as e:
    if fallback is not None:
        return fallback  # Handle fallback here
    raise
```

## Action Required:
1. **Stop** Digital Being
2. **Restart** to load new code
3. ✅ Error will be gone

## Hot Reload:
If hot reload is enabled, it should pick up the fix automatically.
If not - manual restart needed.

---

**Date:** 2026-02-23 17:00 MSK  
**Severity:** Medium (causes weekly update failures)  
**Fix:** Already in repository, needs restart
