# 🛠️ Manual Integration Guide

This directory contains code snippets that need to be **manually integrated** into existing files.

## 📝 Why Manual?

These changes require context-aware placement within existing methods. Copy-pasting the entire file would overwrite your custom modifications.

---

## 🚀 Quick Start

### 1️⃣ Graceful Shutdown

**File:** `main.py`  
**Template:** [`main_shutdown.py`](./main_shutdown.py)

**Steps:**
1. Open `main.py`
2. After imports, add the `create_shutdown_handler()` function
3. In `main()`, after all components are initialized:
   ```python
   shutdown_handler = create_shutdown_handler(
       heavy_tick, light_tick, self_model, value_engine, milestones
   )
   signal.signal(signal.SIGTERM, shutdown_handler)
   signal.signal(signal.SIGINT, shutdown_handler)
   log.info("✅ Signal handlers registered")
   ```

**Test:**
```bash
kill -TERM <pid>  # Should see "graceful shutdown" in logs
```

---

### 2️⃣ Health Monitoring

**File:** `core/heavy_tick.py`  
**Template:** [`heavy_tick_health.py`](./heavy_tick_health.py)

**Steps:**
1. Open `core/heavy_tick.py`
2. Find `_run_tick()` method
3. After the `meta_cognition` step (~line 450), insert the health check code

**Test:**
```bash
# Wait for tick #100, #200, etc.
# Should see "✅ Health check passed" in logs
```

---

### 3️⃣ Goal Loop Detector

**File:** `core/strategy_engine.py`  
**Template:** [`strategy_loop_detector.py`](./strategy_loop_detector.py)

**Steps:**
1. Open `core/strategy_engine.py`
2. Add the `_detect_loop()` method to `StrategyEngine` class
3. In `select_goal()`, add the loop check **at the very start** (before LLM call)

**Test:**
```bash
# System should break out of repetitive "observe" actions
# Look for "🔁 LOOP DETECTED" in logs
```

---

### 4️⃣ Social Layer Persistence

**File:** `core/social_layer.py`  
**Template:** [`social_persistence.py`](./social_persistence.py)

**Steps:**
1. Open `core/social_layer.py`
2. Add `_persist_inbox()` and `_load_pending_inbox()` methods
3. In `__init__()`, after `self._inbox_messages = []`, call `self._load_pending_inbox()`
4. In `check_inbox()`, add `self._persist_inbox()` at the end

**Test:**
```bash
# 1. Send message to inbox.txt
# 2. Kill system BEFORE it replies
# 3. Restart system
# 4. System should remember unread message
```

---

## ✅ Verification Checklist

After integrating all updates:

- [ ] System handles `SIGTERM` gracefully (no data loss)
- [ ] Health checks run every 100 ticks
- [ ] Loop detector prevents repetitive goals
- [ ] Inbox messages survive restart
- [ ] All JSON files use atomic writes (no `.tmp` files left behind)

---

## 📊 Impact

| Feature | Lines Added | Complexity |
|---------|------------|------------|
| Graceful Shutdown | ~35 | Low |
| Health Check | ~25 | Low |
| Loop Detector | ~30 | Medium |
| Social Persistence | ~40 | Medium |
| **TOTAL** | **~130** | **Low-Medium** |

---

## ⚠️ Troubleshooting

### "NameError: name 'log' is not defined"
**Solution:** Add `import logging` at top of file, and `log = logging.getLogger(__name__)`

### "AttributeError: 'NoneType' has no attribute '_save'"
**Solution:** Check that components are initialized before signal handler setup

### Health check fails immediately
**Solution:** Run `PRAGMA integrity_check` on `memory/episodic.db` using SQLite CLI

---

## 🚀 Future Enhancements (Stage 26+)

Not included in this PR, but recommended:

1. **Prometheus Metrics** - `/metrics` endpoint for Grafana
2. **Semantic Principle Search** - Use VectorMemory for principle retrieval
3. **Multi-Agent Debate** - Two LLMs argue, third synthesizes
4. **A/B Testing** - System compares strategies empirically
5. **Web Dashboard** - React UI for real-time monitoring

See main README for full roadmap.

---

**Questions?** Open an issue or check [PR #10](https://github.com/kutO-O/digital-being/pull/10)
