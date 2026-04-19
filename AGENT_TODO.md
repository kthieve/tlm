# AGENT_TODO — 0.2.0 and follow-ups

## 0.2.0b1 (done in tree)

- [x] Permissions / freelist / sandbox / root guard / GUI Permissions / installer + release workflow / log redaction / `tlm paths|allow|unallow` / `config migrate-keys`.

## 0.2.0b2 (done in tree)

- [x] Ask mode **Lightpanda** web tools: `tlm-web` fenced blocks, `config.toml` web keys, `tlm ask --no-web` / `tlm ? --no-web`.

## Next (0.3.0+)

- [ ] **`tlm ask --stream`** — CLI flag + `run_interactive_ask` path using `provider.stream`.
- [ ] **`tlm do` — structured re-parse after `e`** — Re-parse JSON after `$EDITOR` edits.
- [ ] **Pricing / tokens** — Grow `telemetry/prices.py`; document unknown-model cost as `None` in `summarize_usage` / JSONL.
- [ ] **Ask UX polish** — Optional Rich syntax highlighting in `ask_tools.print_markdown`.
- [ ] **GUI:** Chat tab and usage graphs; more log redaction UX.
- [ ] **`tlm write`:** Optional gate edit + JSON re-parse (parity with `do`).
- [ ] **Packaging:** Publish Homebrew / Scoop / winget; optional `.deb` in CI.
- [ ] **Man page:** Expand `docs/tlm.1` to full parity with `tlm help`.
