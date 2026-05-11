# Planning & Agile Lifecycle

This rule defines the structure for all planning documents and the implementation of the 7-Phase Agile Loop in `tlm`.

## 1. Milestone Plans (`.cursor/plans/version/`)
Each major sub-version (e.g., `v0.3.0_foundation.md`) must follow this structure:
- **Audit**: Table of existing features vs. targeted requirements.
- **Goal**: High-level objective.
- **Sprints**: 4-8 granular sprints, each mapping to one full A-G cycle.
- **Tasklist**: Checkbox list for progress tracking.
- **Success Criteria**: Measurable outcomes for milestone completion.

## 2. The Planning Shard System
Shards are forward-compatibility contracts used when a current feature impacts a future milestone.

### When to Create a Shard:
- If your current code creates a data structure or API that a future feature (e.g., WebUI in v0.7.0) will need to consume.
- If you find a "gotcha" that doesn't matter now but will break v0.6.0's memory system.

### Shard Structure (`.cursor/plans/shards/<name>.shard.md`):
- **Target Version**: (e.g., `v0.7.0`)
- **Target Feature**: (e.g., `WebUI Integration`)
- **Contract**: The technical details (JSON schema, function signature, or logic requirement) the future developer must follow.

### Lifecycle:
1. **Plan Phase**: Check `SHARD_LEDGER.md` for shards matching your current version.
2. **Document Phase**: Write new shards for future impacts.
3. **Register**: Every new shard MUST be added to `SHARD_LEDGER.md`.

## 3. The 7-Phase Agile Loop (A-G)
Every sprint must progress through:
- **A: Plan** (Architecture/Shard check)
- **B: Build** (Implementation)
- **C: Test** (Pytest/Mypy)
- **D: Document** (Update `CODE_INDEX.md` and `GEMINI.md`)
- **E: QC** (Safety/Frugality audit)
- **F: Report** (Session report in `.cursor/plans/reports/`)
- **G: Polish** (Formatting/Refinement)
