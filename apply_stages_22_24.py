#!/usr/bin/env python3
"""
Automated integration script for Stage 22-24.
Fixes heavy_tick.py to include TimePerception, SocialLayer, and MetaCognition.

Usage:
    python apply_stages_22_24.py
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
    
    changes = []
    
    # 1. Add imports
    print("\n✅ Step 1: Checking imports...")
    
    imports_to_add = [
        ("from core.time_perception import TimePerception", "Stage 22"),
        ("from core.social_layer import SocialLayer", "Stage 23"),
        ("from core.meta_cognition import MetaCognition", "Stage 24"),
    ]
    
    for import_line, stage in imports_to_add:
        if import_line not in content:
            # Add after VectorMemory import
            content = content.replace(
                "from core.memory.vector_memory import VectorMemory",
                f"from core.memory.vector_memory import VectorMemory\n{import_line}  # {stage}"
            )
            changes.append(f"Added import: {import_line}")
            print(f"  ✅ Added {stage} import")
        else:
            print(f"  ✅ {stage} import already present")
    
    # 2. Check __init__ parameters
    print("\n⚠️  Step 2: __init__ parameters (manual check needed)")
    print("  Please verify __init__ has:")
    print("    - time_perception: 'TimePerception | None' = None")
    print("    - social_layer: 'SocialLayer | None' = None")
    print("    - meta_cognition: 'MetaCognition | None' = None")
    print("  And stores them as:")
    print("    - self._time_perc = time_perception")
    print("    - self._social = social_layer")
    print("    - self._meta_cog = meta_cognition")
    
    # 3. Check _run_tick calls
    print("\n🔍 Step 3: Checking _run_tick() method calls...")
    
    required_calls = [
        ("await self._step_time_perception(n)", "Stage 22"),
        ("await self._step_social_interaction(n)", "Stage 23"),
        ("await self._step_meta_cognition(n)", "Stage 24"),
    ]
    
    for call, stage in required_calls:
        if call in content:
            print(f"  ✅ {stage}: {call} present")
        else:
            print(f"  ❌ {stage}: {call} MISSING")
            changes.append(f"MISSING in _run_tick: {call}")
    
    # 4. Check methods exist
    print("\n🔍 Step 4: Checking methods exist...")
    
    required_methods = [
        ("async def _step_time_perception", "Stage 22"),
        ("async def _step_social_interaction", "Stage 23"),
        ("async def _step_meta_cognition", "Stage 24"),
    ]
    
    for method, stage in required_methods:
        if method in content:
            print(f"  ✅ {stage}: {method}() exists")
        else:
            print(f"  ❌ {stage}: {method}() MISSING")
            changes.append(f"MISSING method: {method}")
    
    # 5. Check _build_social_context
    print("\n🔍 Step 5: Checking _build_social_context()...")
    
    context_checks = [
        ("if self._time_perc:", "Stage 22"),
        ("if self._social:", "Stage 23 (optional in social_context)"),
        ("if self._meta_cog:", "Stage 24"),
    ]
    
    # Find _build_social_context method
    if "def _build_social_context(self)" in content:
        context_start = content.find("def _build_social_context(self)")
        context_end = content.find("\n    def ", context_start + 1)
        context_method = content[context_start:context_end]
        
        for check, stage in context_checks:
            if check in context_method and "to_prompt_context" in context_method:
                print(f"  ✅ {stage} context added")
            else:
                print(f"  ⚠️  {stage} context might be missing")
                changes.append(f"Check _build_social_context for {stage}")
    else:
        print("  ❌ _build_social_context() not found")
    
    # 6. Check _step_monologue
    print("\n🔍 Step 6: Checking _step_monologue()...")
    
    if "async def _step_monologue(self, n: int)" in content:
        monologue_start = content.find("async def _step_monologue(self, n: int)")
        monologue_end = content.find("\n    async def ", monologue_start + 1)
        if monologue_end == -1:
            monologue_end = content.find("\n    def ", monologue_start + 1)
        monologue_method = content[monologue_start:monologue_end]
        
        for check, stage in context_checks:
            if check in monologue_method and "to_prompt_context" in monologue_method:
                print(f"  ✅ {stage} context added")
            else:
                print(f"  ⚠️  {stage} context might be missing")
                changes.append(f"Check _step_monologue for {stage}")
    else:
        print("  ❌ _step_monologue() not found")
    
    # Summary
    print("\n" + "="*60)
    if content != original_content:
        print("✅ Changes made to imports")
        file_path.write_text(content, encoding="utf-8")
        print(f"   Saved to {file_path}")
    else:
        print("ℹ️  No automatic changes made")
    
    if changes:
        print("\n⚠️  MANUAL ACTIONS REQUIRED:")
        for i, change in enumerate(changes, 1):
            print(f"   {i}. {change}")
        print("\n📝 See docs/STAGE24_HEAVY_TICK_PATCH.md for detailed instructions")
    else:
        print("\n✅ All checks passed! heavy_tick.py appears to be correctly integrated.")
    
    print("="*60)

if __name__ == "__main__":
    main()
