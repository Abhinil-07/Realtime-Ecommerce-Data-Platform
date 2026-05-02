---
name: session-handoff
description: >
  Automates end-of-session handoff by updating PROGRESS.md with completed items, schema
  changes, Databricks decisions, and the exact next step. Use this skill when the user says
  "wrap up", "end session", "handoff", "we're done", "update progress", "save progress",
  "what did we do today", or any variation of ending the current work session. Also trigger
  at the end of any long coding session where significant work was completed, even if the
  user doesn't explicitly ask — offer to run the handoff. This ensures continuity between
  sessions so the next session can pick up exactly where this one left off.
---

# Session Handoff Skill

At the end of every session, update `PROGRESS.md` so the next session knows exactly what
was done and what to do next. This is the project's institutional memory.

## What to Update

### 1. Mark Completed Items ✅
In the "Medallion Layer Build Status" table, change status for any tables worked on:
- `⬜ Unknown` → `✅ Done` (with today's date in Notes)
- `⬜ Unknown` → `🔄 In Progress` (if partially done)
- `⬜ Unknown` → `❌ Blocked` (if blocked, with reason)

In the "Cross-Cutting Feature Checklist", check off completed items:
```markdown
- [x] Extract transformation logic into `src/transformations/*.py`  ← ✅ 2026-05-02
```

### 2. Document Schema Changes
If any table schema changed (columns added, renamed, types changed), add to the Schema
Change Log table:

```markdown
| 2026-05-02 | `silver_customer_dim` | Added `email` column (STRING) | Customer enrichment requirement |
```

### 3. Note Databricks Decisions
If any migration-relevant decisions were made, record them:
- "Decided to use `row_number()` instead of `monotonically_increasing_id()` for surrogate keys"
- "Confirmed MERGE syntax is identical in Databricks — no migration changes needed"

### 4. Write the Exact Next Step
Be specific — not "continue Silver" but:
```markdown
**Exact next step**: Implement `src/transformations/scd2.py` generic merge function.
Start with the `run_gate2_assertions()` function (see skill: scd2-merge for spec).
Then implement `scd2_merge()`. Test against `delivery_partner_dim` notebook first.
```

### 5. Update Last Session Summary
```markdown
## Last Session Summary

**Date**: 2026-05-02
**What was completed**: Created 11 skills for project automation (scd2-merge, dlq-writer, etc.)
**Open issues / blockers**: None
**Exact next step**: [specific next step]
**Databricks decisions made**: [list or "none"]
```

## Process

1. Review all changes made this session (files modified, tables created, code written)
2. Read current `PROGRESS.md` to understand what was already tracked
3. Apply all updates in a single edit to `PROGRESS.md`
4. Summarize the handoff to the user for confirmation

## When to Offer

If a session has been going on for a while and significant work was completed, proactively
offer: "Want me to update PROGRESS.md with what we did today before we wrap up?"
