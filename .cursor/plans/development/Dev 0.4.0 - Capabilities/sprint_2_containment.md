# Sprint 2: Multi-language Containment

## Goal
Implement isolated environments for Abilities written in different languages (Python, Node.js) to prevent global environment contamination.

## Phase A: Plan
- Research `venv` creation speed and caching.
- Design the directory structure for isolated runtimes in `.tlm/runtimes/`.

## Phase B: Build
- [ ] Implement `src/tlm/plugins/runtimes/python.py` (automated `venv` creation).
- [ ] Implement `src/tlm/plugins/runtimes/node.py` (`npm install` isolation).
- [ ] Integrate runtime selection into `ExtensionManager`.

## Phase C: Test
- [ ] Verify that a Python Ability can import a dependency not present in the main `tlm` venv.
- [ ] Verify that `node_modules` are contained within the Ability folder.

## Phase D: Document
- [ ] Update `docs/abilities.md` with runtime configuration details.
