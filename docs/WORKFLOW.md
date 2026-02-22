# Workflow Guide - Production-Grade Refactoring

> **Purpose:** This document explains how to work on the Digital Being project using a multi-stage workflow that preserves context across sessions.

---

## Problem We're Solving

**Challenge:** AI assistant conversations lose context. You can't rely on a single chat session to complete a large refactoring project.

**Solution:** Use a document-driven workflow where:
1. Master documents track project state
2. Phase-specific prompts contain all necessary context
3. Results are committed to git and documented
4. Any AI assistant can pick up where the last one left off

---

## Workflow Overview

```
┌──────────────────────────────────────┐
│  1. Check Current Phase              │
│     (ARCHITECTURE_MASTER.md)         │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  2. Get Phase Prompt                 │
│     (docs/prompts/phase-N.md)        │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  3. Execute in New Chat              │
│     (Copy entire prompt)             │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  4. Review Results                   │
│     (Validate output quality)        │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  5. Commit & Document                │
│     (Git commit + update docs)       │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  6. Mark Phase Complete              │
│     (Update ARCHITECTURE_MASTER.md)  │
└──────────────────────────────────────┘
```

---

## Step-by-Step Instructions

### Step 1: Check Current Phase

**Open:** `docs/ARCHITECTURE_MASTER.md`

**Find:** The "Refactoring Roadmap" section

**Identify:** Which phase you're working on (look for unchecked [ ] boxes)

Example:
```markdown
### Phase 1: Audit & Documentation (Week 1)
- [x] Complete code audit with quality scores  ← Done
- [ ] Document all architectural decisions      ← Next task
- [ ] Identify all technical debt
```

---

### Step 2: Get Phase Prompt

**Navigate to:** `docs/prompts/`

**Find:** The prompt file for your current phase
- Phase 1 = `phase-1-audit.md`
- Phase 2 = `phase-2-critical-fixes.md`
- Phase 3 = `phase-3-code-quality.md`
- etc.

**Open** the prompt file and **read it completely** before copying.

---

### Step 3: Execute in New Chat

#### For You (Human):

1. **Open a fresh AI assistant chat** (Claude, ChatGPT, Perplexity, etc.)

2. **Copy the ENTIRE prompt** from the phase file
   - Include all sections: Context, Task, Requirements, Output Format

3. **Paste and send**

4. **Follow the assistant's instructions**
   - It may ask clarifying questions
   - Provide file contents when requested
   - Give access to repository if possible

5. **Save the assistant's output**
   - Copy responses to files
   - Save generated code
   - Document findings

#### For AI Assistants:

If you're an AI assistant reading this:

1. **Start by reading:**
   - `docs/ARCHITECTURE_MASTER.md` (full project context)
   - The specific phase prompt you're executing
   - Relevant component docs in `docs/`

2. **Follow the prompt exactly:**
   - Use specified output formats
   - Include all required sections
   - Meet quality criteria

3. **Provide complete, actionable output:**
   - Don't leave TODOs or placeholders
   - Include file paths and line numbers
   - Give specific recommendations

4. **Document your decisions:**
   - Explain WHY you made choices
   - Note alternatives considered
   - Flag risks or concerns

---

### Step 4: Review Results

**Before accepting any output, verify:**

✅ **Completeness**
- All required sections present?
- No placeholder/TODO text?
- Specific file paths and line numbers?

✅ **Quality**
- Follows project style guide?
- Includes reasoning/explanations?
- Actionable recommendations?

✅ **Consistency**
- Aligns with ARCHITECTURE_MASTER.md?
- Doesn't contradict existing decisions?
- Matches current project structure?

**If issues found:**
- Ask the AI assistant to refine output
- Point to specific problems
- Reference style guide or examples

---

### Step 5: Commit & Document

#### 5a. Apply Changes to Code

**If the phase produced code changes:**

```bash
# Create a feature branch
git checkout -b refactor/phase-N-description

# Apply the changes
# (manually or via provided scripts)

# Test that it works
python main.py  # or appropriate test

# Commit
git add .
git commit -m "Refactor: Phase N - Description

Changes:
- Fixed X in Y
- Improved Z
- Added tests for W

See docs/prompts/phase-N-results.md for details"

# Merge to main
git checkout main
git merge refactor/phase-N-description
git push
```

#### 5b. Document Results

**Create:** `docs/prompts/phase-N-results.md`

**Template:**
```markdown
# Phase N Results

**Date:** YYYY-MM-DD
**Executed by:** [AI Assistant Name]
**Time spent:** ~X hours

## Summary
Brief overview of what was accomplished.

## Changes Made
- File path: description of change
- File path: description of change

## Key Findings
- Finding 1
- Finding 2

## Issues Encountered
- Problem 1 and how it was resolved
- Problem 2 and how it was resolved

## Recommendations for Next Phase
- Recommendation 1
- Recommendation 2

## Links
- Commit: [SHA]
- Related issues: #N
```

---

### Step 6: Mark Phase Complete

**Update:** `docs/ARCHITECTURE_MASTER.md`

**In the Roadmap section:**

```markdown
### Phase 1: Audit & Documentation (Week 1)
- [x] Complete code audit with quality scores     ← Add [x]
- [x] Document all architectural decisions        ← Add [x]
- [x] Identify all technical debt                 ← Add [x]
```

**Add completion note:**

```markdown
**Phase 1 Completed:** 2026-02-22  
**Results:** See docs/prompts/phase-1-results.md  
**Commits:** abc1234, def5678
```

**Commit documentation:**

```bash
git add docs/ARCHITECTURE_MASTER.md docs/prompts/phase-1-results.md
git commit -m "Docs: Mark Phase 1 complete"
git push
```

---

## Best Practices

### Do's ✅

- **Always start with fresh context** - Copy full prompts, don't rely on conversation history
- **Verify before committing** - Test changes actually work
- **Document decisions** - Update ARCHITECTURE_MASTER.md with any significant choices
- **Save incremental progress** - Commit after each completed task
- **Use descriptive commit messages** - Future you will thank you

### Don'ts ❌

- **Don't skip review step** - AI output needs human validation
- **Don't commit broken code** - Always test first
- **Don't lose context** - Update docs even if phase incomplete
- **Don't work on multiple phases simultaneously** - Finish one before starting next
- **Don't forget to mark tasks complete** - Keep roadmap current

---

## Emergency Recovery

### Lost Context Mid-Phase

**Problem:** Chat history lost, but phase not complete

**Solution:**
1. Check `git log` for last commit
2. Read `docs/prompts/phase-N.md` to see what should be done
3. Check ARCHITECTURE_MASTER.md roadmap for completed tasks
4. Start new chat with prompt + "Previous work was partially complete. Last commit: [SHA]. What should I do next?"

### Conflicting Changes

**Problem:** New work conflicts with previous commits

**Solution:**
1. Review `docs/prompts/phase-N-results.md` for previous rationale
2. Check Decision Log in ARCHITECTURE_MASTER.md
3. Decide which approach is better (document why)
4. Update Decision Log with new choice
5. Commit with clear message explaining the change

### Quality Issues Found Later

**Problem:** Past phase output has bugs or quality issues

**Solution:**
1. Create issue in ARCHITECTURE_MASTER.md "Known Problems"
2. Note which phase introduced it
3. Fix immediately if P0, otherwise schedule for future phase
4. Update phase-N-results.md with post-completion notes

---

## Prompt Template (For Creating New Phases)

When creating a new phase prompt, use this structure:

```markdown
# Phase N: [Name]

## Context
[Paste from ARCHITECTURE_MASTER.md - current state, goals, constraints]

## Task
[Specific, measurable objective for this phase]

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

## Input Files
- File 1: [path and description]
- File 2: [path and description]

## Output Format
[Exact structure expected in deliverables]

## Success Criteria
[How to verify the phase is complete]

## Estimated Effort
[Hours or days]

## Dependencies
- Phase X must be complete first
- Requires tool Y to be installed

## References
- Link to relevant docs
- Link to examples
```

---

## FAQ

**Q: Can I use different AI assistants for different phases?**  
A: Yes! That's the point of this system. Each phase prompt contains all needed context.

**Q: What if the AI assistant can't access my git repository?**  
A: Paste file contents into the chat, or describe the current state. Update the prompt with this info for next time.

**Q: How do I handle phases that take multiple chat sessions?**  
A: Break into sub-tasks. Complete one, commit, document, then start fresh chat for next sub-task.

**Q: What if I disagree with the AI's recommendations?**  
A: Document your decision in the Decision Log and explain why. You're in charge.

**Q: Can I skip phases?**  
A: Only if you document why in ARCHITECTURE_MASTER.md. Some phases have dependencies.

**Q: How do I know if output quality is good enough?**  
A: Check against the Success Criteria in the phase prompt. When in doubt, ask another AI to review it.

---

## Quick Reference Card

**Starting a New Phase:**
1. Read `docs/ARCHITECTURE_MASTER.md` → Find current phase
2. Open `docs/prompts/phase-N.md` → Get context
3. Copy full prompt → Paste in new AI chat
4. Execute → Save results

**Finishing a Phase:**
1. Review output → Verify quality
2. Apply changes → Test works
3. Commit code → Push to git
4. Document results → Save in `docs/prompts/phase-N-results.md`
5. Update roadmap → Mark tasks complete in ARCHITECTURE_MASTER.md
6. Commit docs → Push to git

**In Trouble:**
1. Check `git log` → See what was done
2. Read phase results → Understand decisions
3. Ask in new chat → "I'm working on Phase N, last commit was [SHA], what should I do?"

---

**Next:** See `docs/prompts/phase-1-audit.md` to begin refactoring work.
