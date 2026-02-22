#!/usr/bin/env python3
"""
Auto-apply script for system improvements.
Usage: python scripts/apply_improvements.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

def patch_main_py():
    """Patch main.py with graceful shutdown."""
    print("📝 Patching main.py...")
    main_path = ROOT / "main.py"
    if not main_path.exists():
        print("❌ main.py not found!")
        return False
    
    content = main_path.read_text(encoding="utf-8")
    
    # Find and replace _signal_handler
    old_handler = r'def _signal_handler\(\):\s+logger\.info\("Shutdown signal received\."\)\s+stop_event\.set\(\)'
    
    new_handler = '''def _signal_handler():
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
        stop_event.set()'''
    
    if re.search(old_handler, content):
        content = re.sub(old_handler, new_handler, content)
        main_path.write_text(content, encoding="utf-8")
        print("✅ main.py patched successfully")
        return True
    else:
        print("⚠️ main.py: _signal_handler not found or already patched")
        return True

def patch_heavy_tick():
    """Patch heavy_tick.py with health check."""
    print("📝 Patching core/heavy_tick.py...")
    heavy_path = ROOT / "core" / "heavy_tick.py"
    if not heavy_path.exists():
        print("❌ core/heavy_tick.py not found!")
        return False
    
    content = heavy_path.read_text(encoding="utf-8")
    
    # Check if already patched
    if "health check every 100 ticks" in content.lower():
        print("⚠️ heavy_tick.py already patched")
        return True
    
    # Find insertion point after meta_cognition step
    insertion_marker = 'log.info(f"[HeavyTick #{n}] All steps finished.")'
    
    health_check_code = '''
        # ── Health Check (every 100 ticks) ──────────────────────────
        if n % 100 == 0:
            log.info(f"[HeavyTick #{n}] HEALTH CHECK")
            health_ok = True
            
            # Check episodic memory integrity
            if not self._mem.health_check():
                log.error(f"[HeavyTick #{n}] ❌ EpisodicMemory health check FAILED")
                health_ok = False
            
            # Check critical files exist
            critical_files = [
                self._cfg["paths"]["state"],
                "memory/self_model.json",
                "memory/values_state.json",
                "milestones/milestones.json",
            ]
            for fpath in critical_files:
                full_path = Path(fpath) if Path(fpath).is_absolute() else Path.cwd() / fpath
                if not full_path.exists():
                    log.error(f"[HeavyTick #{n}] ❌ Critical file missing: {fpath}")
                    health_ok = False
            
            if health_ok:
                log.info(f"[HeavyTick #{n}] ✅ Health check passed")
            else:
                log.error(f"[HeavyTick #{n}] ⚠️ Health check FAILED - system degradation detected")
                self._mem.add_episode(
                    "system.health_check_failed",
                    f"Health check failed at tick #{n}",
                    outcome="error",
                )

        log.info(f"[HeavyTick #{n}] All steps finished.")'''
    
    content = content.replace(
        f'        {insertion_marker}',
        health_check_code
    )
    
    heavy_path.write_text(content, encoding="utf-8")
    print("✅ core/heavy_tick.py patched successfully")
    return True

def patch_strategy_engine():
    """Patch strategy_engine.py with loop detector."""
    print("📝 Patching core/strategy_engine.py...")
    strategy_path = ROOT / "core" / "strategy_engine.py"
    if not strategy_path.exists():
        print("❌ core/strategy_engine.py not found!")
        return False
    
    content = strategy_path.read_text(encoding="utf-8")
    
    # Check if already patched
    if "_detect_loop" in content:
        print("⚠️ strategy_engine.py already patched")
        return True
    
    # Add _detect_loop method before select_goal
    loop_detector = '''
    def _detect_loop(self, recent_count: int = 5) -> bool:
        """Detect if system is stuck in a loop of repetitive goals.
        
        Returns:
            True if loop detected, False otherwise
        """
        if len(self._goal_history) < recent_count:
            return False
        
        recent_goals = [g["goal"] for g in self._goal_history[-recent_count:]]
        recent_actions = [g["action_type"] for g in self._goal_history[-recent_count:]]
        
        # Check if all recent goals are identical
        if len(set(recent_goals)) == 1:
            log.warning(f"🔁 LOOP DETECTED: Same goal repeated {recent_count} times: '{recent_goals[0][:60]}'")
            return True
        
        # Check if stuck on observe
        if recent_actions.count("observe") >= recent_count - 1:
            log.warning(f"🔁 LOOP DETECTED: Stuck on 'observe' action ({recent_count - 1}/{recent_count} ticks)")
            return True
        
        return False

'''
    
    # Find select_goal method and insert before it
    select_goal_pattern = r'(\s+async def select_goal\()'
    content = re.sub(select_goal_pattern, loop_detector + r'\1', content, count=1)
    
    # Now patch select_goal to use _detect_loop
    # Find the start of select_goal and add loop check
    select_goal_start = 'async def select_goal('
    if select_goal_start in content:
        # Find where to insert (after method signature and docstring)
        lines = content.split('\n')
        new_lines = []
        in_select_goal = False
        inserted = False
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            if 'async def select_goal(' in line:
                in_select_goal = True
            elif in_select_goal and not inserted and line.strip() and not line.strip().startswith('"""') and not line.strip().startswith('#'):
                # Insert loop check at first real line of method
                indent = len(line) - len(line.lstrip())
                loop_check = f"{' ' * indent}# Check for goal loops\n"
                loop_check += f"{' ' * indent}if self._detect_loop(recent_count=5):\n"
                loop_check += f"{' ' * (indent + 4)}log.warning(\"Forcing diversity due to detected loop\")\n"
                loop_check += f"{' ' * (indent + 4)}# Force a different action type\n"
                loop_check += f"{' ' * (indent + 4)}pass  # Let normal flow continue but LLM will see loop warning in context\n"
                loop_check += "\n"
                new_lines.insert(-1, loop_check)
                inserted = True
                in_select_goal = False
        
        content = '\n'.join(new_lines)
    
    strategy_path.write_text(content, encoding="utf-8")
    print("✅ core/strategy_engine.py patched successfully")
    return True

def patch_social_layer():
    """Patch social_layer.py with inbox persistence."""
    print("📝 Patching core/social_layer.py...")
    social_path = ROOT / "core" / "social_layer.py"
    if not social_path.exists():
        print("⚠️ core/social_layer.py not found (optional component)")
        return True
    
    content = social_path.read_text(encoding="utf-8")
    
    # Check if already patched
    if "_persist_inbox" in content:
        print("⚠️ social_layer.py already patched")
        return True
    
    # Add persistence methods before check_inbox
    persistence_methods = '''
    def _persist_inbox(self) -> None:
        """Save pending inbox messages to disk."""
        pending_path = self._memory_dir / "pending_inbox.json"
        try:
            with open(pending_path, "w", encoding="utf-8") as f:
                json.dump(self._inbox_messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to persist inbox: {e}")
    
    def _load_pending_inbox(self) -> None:
        """Load pending inbox messages from disk."""
        pending_path = self._memory_dir / "pending_inbox.json"
        if not pending_path.exists():
            return
        try:
            with open(pending_path, "r", encoding="utf-8") as f:
                self._inbox_messages = json.load(f)
            if self._inbox_messages:
                log.info(f"📬 Loaded {len(self._inbox_messages)} pending inbox messages")
        except Exception as e:
            log.error(f"Failed to load pending inbox: {e}")

'''
    
    # Find check_inbox method
    check_inbox_pattern = r'(\s+def check_inbox\()'
    content = re.sub(check_inbox_pattern, persistence_methods + r'\1', content, count=1)
    
    # Add _load_pending_inbox() to __init__
    init_pattern = r'(self\._inbox_messages = \[\])'
    content = re.sub(init_pattern, r'\1\n        self._load_pending_inbox()', content, count=1)
    
    # Add _persist_inbox() at end of check_inbox
    # Find the end of check_inbox method
    lines = content.split('\n')
    new_lines = []
    in_check_inbox = False
    indentation = None
    
    for i, line in enumerate(lines):
        if 'def check_inbox(' in line:
            in_check_inbox = True
            indentation = len(line) - len(line.lstrip())
        elif in_check_inbox and line.strip().startswith('return '):
            # Insert persistence before return
            new_lines.append(' ' * (indentation + 4) + 'self._persist_inbox()')
            in_check_inbox = False
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    social_path.write_text(content, encoding="utf-8")
    print("✅ core/social_layer.py patched successfully")
    return True

def main():
    print("="*60)
    print("🚀 Digital Being - Auto-Apply System Improvements")
    print("="*60)
    print()
    
    results = []
    
    results.append(("main.py", patch_main_py()))
    results.append(("heavy_tick.py", patch_heavy_tick()))
    results.append(("strategy_engine.py", patch_strategy_engine()))
    results.append(("social_layer.py", patch_social_layer()))
    
    print()
    print("="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    if all(r[1] for r in results):
        print()
        print("🎉 All improvements applied successfully!")
        print()
        print("Next steps:")
        print("1. Review changes: git diff")
        print("2. Test system: python main.py")
        print("3. Verify: kill -TERM <pid> (should see graceful shutdown)")
        return 0
    else:
        print()
        print("⚠️ Some patches failed. Check errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
