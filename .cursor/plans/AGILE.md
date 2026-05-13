# Agile Development Loop & Infrastructure

This document defines the strict engineering lifecycle for `tlm`. Adherence to this loop is mandatory for all developers and AI agents.

## 1. The 7-Phase Agile Loop

### Phase A: Plan
- **Goal**: Define the scope and architecture.
- **Action**: Read relevant `AGENT_PLAN.md` milestones and check `.cursor/plans/shards/SHARD_LEDGER.md` for target feature/version shards.
- **Output**: A brief plan summary shared with the user.

### Phase B: Build
- **Goal**: Implement logic.
- **Action**: Write surgical code. Follow PEP 8 and project-specific conventions in `GEMINI.md`.
- **Constraint**: Do not implement future features; leave shards instead.

### Phase C: Test
- **Goal**: Verify correctness.
- **Action**: Run existing tests (`pytest`). Write new tests for new features. Ensure 0 failures before proceeding.

### Phase D: Document
- **Goal**: Update the "AI Codex."
- **Action**: Update `CODE_INDEX.md` if files or roles changed. Add/Update `GEMINI.md` or `docs/*.md` as needed.

### Phase E: QC (Quality Control)
- **Goal**: Audit for standards.
- **Checklist**:
  - **Safety**: Does this respect the Four-Tier safety model?
  - **Frugality**: Is token usage minimized?
  - **Security**: No secrets or hardcoded keys?
  - **Types**: Run `mypy`.
  - **Lint**: Run `ruff check`.

### Phase F: Report
- **Goal**: Transparent progress.
- **Action**: Create a session report in `.cursor/plans/reports/vX.Y.Z_feature_name.report.md`.
- **Output**: A concise summary for the user.

### Phase G: Polish
- **Goal**: Final refinement.
- **Action**: Run `ruff format`. Refactor for readability. Remove debug logs/comments.

---

## 2. Versioning Strategy
We use **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`.
- **Patch**: Bug fixes, minor documentation, or QC/Polish cycles.
- **Minor**: New Features, Milestones (e.g., v0.3.0 -> v0.4.0), or major Shard implementations.
- **Major**: Architectural resets or 1.0.0 stability.

---

## 3. Development Folder & Tracking

For every **Minor** or **Major** version change (e.g., v0.3.0 → v0.4.0), developers must:
1. Create a dedicated folder: `.cursor/plans/development/Dev X.Y.Z - <Name>`.
2. Maintain modular tracking files within this folder:
   - `tasklist.md`: Component-level TODOs and sprint status.
   - `subversion_details.md`: Tracking of minor patches and internal version shifts.
   - `sprint_N_feature.md`: Granular phase-level planning for specific features.
3. Link to these files from the main milestone document in `.cursor/plans/version/vX.Y.Z_name.md`.

---

## 4. The Planning Shard System
See [`.cursor/plans/shards/README.md`](./shards/README.md) for detailed instructions.
Shards are the "connective tissue" between versions. They ensure Feature A remains compatible with the future Feature G.

---

## 5. The AI Codex (CODE_INDEX.md)
The primary navigation tool. AI Agents MUST use the Codex to locate files instead of scanning the full directory tree. This saves context and improves accuracy.
