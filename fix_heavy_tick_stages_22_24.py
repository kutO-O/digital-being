#!/usr/bin/env python3
"""
Automated fix script for heavy_tick.py Stage 22-24 integration.
Adds missing methods with correct indentation and separates logic.

Usage:
    python fix_heavy_tick_stages_22_24.py
"""

import re
from pathlib import Path

def main():
    file_path = Path("core/heavy_tick.py")
    
    if not file_path.exists():
        print("❌ Error: core/heavy_tick.py not found")
        return
    
    print("🔧 Reading heavy_tick.py...")
    content = file_path.read_text(encoding="utf-8")
    original_content = content
    
    # Backup
    backup_path = file_path.with_suffix(".py.backup")
    backup_path.write_text(content, encoding="utf-8")
    print(f"✅ Backup created: {backup_path}")
    
    # 1. Add imports
    print("\n📦 Step 1: Adding imports...")
    imports_to_add = [
        ("from core.time_perception import TimePerception", "Stage 22"),
        ("from core.social_layer import SocialLayer", "Stage 23"),
        ("from core.meta_cognition import MetaCognition", "Stage 24"),
    ]
    
    for import_line, stage in imports_to_add:
        if import_line not in content:
            content = content.replace(
                "from core.memory.vector_memory import VectorMemory",
                f"from core.memory.vector_memory import VectorMemory\n{import_line}  # {stage}"
            )
            print(f"  ✅ Added {stage} import")
        else:
            print(f"  ℹ️  {stage} import already present")
    
    # 2. Find where to insert methods (after _step_shell_executor)
    print("\n🔍 Step 2: Finding insertion point...")
    
    # Find _step_shell_executor method
    shell_pattern = r'(    async def _step_shell_executor\(self, n: int\) -> None:.*?(?=\n    async def |\n    def |\Z))'
    shell_match = re.search(shell_pattern, content, re.DOTALL)
    
    if not shell_match:
        print("  ⚠️  Could not find _step_shell_executor method")
        print("  Will append methods at end of class")
        # Find last method in class
        class_pattern = r'(class HeavyTick:.*?)(?=\n\nclass |\Z)'
        class_match = re.search(class_pattern, content, re.DOTALL)
        if class_match:
            insertion_point = class_match.end()
        else:
            print("  ❌ Could not find HeavyTick class")
            return
    else:
        insertion_point = shell_match.end()
        print(f"  ✅ Found insertion point after _step_shell_executor")
    
    # 3. Build methods to insert
    print("\n🏗️  Step 3: Building methods...")
    
    # Stage 22: Time Perception
    time_perception_method = '''

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
'''

    # Stage 23: Social Layer
    social_layer_method = '''

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
'''

    # Stage 24: Meta-Cognition
    meta_cognition_method = '''

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
'''

    # Check if methods already exist
    methods_to_add = []
    
    if "async def _step_time_perception(self, n: int)" not in content:
        methods_to_add.append(("_step_time_perception", time_perception_method))
        print("  ✅ Will add _step_time_perception()")
    else:
        print("  ℹ️  _step_time_perception() already exists")
    
    if "async def _step_social_interaction(self, n: int)" not in content:
        methods_to_add.append(("_step_social_interaction", social_layer_method))
        print("  ✅ Will add _step_social_interaction()")
    else:
        print("  ℹ️  _step_social_interaction() already exists")
    
    if "async def _step_meta_cognition(self, n: int)" not in content:
        methods_to_add.append(("_step_meta_cognition", meta_cognition_method))
        print("  ✅ Will add _step_meta_cognition()")
    else:
        print("  ℹ️  _step_meta_cognition() already exists")
    
    # Insert methods
    if methods_to_add:
        print("\n📝 Step 4: Inserting methods...")
        all_methods = "".join([method for _, method in methods_to_add])
        content = content[:insertion_point] + all_methods + content[insertion_point:]
        print(f"  ✅ Added {len(methods_to_add)} method(s)")
    else:
        print("\n ℹ️  All methods already present")
    
    # 5. Update _run_tick to call new methods
    print("\n🔄 Step 5: Updating _run_tick()...")
    
    # Find _run_tick method
    run_tick_pattern = r'(    async def _run_tick\(self, n: int\) -> None:.*?await self\._step_shell_executor\(n\))'
    run_tick_match = re.search(run_tick_pattern, content, re.DOTALL)
    
    if run_tick_match:
        calls_to_add = []
        if "await self._step_time_perception(n)" not in content:
            calls_to_add.append("\n        await self._step_time_perception(n)  # Stage 22")
        if "await self._step_social_interaction(n)" not in content:
            calls_to_add.append("\n        await self._step_social_interaction(n)  # Stage 23")
        if "await self._step_meta_cognition(n)" not in content:
            calls_to_add.append("\n        await self._step_meta_cognition(n)  # Stage 24")
        
        if calls_to_add:
            insertion_text = "".join(calls_to_add)
            content = content[:run_tick_match.end()] + insertion_text + content[run_tick_match.end():]
            print(f"  ✅ Added {len(calls_to_add)} call(s) to _run_tick()")
        else:
            print("  ℹ️  All calls already present in _run_tick()")
    else:
        print("  ⚠️  Could not find _run_tick method to update")
    
    # 6. Save file
    if content != original_content:
        print("\n💾 Step 6: Saving changes...")
        file_path.write_text(content, encoding="utf-8")
        print(f"  ✅ Saved to {file_path}")
        print(f"  ✅ Backup at {backup_path}")
        
        print("\n" + "="*60)
        print("✅ SUCCESS! heavy_tick.py has been updated.")
        print("="*60)
        
        print("\n📋 Next steps:")
        print("  1. Verify syntax: python -m py_compile core/heavy_tick.py")
        print("  2. Check __init__ has: self._time_perc, self._social, self._meta_cog")
        print("  3. Run system: python main.py")
    else:
        print("\nℹ️  No changes needed - file already up to date")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
