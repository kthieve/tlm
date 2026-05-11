# Shard: Snapshot Worker Integration
- **Target Version**: v0.6.0
- **Target Feature**: Persistence (Worker State Recovery)
- **Origin**: v0.3.0 Foundation (Sprint 1)

## Context
Milestone 0.3.0 introduces a non-destructive temporal snapshot system using `git stash create`. 

## Contract
When implementing the background worker in v0.6.0, the worker state (active task, current stack) should be captured *within* the snapshot metadata. This ensures that a `tlm undo` can revert not just the filesystem, but also the worker's conceptual state to that exact point in time.
