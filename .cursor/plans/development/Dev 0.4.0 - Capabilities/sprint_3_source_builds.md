# Sprint 3: Source-Build Orchestration

## Goal
Enable `tlm` to download and compile tools from source (e.g., C++/Rust/Go) to expand its "Abilities" beyond Python/Node.

## Phase A: Plan
- Identify required system tools (gcc, make, cmake, cargo).
- Design the build staging area in `.tlm/build/`.

## Phase B: Build
- [ ] Create `src/tlm/plugins/orchestrator.py` for managing builds.
- [ ] Implement `AbilitySource` handler (git clone, wget).
- [ ] Implement build step runners (e.g., `make`, `python setup.py install`).

## Phase C: Test
- [ ] Attempt to build a simple C "Hello World" tool and verify it can be executed via `tlm`.
- [ ] Test cleanup logic: `tlm ability uninstall` should remove build artifacts.

## Phase D: Document
- [ ] Add "Source Builds" section to `docs/abilities.md`.
