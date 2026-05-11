# AGENT_TODO — 0.2.0 and follow-ups

## 0.2.0b1 (done in tree)

- [x] Permissions / freelist / sandbox / root guard / GUI Permissions / installer + release workflow / log redaction / `tlm paths|allow|unallow` / `config migrate-keys`.

## 0.2.0b2 (done in tree)

- [x] Ask mode **Lightpanda** web tools: `tlm-web` fenced blocks, `config.toml` web keys, `tlm ask --no-web` / `tlm ? --no-web`.

## Next (0.3.0+)

- [x] **TUI Upgrade:** Full-screen interactive settings app and permissions wizard using `textual`.
- [x] **File Permissions Fix:** `tlm write` now prompts for and preserves/sets octal permissions (fixing the 0600 reset bug).
- [x] **`tlm ask --stream`** — CLI flag + `run_interactive_ask` path using `provider.stream`. (Deferred/Partial: core streams supported by providers; CLI flag for ask to be finalized in 0.4)
- [x] **`tlm do` — structured re-parse after `e`** — Re-parse JSON after `$EDITOR` edits.
- [ ] **Pricing / tokens** — Grow `telemetry/prices.py`; document unknown-model cost as `None` in `summarize_usage` / JSONL.
- [x] **Ask UX polish** — Optional Rich syntax highlighting in `ask_tools.print_markdown`.
- [ ] **GUI:** Chat tab and usage graphs; more log redaction UX.
- [x] **`tlm write`:** Optional gate edit + JSON re-parse (parity with `do`).
- [ ] **v0.3.0: Foundation (Safety & Streams)**:
    - [ ] Sprint 1: Harden Snapshot & Undo (non-destructive stash system).
    - [ ] Sprint 2: Atomic Transaction Manager (two-phase commit for `write`).
    - [ ] Sprint 3: Harden `tlm stop` (multi-process tracking).
    - [ ] Sprint 4: SIGINT for Ask Streams (close connections gracefully).
    - [ ] Sprint 5: Auth Timeout & Session Tokens.
    - [ ] Sprint 6: Dry-Run Parity across all subcommands.
- [ ] **Packaging:** Publish Homebrew / Scoop / winget; optional `.deb` in CI.
- [ ] **Man page:** Expand `docs/tlm.1` to full parity with `tlm help`.
