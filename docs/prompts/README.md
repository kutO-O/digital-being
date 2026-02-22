# Prompts Directory

> **Purpose:** This directory contains phase-specific prompts for systematically refactoring the Digital Being project to production-grade quality.

---

## What Is This?

This is a **multi-stage workflow system** designed to overcome a fundamental limitation of AI assistants: **context loss**.

### The Problem

Working on a large refactoring project with AI assistants is challenging because:
- Conversations eventually lose context
- You can't rely on chat history across sessions
- Different AI assistants can't access each other's work
- Progress gets lost between sessions

### The Solution

**Self-contained prompts** that include:
1. Full project context
2. Specific task definition
3. Required output format
4. Success criteria
5. Examples and templates

Each prompt is designed to be **copied into a fresh AI chat** with zero prior context needed.

---

## Available Prompts

### Phase 1: Code Audit
**File:** [`phase-1-audit.md`](./phase-1-audit.md)  
**Goal:** Complete analysis of codebase quality  
**Time:** 3-5 hours  
**Deliverable:** Comprehensive audit report with quality scores

**Use when:**
- Starting the refactoring process
- Need to understand current state
- Want to identify all problems

---

### Phase 2: Critical Fixes
**File:** [`phase-2-critical-fixes.md`](./phase-2-critical-fixes.md)  
**Goal:** Fix all P0 (critical) bugs and stability issues  
**Time:** 2-3 weeks  
**Deliverable:** Stable system that runs 24+ hours without crashes

**Use when:**
- Phase 1 audit is complete
- System has crashes or data loss issues
- Need baseline stability before refactoring

**Prerequisites:**
- [ ] Phase 1 complete
- [ ] P0 issues identified in Technical Debt Register

---

### Phase 3: Code Quality
**File:** [`phase-3-code-quality.md`](./phase-3-code-quality.md)  
**Goal:** Add type hints, docstrings, tests, improve architecture  
**Time:** 2-3 weeks  
**Deliverable:** Production-grade code that passes all quality checks

**Use when:**
- Phase 2 fixes are complete
- System is stable
- Ready to improve maintainability

**Prerequisites:**
- [ ] Phase 1 complete
- [ ] Phase 2 complete
- [ ] No P0 issues remaining

---

### Future Phases (To Be Created)

**Phase 4: Architecture Cleanup**
- Extract interfaces
- Implement dependency injection
- Consolidate duplicate functionality
- Optimize performance

**Phase 5: Advanced Features**
- Improve multi-agent coordination
- Enhanced memory consolidation
- Telemetry and metrics
- Long-term stability testing

---

## How to Use These Prompts

### Quick Start (5 steps)

1. **Check current phase**
   ```bash
   # Look in docs/ARCHITECTURE_MASTER.md
   # Find "Refactoring Roadmap" section
   # See which phase has unchecked [ ] boxes
   ```

2. **Open the phase prompt**
   ```bash
   # Example for Phase 1:
   cat docs/prompts/phase-1-audit.md
   ```

3. **Copy the ENTIRE prompt**
   - Select all (Ctrl+A / Cmd+A)
   - Copy (Ctrl+C / Cmd+C)

4. **Paste into fresh AI chat**
   - Open Claude, ChatGPT, Perplexity, etc.
   - Start new conversation
   - Paste prompt
   - Follow AI's instructions

5. **Save and document results**
   ```bash
   # Save AI output to:
   docs/prompts/phase-N-results.md
   
   # Commit changes:
   git add .
   git commit -m "Phase N: [description]"
   
   # Update roadmap:
   # Mark tasks complete in ARCHITECTURE_MASTER.md
   ```

### Detailed Workflow

See [`../WORKFLOW.md`](../WORKFLOW.md) for comprehensive step-by-step instructions.

---

## Results Files

After completing each phase, create a results file:

```
docs/prompts/
  phase-1-results.md    ← Audit findings
  phase-2-results.md    ← Fixes applied
  phase-3-results.md    ← Quality improvements
  ...
```

**Template for results file:**

```markdown
# Phase N Results

**Date:** YYYY-MM-DD  
**Executed by:** [AI Assistant Name]  
**Time spent:** ~X hours

## Summary
[Brief overview]

## Changes Made
- File: description
- File: description

## Key Findings
- Finding 1
- Finding 2

## Issues Encountered
- Problem and resolution

## Metrics
| Metric | Before | After |
|--------|--------|-------|
| ... | ... | ... |

## Recommendations for Next Phase
- Recommendation 1
- Recommendation 2

## Links
- Commits: [SHA1], [SHA2]
- Related docs: [...]
```

---

## Best Practices

### Do's ✅

- **Always use fresh context** - Copy full prompt, don't assume AI remembers
- **Follow the order** - Complete Phase 1 before Phase 2, etc.
- **Document everything** - Save results files, update master docs
- **Test before committing** - Verify changes actually work
- **One phase at a time** - Don't mix phases

### Don'ts ❌

- **Don't skip phases** - Each builds on previous
- **Don't modify prompts** - They're designed carefully (unless you have good reason)
- **Don't lose results** - Always save AI output to results file
- **Don't forget to update roadmap** - Mark completed tasks in ARCHITECTURE_MASTER.md
- **Don't rush** - Quality over speed

---

## Troubleshooting

### "I'm in the middle of a phase and lost context"

**Solution:**
1. Check git log to see what was done: `git log --oneline -10`
2. Read the phase prompt again
3. Look at ARCHITECTURE_MASTER.md roadmap for completed tasks
4. Start new AI chat with: 
   ```
   [Paste full phase prompt]
   
   NOTE: Previous work was partially complete.
   Last commit: [SHA]
   Completed tasks: [list from roadmap]
   What should I focus on next?
   ```

### "AI output doesn't match expected format"

**Solution:**
1. Point AI to the "Output Format" section in prompt
2. Ask: "Please reformat your response to match the required output format exactly"
3. Provide example if needed

### "I want to skip a phase"

**Solution:**
Only skip if:
- Phase truly doesn't apply to your project
- You document the decision in ARCHITECTURE_MASTER.md
- You understand dependencies (e.g., Phase 3 assumes Phase 2 is done)

**Document in ARCHITECTURE_MASTER.md:**
```markdown
### Phase 2: Critical Fixes
**Status:** ⏭️ SKIPPED  
**Reason:** System already stable, no P0 issues  
**Date:** YYYY-MM-DD
```

### "I found errors in a prompt"

**Solution:**
1. Fix the prompt file
2. Commit with clear message
3. Add note in this README under "Prompt Changelog"

---

## Prompt Changelog

### 2026-02-22 - Initial Creation
- Created Phase 1 (Audit) prompt
- Created Phase 2 (Critical Fixes) prompt
- Created Phase 3 (Code Quality) prompt
- Established prompt structure and workflow

---

## Creating New Phase Prompts

When the project needs a new phase:

**1. Copy template** from WORKFLOW.md "Prompt Template" section

**2. Fill in all sections:**
- Context (what's the current state?)
- Task (what specific work needs done?)
- Requirements (what must be delivered?)
- Output Format (exact structure expected)
- Success Criteria (how to verify completion?)
- Examples (show good/bad code)
- Estimated Time (realistic effort estimate)

**3. Test the prompt:**
- Give it to an AI assistant
- See if output matches expectations
- Refine based on results

**4. Add to this README** in "Available Prompts" section

**5. Update ARCHITECTURE_MASTER.md** roadmap with new phase

---

## FAQ

**Q: Can I use different AI models for different phases?**  
A: Yes! That's the point. Each prompt is self-contained.

**Q: What if the AI can't access my git repo?**  
A: Paste file contents into chat when asked. The prompts guide the AI to request needed files.

**Q: How long does the full refactoring take?**  
A: Phases 1-3: ~6-8 weeks total. Phases 4-5: TBD.

**Q: Can I work on multiple phases in parallel?**  
A: Not recommended. Phases build on each other. Complete one before starting next.

**Q: What if I disagree with AI recommendations?**  
A: You're in charge. Document your decision in ARCHITECTURE_MASTER.md Decision Log and proceed your way.

**Q: How do I know a phase is really complete?**  
A: Check Success Criteria in the phase prompt. All must be ✅ before moving on.

---

## Related Documentation

- [`../ARCHITECTURE_MASTER.md`](../ARCHITECTURE_MASTER.md) - Project overview, roadmap, decision log
- [`../WORKFLOW.md`](../WORKFLOW.md) - Detailed workflow instructions
- [`../../README.md`](../../README.md) - Project README
- [`../../STAGE_28-30_README.md`](../../STAGE_28-30_README.md) - Current stage documentation

---

## Contact

If you're working on this project:
- Update this README when you create new prompts
- Document lessons learned
- Improve prompts based on experience
- Help future contributors by keeping docs current

---

**Ready to start?** Begin with [phase-1-audit.md](./phase-1-audit.md) 🚀
