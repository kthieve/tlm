# Sprint 1: Plugin Hook System

## Goal
Design and implement a non-destructive hook system that allows `tlm` to be extended without modifying the core `src/` files.

## Phase A: Plan
- Define the `Ability` metadata format (JSON/TOML).
- Design the `ExtensionManager` to load plugins from `XDG_DATA_HOME/tlm/abilities/`.
- Identify core hook points (e.g., pre-command, post-command, custom provider registration).

## Phase B: Build
- [x] Create `src/tlm/plugins/base.py` for abstract base classes.
- [x] Create `src/tlm/plugins/manager.py` for discovery and lifecycle.
- [x] Add `extension_enabled = true` to `settings.py`.

## Phase C: Test
- [x] Unit tests for plugin discovery.
- [x] Mock a simple "Hello World" extension and verify hook execution.

## Phase D: Document
- [x] Update `CODE_INDEX.md` with the new `plugins` package.
- [x] Draft `docs/abilities.md` for developers.
