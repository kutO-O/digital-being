# 🛠️ Scripts

## apply_improvements.py

**Auto-apply system improvements** from PR #10.

### Usage

```bash
# From project root
python scripts/apply_improvements.py
```

### What it does

1. **main.py** — Adds graceful shutdown with component flush
2. **core/heavy_tick.py** — Adds health check every 100 ticks
3. **core/strategy_engine.py** — Adds goal loop detector
4. **core/social_layer.py** — Adds inbox persistence

### Safety

- ✅ Idempotent (safe to run multiple times)
- ✅ Only patches files that exist
- ✅ Skips already-patched files
- ✅ No data loss

### Manual verification

```bash
# See what changed
git diff

# Test graceful shutdown
python main.py &
PID=$!
sleep 10
kill -TERM $PID
grep "✅ Graceful shutdown complete" logs/digital_being.log

# Test health check
# Wait for tick #100
grep "✅ Health check passed" logs/digital_being.log
```

---

**Questions?** See [PR #10](https://github.com/kutO-O/digital-being/pull/10)
