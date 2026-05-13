# v0.4.0 Tasklist: Capabilities

This document tracks the component-level implementation status for the v0.4.0 milestone.

## Sprints Overview

| Sprint | Feature | Status |
|---|---|---|
| 1 | Plugin Hook System | 📅 Planned |
| 2 | Multi-language Containment | 📅 Planned |
| 3 | Source-Build Orchestration | 📅 Planned |
| 4 | `tlm ability` CLI | 📅 Planned |

## Component Breakdown

### Core Plugin Hook System
- [ ] Design non-destructive `src/` hooks
- [ ] Implement `ExtensionManager` in `src/tlm/plugins/`
- [ ] Define `Ability` interface (metadata, entrypoints)

### Containment Drivers
- [ ] `venv` isolation logic for Python
- [ ] `node_modules` isolation for Node.js
- [ ] Sandbox build staging logic

### Source-Build Logic
- [ ] Build orchestration for compiled tools
- [ ] Dependency resolution for system libs
- [ ] Binary linking and path management

### CLI & UI
- [ ] `tlm ability list`
- [ ] `tlm ability install <url/path>`
- [ ] `tlm ability test`
- [ ] `tlm ability uninstall`
