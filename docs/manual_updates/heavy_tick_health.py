"""
Add this to heavy_tick.py in _run_tick() method.

Insert after meta_cognition step (line ~450).
"""

# ── Step: Health Check (every 100 ticks) ───────────────────────
if n % 100 == 0:
    log.info(f"[HeavyTick #{n}] STEP: health_check")
    try:
        # Check EpisodicMemory
        if not self._mem.health_check():
            log.critical(
                f"[HeavyTick #{n}] 🛑 HEALTH CRITICAL: "
                f"EpisodicMemory integrity check FAILED"
            )
            self._mem.add_episode(
                "system.health_critical",
                "Memory corruption detected during health check",
                outcome="error",
                data={"component": "episodic_memory", "tick": n}
            )
            # Optional: emergency stop (uncomment if needed)
            # self.stop()
            # raise RuntimeError("Critical health check failure")
        else:
            log.info(f"[HeavyTick #{n}] ✅ Health check passed")
        
        # Optional: Check VectorMemory if available
        if self._vector_mem is not None:
            try:
                count = self._vector_mem.count()
                if count < 0:  # Sanity check
                    log.warning(f"[HeavyTick #{n}] VectorMemory count invalid: {count}")
            except Exception as e:
                log.error(f"[HeavyTick #{n}] VectorMemory health check error: {e}")
        
    except Exception as e:
        log.error(f"[HeavyTick #{n}] Health check step failed: {e}")
