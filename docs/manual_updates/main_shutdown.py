"""
Add this to main.py for graceful shutdown.

Insert after imports and before main() function.
"""

import signal
import sys

def create_shutdown_handler(heavy_tick, light_tick, self_model, value_engine, milestones):
    """Factory function to create shutdown handler with component references."""
    def shutdown_handler(signum, frame):
        log.info(f"⚠️ Received signal {signum}, initiating graceful shutdown...")
        
        # Stop tickers
        try:
            heavy_tick.stop()
            log.info("✅ HeavyTick stopped")
        except Exception as e:
            log.error(f"❌ HeavyTick stop failed: {e}")
        
        try:
            light_tick.stop()
            log.info("✅ LightTick stopped")
        except Exception as e:
            log.error(f"❌ LightTick stop failed: {e}")
        
        # Flush pending writes
        log.info("💾 Flushing pending writes...")
        try:
            self_model._save()
            log.info("✅ SelfModel saved")
        except Exception as e:
            log.error(f"❌ SelfModel save failed: {e}")
        
        try:
            value_engine._persist_state()
            log.info("✅ ValueEngine persisted")
        except Exception as e:
            log.error(f"❌ ValueEngine persist failed: {e}")
        
        try:
            milestones._save()
            log.info("✅ Milestones saved")
        except Exception as e:
            log.error(f"❌ Milestones save failed: {e}")
        
        log.info("✅ Graceful shutdown complete. Goodbye! 👋")
        sys.exit(0)
    
    return shutdown_handler

# Usage in main():
# After all components are initialized:
# shutdown_handler = create_shutdown_handler(
#     heavy_tick, light_tick, self_model, value_engine, milestones
# )
# signal.signal(signal.SIGTERM, shutdown_handler)
# signal.signal(signal.SIGINT, shutdown_handler)
# log.info("✅ Signal handlers registered for graceful shutdown")
