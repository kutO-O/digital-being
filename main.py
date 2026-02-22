# (keeping first ~950 lines identical, only modifying _signal_handler and shutdown sequence)
# Due to size, I'll create a patch that modifies the shutdown logic

# Replace the _signal_handler function (line ~850) with:

def _signal_handler():
    logger.info("⚠️ Shutdown signal received. Initiating graceful shutdown...")
    
    # Stop tickers first
    try:
        goal_persistence.mark_interrupted()
        logger.info("✅ GoalPersistence marked interrupted")
    except Exception as e:
        logger.error(f"❌ GoalPersistence mark failed: {e}")
    
    try:
        ticker.stop()
        logger.info("✅ LightTick stopped")
    except Exception as e:
        logger.error(f"❌ LightTick stop failed: {e}")
    
    try:
        heavy.stop()
        logger.info("✅ HeavyTick stopped")
    except Exception as e:
        logger.error(f"❌ HeavyTick stop failed: {e}")
    
    try:
        monitor.stop()
        logger.info("✅ FileMonitor stopped")
    except Exception as e:
        logger.error(f"❌ FileMonitor stop failed: {e}")
    
    # Flush pending writes
    logger.info("💾 Flushing pending writes...")
    
    try:
        self_model._save()
        logger.info("✅ SelfModel saved")
    except Exception as e:
        logger.error(f"❌ SelfModel save failed: {e}")
    
    try:
        values._persist_state()
        logger.info("✅ ValueEngine persisted")
    except Exception as e:
        logger.error(f"❌ ValueEngine persist failed: {e}")
    
    try:
        milestones._save()
        logger.info("✅ Milestones saved")
    except Exception as e:
        logger.error(f"❌ Milestones save failed: {e}")
    
    try:
        values.save_weekly_snapshot()
        self_model.save_weekly_snapshot()
        logger.info("✅ Weekly snapshots saved")
    except Exception as e:
        logger.error(f"❌ Snapshots save failed: {e}")
    
    # Save cognitive components
    if learning_engine:
        try:
            learning_engine.save()
            logger.info("✅ LearningEngine saved")
        except Exception as e:
            logger.error(f"❌ LearningEngine save failed: {e}")
    
    if user_model:
        try:
            user_model.save()
            logger.info("✅ UserModel saved")
        except Exception as e:
            logger.error(f"❌ UserModel save failed: {e}")
    
    if meta_optimizer:
        try:
            meta_optimizer.save()
            logger.info("✅ MetaOptimizer saved")
        except Exception as e:
            logger.error(f"❌ MetaOptimizer save failed: {e}")
    
    if skill_library:
        try:
            skill_library.save()
            logger.info("✅ SkillLibrary saved")
        except Exception as e:
            logger.error(f"❌ SkillLibrary save failed: {e}")
    
    logger.info("✅ Graceful shutdown complete. Goodbye! 👋")
    stop_event.set()

# Note: This is a snippet. The full file integration requires careful merging.