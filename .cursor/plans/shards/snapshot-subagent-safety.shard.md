# Shard: Snapshot Subagent Safety
- **Target Version**: v0.8.0
- **Target Feature**: Orchestration (Governor Role)
- **Origin**: v0.3.0 Foundation (Sprint 1)

## Context
Milestone 0.3.0 establishes the "Atomic Transaction" and "Temporal Snapshot" as the primary safety net for human-driven changes.

## Contract
In v0.8.0, when the **Governor** agent approves a set of autonomous changes proposed by the **Architect**, it MUST trigger a `snapshot.create_snapshot()` before any writes are committed. This ensures that even autonomous "sentient" errors can be reverted by the user with 100% fidelity using `tlm undo`.
